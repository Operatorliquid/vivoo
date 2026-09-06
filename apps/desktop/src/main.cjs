const {
  app, BrowserWindow, dialog, Menu, nativeImage, powerMonitor, powerSaveBlocker, shell, Tray,
} = require('electron');
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const https = require('node:https');
const path = require('node:path');

const DASHBOARD_URL = process.env.COURTVISION_DASHBOARD_URL || 'http://54.232.8.119';
const LOCAL_DASHBOARD_PORT = 8780;
const LOCAL_RELAY_URL = 'rtsp://127.0.0.1:8554/courtvision';
const managed = new Map();
let quitting = false;
let logPath;
let dashboardProxy;
let updateInstallTimer;
let watchdogTimer;
let powerBlockerId;
let mainWindow;
let tray;
const serviceFailures = new Map();
const serviceStartedAt = new Map();

function redact(value) {
  return String(value).replace(/rtsp:\/\/[^\s/@]+:[^\s/@]+@/g, 'rtsp://***:***@');
}

function log(message) {
  const line = `${new Date().toISOString()} ${redact(message)}\n`;
  if (logPath) fs.appendFileSync(logPath, line, { encoding: 'utf8', mode: 0o600 });
}

function executableName(name) {
  return process.platform === 'win32' ? `${name}.exe` : name;
}

function runtimeRoot() {
  return app.isPackaged ? path.join(process.resourcesPath, 'runtime') : path.resolve(__dirname, '../runtime');
}

function dataRoot() {
  return path.join(app.getPath('appData'), 'CourtVision');
}

function developmentAgent() {
  const root = path.resolve(__dirname, '../../capture-agent');
  if (process.platform === 'win32') {
    return { command: 'py', prefix: ['-3', path.join(root, 'src/main.py')], env: { PYTHONPATH: path.join(root, 'src') } };
  }
  const virtualPython = path.join(root, '.venv', 'bin', 'python');
  return {
    command: fs.existsSync(virtualPython) ? virtualPython : 'python3',
    prefix: [path.join(root, 'src/main.py')],
    env: { PYTHONPATH: path.join(root, 'src') },
  };
}

function agentCommand() {
  if (!app.isPackaged) return developmentAgent();
  const command = path.join(runtimeRoot(), 'agent', 'courtvision-agent', executableName('courtvision-agent'));
  return { command, prefix: [], env: {} };
}

function spawnManaged(name, command, args, env = {}) {
  if (quitting) return;
  log(`Iniciando ${name}`);
  const child = spawn(command, args, {
    env: { ...process.env, ...env },
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  managed.set(name, child);
  serviceStartedAt.set(name, Date.now());
  child.stdout.on('data', (chunk) => log(`[${name}] ${chunk}`));
  child.stderr.on('data', (chunk) => log(`[${name}] ${chunk}`));
  child.on('error', (error) => log(`${name} no pudo iniciarse: ${error.message}`));
  child.on('close', (code, signal) => {
    if (managed.get(name) === child) managed.delete(name);
    log(`${name} finalizó (code=${code}, signal=${signal || 'none'})`);
    if (!quitting) {
      const stable = Date.now() - (serviceStartedAt.get(name) || 0) > 60_000;
      const failures = stable ? 0 : Math.min((serviceFailures.get(name) || 0) + 1, 8);
      serviceFailures.set(name, failures);
      const delay = Math.min(3_000 * (2 ** failures), 60_000);
      log(`${name} se reiniciará en ${Math.round(delay / 1000)}s`);
      setTimeout(() => startService(name), delay).unref();
    }
  });
}

function configPath() {
  return path.join(dataRoot(), 'agent.json');
}

function initializeAgent() {
  const agent = agentCommand();
  const dashboardApi = `${DASHBOARD_URL.replace(/\/$/, '')}/api`;
  const result = spawnSync(agent.command, [
    ...agent.prefix,
    '--config', configPath(),
    '--init',
    '--cloud-api-url', dashboardApi,
    '--storage-dir', path.join(dataRoot(), 'media'),
    '--relay-rtsp-url', LOCAL_RELAY_URL,
  ], {
    env: { ...process.env, ...agent.env },
    windowsHide: true,
    encoding: 'utf8',
  });
  if (result.status !== 0) {
    log(`No se pudo inicializar el agente: ${result.stderr || result.error || 'error desconocido'}`);
    return false;
  }
  return true;
}

function configureWindowsBackgroundTask() {
  const script = [
    "$action = New-ScheduledTaskAction -Execute $env:VIVOO_TASK_EXECUTABLE -Argument '--background'",
    "$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME",
    "$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew",
    "Register-ScheduledTask -TaskName 'VivooCaptureService' -Action $action -Trigger $trigger -Settings $settings -Description 'Mantiene activa la captura local de vivoo' -Force | Out-Null",
  ].join('; ');
  const encoded = Buffer.from(script, 'utf16le').toString('base64');
  const result = spawnSync('powershell.exe', [
    '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', encoded,
  ], {
    env: { ...process.env, VIVOO_TASK_EXECUTABLE: process.execPath },
    windowsHide: true,
    encoding: 'utf8',
  });
  if (result.status === 0) {
    log('Inicio protegido de Windows configurado');
    return true;
  }
  log(`No se pudo configurar el inicio protegido: ${result.stderr || result.error || 'error desconocido'}`);
  return false;
}

function configureStartup() {
  if (!app.isPackaged) return;
  if (process.platform === 'win32') {
    const scheduled = configureWindowsBackgroundTask();
    app.setLoginItemSettings({
      openAtLogin: !scheduled,
      openAsHidden: true,
      args: ['--background'],
    });
    return;
  }
  app.setLoginItemSettings({
    openAtLogin: true,
    openAsHidden: true,
    args: ['--background'],
  });
}

function startService(name) {
  if (managed.has(name) || quitting) return;
  const agent = agentCommand();
  if (name === 'agent') {
    spawnManaged(name, agent.command, [
      ...agent.prefix,
      '--config', configPath(),
      '--resources', runtimeRoot(),
    ], agent.env);
    return;
  }
  if (name === 'relay') {
    const relayBinary = path.join(runtimeRoot(), 'bin', executableName('mediamtx'));
    const relayConfig = path.join(runtimeRoot(), 'config', 'mediamtx.yml');
    if (!fs.existsSync(relayBinary) || !fs.existsSync(relayConfig)) {
      log('Relay local no disponible en este build; la cámara usará conexión directa');
      return;
    }
    spawnManaged(name, agent.command, [
      ...agent.prefix,
      '--config', configPath(),
      '--relay-supervisor',
      '--relay-binary', relayBinary,
      '--relay-config', relayConfig,
    ], agent.env);
  }
}

function stopServices() {
  quitting = true;
  for (const [name, child] of managed) {
    log(`Deteniendo ${name}`);
    if (!child.killed) child.kill();
  }
  managed.clear();
  dashboardProxy?.close();
  if (updateInstallTimer) clearTimeout(updateInstallTimer);
  if (watchdogTimer) clearInterval(watchdogTimer);
  if (Number.isInteger(powerBlockerId) && powerSaveBlocker.isStarted(powerBlockerId)) {
    powerSaveBlocker.stop(powerBlockerId);
  }
}

function ensureService(name) {
  if (quitting || managed.has(name)) return;
  startService(name);
}

async function ensureLocalRuntime() {
  const agentRunning = await endpointAvailable('http://127.0.0.1:8781/v1/status');
  if (!agentRunning) {
    const child = managed.get('agent');
    const age = Date.now() - (serviceStartedAt.get('agent') || 0);
    if (child && age > 45_000) {
      log('Watchdog: agente sin respuesta; reiniciando');
      child.kill();
    } else if (!child) {
      ensureService('agent');
    }
  } else {
    serviceFailures.set('agent', 0);
  }

  const relayRunning = await endpointAvailable('http://127.0.0.1:9997/v3/config/global/get');
  if (!relayRunning && !managed.has('relay')) ensureService('relay');
  if (relayRunning) serviceFailures.set('relay', 0);
}

function startRuntimeWatchdog() {
  void ensureLocalRuntime();
  watchdogTimer = setInterval(() => void ensureLocalRuntime(), 15_000);
  watchdogTimer.unref();
  powerMonitor.on('resume', () => {
    log('Equipo reanudado; verificando cámara y detector');
    setTimeout(() => void ensureLocalRuntime(), 2_000).unref();
  });
}

async function endpointAvailable(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1200);
  try {
    const response = await fetch(url, { signal: controller.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

async function localAgentStatus() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1500);
  try {
    const response = await fetch('http://127.0.0.1:8781/v1/status', { signal: controller.signal });
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

function hasActiveRecording(status) {
  if (!status || typeof status !== 'object') return false;
  if (status.state?.recording === true || status.recording?.active === true) return true;
  return Array.isArray(status.cameras) && status.cameras.some(
    (camera) => camera?.state?.recording === true || camera?.recording?.active === true,
  );
}

async function migrateLegacyCameraServices() {
  if (!app.isPackaged || process.platform !== 'darwin') return;
  const labels = ['com.courtvision.capture-agent', 'com.courtvision.media-relay'];
  const launchAgents = path.join(app.getPath('home'), 'Library', 'LaunchAgents');
  const plists = labels.map((label) => path.join(launchAgents, `${label}.plist`)).filter(fs.existsSync);
  if (plists.length === 0) return;
  if (hasActiveRecording(await localAgentStatus())) {
    log('Migración de servicios antiguos diferida: hay un partido grabándose');
    return;
  }
  const domain = `gui/${process.getuid()}`;
  for (const plist of plists) {
    spawnSync('launchctl', ['bootout', domain, plist], { windowsHide: true, encoding: 'utf8' });
    try { fs.unlinkSync(plist); } catch (error) { log(`No se pudo retirar ${path.basename(plist)}: ${error.message}`); }
  }
  log('Servicios antiguos reemplazados por el runtime integrado de vivoo');
  await new Promise((resolve) => setTimeout(resolve, 1200));
}

function startAutomaticUpdates() {
  if (!app.isPackaged) return;
  const { autoUpdater } = require('electron-updater');
  const updateBase = process.env.COURTVISION_UPDATE_URL
    || `${DASHBOARD_URL.replace(/\/$/, '')}/desktop-updates/${process.platform}/${process.arch}`;
  autoUpdater.setFeedURL({ provider: 'generic', url: updateBase });
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.on('error', (error) => log(`Actualización: ${error.message}`));
  autoUpdater.on('update-available', (info) => log(`Actualización ${info.version} disponible`));
  autoUpdater.on('update-not-available', () => log('vivoo está actualizado'));
  autoUpdater.on('update-downloaded', (info) => {
    log(`Actualización ${info.version} descargada; esperando una pausa segura`);
    const installWhenSafe = async () => {
      if (hasActiveRecording(await localAgentStatus())) {
        updateInstallTimer = setTimeout(installWhenSafe, 60_000);
        return;
      }
      log(`Instalando actualización ${info.version}`);
      updateInstallTimer = setTimeout(() => autoUpdater.quitAndInstall(false, true), 3000);
    };
    void installWhenSafe();
  });
  const check = () => autoUpdater.checkForUpdates().catch((error) => log(`Actualización: ${error.message}`));
  setTimeout(check, 15_000);
  setInterval(check, 6 * 60 * 60 * 1000).unref();
}

function startDashboardProxy() {
  const cloud = new URL(DASHBOARD_URL);
  return new Promise((resolve, reject) => {
    dashboardProxy = http.createServer((request, response) => {
      if (request.url === '/__courtvision/runtime') {
        const body = JSON.stringify({
          cloud_api_url: `${DASHBOARD_URL.replace(/\/$/, '')}/api`,
          public_app_url: DASHBOARD_URL.replace(/\/$/, ''),
        });
        response.writeHead(200, {
          'Content-Type': 'application/json; charset=utf-8',
          'Content-Length': Buffer.byteLength(body),
          'Cache-Control': 'no-store',
        });
        response.end(body);
        return;
      }
      const target = new URL(request.url || '/', cloud);
      if (target.origin !== cloud.origin) {
        response.writeHead(400, { 'Content-Type': 'text/plain; charset=utf-8' });
        response.end('Solicitud no válida.');
        return;
      }
      const transport = target.protocol === 'https:' ? https : http;
      const upstream = transport.request(target, {
        method: request.method,
        headers: { ...request.headers, host: cloud.host },
      }, (upstreamResponse) => {
        const headers = { ...upstreamResponse.headers };
        if (typeof headers.location === 'string') {
          headers.location = headers.location.replace(cloud.origin, `http://127.0.0.1:${dashboardProxy.address().port}`);
        }
        response.writeHead(upstreamResponse.statusCode || 502, headers);
        upstreamResponse.pipe(response);
      });
      upstream.on('error', (error) => {
        log(`Proxy del dashboard: ${error.message}`);
        if (!response.headersSent) response.writeHead(502, { 'Content-Type': 'text/plain; charset=utf-8' });
        response.end('vivoo no pudo conectarse con el servidor.');
      });
      request.pipe(upstream);
    });
    dashboardProxy.once('error', reject);
    dashboardProxy.listen(LOCAL_DASHBOARD_PORT, '127.0.0.1', () => {
      resolve(`http://127.0.0.1:${dashboardProxy.address().port}`);
    });
  });
}

function createWindow(appUrl) {
  const dashboardOrigin = new URL(appUrl).origin;
  const window = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1024,
    minHeight: 720,
    backgroundColor: '#090d0c',
    title: 'vivoo',
    show: false,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  mainWindow = window;
  const launchedInBackground = process.argv.includes('--background');
  window.once('ready-to-show', () => {
    if (!launchedInBackground) window.show();
  });
  window.on('close', (event) => {
    if (quitting) return;
    event.preventDefault();
    window.hide();
    log('Ventana oculta; la captura continúa en segundo plano');
  });
  window.on('closed', () => { if (mainWindow === window) mainWindow = undefined; });
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (new URL(url).origin === dashboardOrigin) return { action: 'allow' };
    void shell.openExternal(url);
    return { action: 'deny' };
  });
  window.webContents.on('will-navigate', (event, url) => {
    if (new URL(url).origin !== dashboardOrigin) {
      event.preventDefault();
      void shell.openExternal(url);
    }
  });
  window.loadURL(appUrl).catch((error) => {
    log(`No se pudo abrir el dashboard: ${error.message}`);
    dialog.showErrorBox('Sin conexión', 'No pudimos abrir vivoo. Revisá la conexión a internet e intentá nuevamente.');
  });
}

function showMainWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
}

function createTray() {
  if (tray) return;
  const iconPath = path.join(__dirname, '../build/icon.png');
  let icon = nativeImage.createFromPath(iconPath);
  if (process.platform === 'darwin') icon = icon.resize({ width: 18, height: 18 });
  tray = new Tray(icon);
  tray.setToolTip('vivoo · captura activa');
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Abrir vivoo', click: showMainWindow },
    { type: 'separator' },
    {
      label: 'Salir y detener captura',
      click: () => {
        quitting = true;
        app.quit();
      },
    },
  ]));
  tray.on('double-click', showMainWindow);
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.whenReady().then(async () => {
    const logsDirectory = path.join(dataRoot(), 'logs');
    fs.mkdirSync(logsDirectory, { recursive: true, mode: 0o700 });
    logPath = path.join(logsDirectory, 'desktop.log');
    configureStartup();
    powerBlockerId = powerSaveBlocker.start('prevent-app-suspension');
    log(`Protección contra suspensión activa (${powerBlockerId})`);
    createTray();
    if (!fs.existsSync(configPath()) && !initializeAgent()) {
      dialog.showErrorBox('vivoo', 'No se pudo preparar el equipo local. El detalle quedó guardado en los registros de vivoo.');
    } else {
      await migrateLegacyCameraServices();
      const relayRunning = await endpointAvailable('http://127.0.0.1:9997/v3/config/global/get');
      if (relayRunning) log('Relay local existente detectado'); else startService('relay');
      const agentRunning = await endpointAvailable('http://127.0.0.1:8781/v1/status');
      if (agentRunning) log('Agente local existente detectado'); else startService('agent');
      startRuntimeWatchdog();
    }
    try {
      createWindow(await startDashboardProxy());
      startAutomaticUpdates();
    } catch (error) {
      log(`No se pudo iniciar el acceso local al dashboard: ${error.message}`);
      dialog.showErrorBox('vivoo', 'No se pudo abrir la aplicación local. Reiniciá vivoo e intentá nuevamente.');
    }
  });
}

app.on('before-quit', () => {
  quitting = true;
  stopServices();
});
app.on('window-all-closed', () => {
  log('Todas las ventanas cerradas; servicios locales continúan activos');
});
app.on('activate', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    showMainWindow();
  } else if (dashboardProxy?.address()) {
    createWindow(`http://127.0.0.1:${dashboardProxy.address().port}`);
  }
});
app.on('second-instance', showMainWindow);
