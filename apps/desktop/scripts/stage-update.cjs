const fs = require('node:fs');
const path = require('node:path');

const desktopRoot = path.resolve(__dirname, '..');
const distRoot = path.join(desktopRoot, 'dist');
const targetRoot = path.resolve(
  desktopRoot,
  '../../infra/deploy/desktop-updates',
  process.platform,
  process.arch,
);
const packageJson = JSON.parse(fs.readFileSync(path.join(desktopRoot, 'package.json'), 'utf8'));
const escapedVersion = String(packageJson.version).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const currentArtifact = new RegExp(`^vivoo-${escapedVersion}-`);

const allowed = process.platform === 'darwin'
  ? [/^latest-mac\.yml$/, /\.zip$/, /\.zip\.blockmap$/, /\.dmg$/, /\.dmg\.blockmap$/]
  : [/^latest\.yml$/, /\.exe$/, /\.exe\.blockmap$/];

if (!fs.existsSync(distRoot)) {
  throw new Error('No existe apps/desktop/dist. Generá el instalador antes de publicar.');
}

const files = fs.readdirSync(distRoot).filter((name) => (
  /^latest(?:-mac)?\.yml$/.test(name)
  || (currentArtifact.test(name) && allowed.some((pattern) => pattern.test(name)))
));
if (!files.some((name) => name.endsWith('.yml'))) {
  throw new Error('Falta el manifiesto de actualización generado por electron-builder.');
}

fs.mkdirSync(targetRoot, { recursive: true });
for (const name of files) {
  fs.copyFileSync(path.join(distRoot, name), path.join(targetRoot, name));
}

const manifestName = process.platform === 'darwin' ? 'latest-mac.yml' : 'latest.yml';
const manifest = fs.readFileSync(path.join(targetRoot, manifestName), 'utf8');
const advertised = [...manifest.matchAll(/^\s*-?\s*(?:url|path):\s*['"]?([^'"\r\n]+)['"]?\s*$/gm)]
  .map((match) => match[1].trim());
const missing = [...new Set(advertised)].filter((name) => !fs.existsSync(path.join(targetRoot, name)));
if (missing.length > 0) {
  throw new Error(`El manifiesto anuncia archivos inexistentes: ${missing.join(', ')}`);
}

process.stdout.write(`Actualización vivoo preparada en ${targetRoot}\n`);
