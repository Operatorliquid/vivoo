#!/usr/bin/env node

const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const VERSION = 'v1.18.2';
const desktopRoot = path.resolve(__dirname, '..');
const projectRoot = path.resolve(desktopRoot, '../..');
const runtimeRoot = path.join(desktopRoot, 'runtime');
const binRoot = path.join(runtimeRoot, 'bin');
const configRoot = path.join(runtimeRoot, 'config');
const modelRoot = path.join(runtimeRoot, 'models');

function executable(name) {
  return process.platform === 'win32' ? `${name}.exe` : name;
}

function copyExecutable(source, destination) {
  if (!source || !fs.existsSync(source)) throw new Error(`No se encontró ${source || destination}`);
  fs.copyFileSync(source, destination);
  fs.chmodSync(destination, 0o755);
}

async function download(url, destination) {
  const response = await fetch(url, { redirect: 'follow' });
  if (!response.ok) throw new Error(`No se pudo descargar ${url}: HTTP ${response.status}`);
  fs.writeFileSync(destination, Buffer.from(await response.arrayBuffer()));
}

function assetName() {
  const platform = { darwin: 'darwin', win32: 'windows', linux: 'linux' }[process.platform];
  const arch = { arm64: 'arm64', x64: 'amd64' }[process.arch];
  if (!platform || !arch) throw new Error(`Plataforma sin soporte: ${process.platform}/${process.arch}`);
  return `mediamtx_${VERSION}_${platform}_${arch}.${process.platform === 'win32' ? 'zip' : 'tar.gz'}`;
}

async function prepareMediaMtx() {
  const asset = assetName();
  const release = `https://github.com/bluenviron/mediamtx/releases/download/${VERSION}`;
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'courtvision-mediamtx-'));
  const archive = path.join(temporary, asset);
  const checksums = path.join(temporary, 'checksums.sha256');
  await Promise.all([download(`${release}/${asset}`, archive), download(`${release}/checksums.sha256`, checksums)]);
  const expectedLine = fs.readFileSync(checksums, 'utf8').split(/\r?\n/).find((line) => line.endsWith(asset));
  if (!expectedLine) throw new Error(`El release no publicó checksum para ${asset}`);
  const expected = expectedLine.split(/\s+/)[0];
  const actual = crypto.createHash('sha256').update(fs.readFileSync(archive)).digest('hex');
  if (actual !== expected) throw new Error('El checksum de MediaMTX no coincide');
  const extract = path.join(temporary, 'extract');
  fs.mkdirSync(extract);
  const result = process.platform === 'win32'
    ? spawnSync('powershell', ['-NoProfile', '-Command', `Expand-Archive -LiteralPath '${archive.replaceAll("'", "''")}' -DestinationPath '${extract.replaceAll("'", "''")}'`], { stdio: 'inherit' })
    : spawnSync('tar', ['-xzf', archive, '-C', extract], { stdio: 'inherit' });
  if (result.status !== 0) throw new Error('No se pudo extraer MediaMTX');
  copyExecutable(path.join(extract, executable('mediamtx')), path.join(binRoot, executable('mediamtx')));
  fs.rmSync(temporary, { recursive: true, force: true });
}

async function main() {
  fs.rmSync(binRoot, { recursive: true, force: true });
  fs.rmSync(configRoot, { recursive: true, force: true });
  fs.rmSync(modelRoot, { recursive: true, force: true });
  fs.mkdirSync(binRoot, { recursive: true });
  fs.mkdirSync(configRoot, { recursive: true });
  fs.mkdirSync(modelRoot, { recursive: true });
  let ffmpegPath = require('ffmpeg-static');
  if (!fs.existsSync(ffmpegPath)) {
    const installer = require.resolve('ffmpeg-static/install.js');
    const result = spawnSync(process.execPath, [installer], { cwd: path.dirname(installer), stdio: 'inherit' });
    if (result.status !== 0) throw new Error('No se pudo preparar el binario portable de FFmpeg');
    ffmpegPath = require('ffmpeg-static');
  }
  copyExecutable(ffmpegPath, path.join(binRoot, executable('ffmpeg')));
  copyExecutable(require('ffprobe-static').path, path.join(binRoot, executable('ffprobe')));
  await prepareMediaMtx();
  fs.copyFileSync(path.join(projectRoot, 'infra/local/mediamtx.yml'), path.join(configRoot, 'mediamtx.yml'));
  const model = process.env.COURTVISION_POSE_MODEL || path.join(projectRoot, 'yolo26n-pose.pt');
  if (!fs.existsSync(model)) throw new Error('Falta yolo26n-pose.pt; definí COURTVISION_POSE_MODEL antes de empaquetar');
  fs.copyFileSync(model, path.join(modelRoot, 'yolo26n-pose.pt'));
  console.log(`Runtime nativo preparado en ${runtimeRoot}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
