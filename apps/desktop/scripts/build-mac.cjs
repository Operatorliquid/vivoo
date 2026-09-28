const { execFileSync, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

if (process.platform !== 'darwin') {
  throw new Error('El instalador de macOS debe generarse en macOS.');
}

const desktopRoot = path.resolve(__dirname, '..');
const packageJson = JSON.parse(fs.readFileSync(path.join(desktopRoot, 'package.json'), 'utf8'));
const outputRoot = path.join(os.tmpdir(), `vivoo-desktop-build-${packageJson.version}-${process.arch}`);
const distRoot = path.join(desktopRoot, 'dist');
fs.rmSync(outputRoot, { recursive: true, force: true });

const args = [
  'exec', 'electron-builder', '--mac', 'dmg', 'zip',
  `--config.directories.output=${outputRoot}`,
  `--config.icon=${path.join(desktopRoot, 'build/icon.png')}`,
  `--config.mac.entitlements=${path.join(desktopRoot, 'build/entitlements.mac.plist')}`,
  `--config.mac.entitlementsInherit=${path.join(desktopRoot, 'build/entitlements.mac.plist')}`,
];
if (!process.env.CSC_LINK && !process.env.CSC_NAME) {
  args.push('--config.mac.identity=-');
}

const build = spawnSync('pnpm', args, { cwd: desktopRoot, env: process.env, stdio: 'inherit' });
if (build.status !== 0) process.exit(build.status || 1);

const appPath = fs.readdirSync(outputRoot, { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && entry.name.startsWith('mac'))
  .map((entry) => path.join(outputRoot, entry.name, 'vivoo.app'))
  .find(fs.existsSync);
if (!appPath) throw new Error('electron-builder no generó vivoo.app.');

execFileSync('codesign', ['--verify', '--deep', '--strict', '--verbose=2', appPath], { stdio: 'inherit' });
execFileSync('codesign', ['-dv', '--verbose=2', appPath], { stdio: 'inherit' });

fs.rmSync(distRoot, { recursive: true, force: true });
fs.mkdirSync(distRoot, { recursive: true });
const releaseFiles = fs.readdirSync(outputRoot).filter((name) => (
  /\.(?:dmg|zip|blockmap)$/.test(name) || /^latest-mac\.yml$/.test(name)
));
if (!releaseFiles.some((name) => name === 'latest-mac.yml')) {
  throw new Error('El build no generó latest-mac.yml.');
}
for (const name of releaseFiles) {
  fs.copyFileSync(path.join(outputRoot, name), path.join(distRoot, name));
}
fs.rmSync(outputRoot, { recursive: true, force: true });
process.stdout.write(`Instalador macOS ${packageJson.version} validado en ${distRoot}\n`);
