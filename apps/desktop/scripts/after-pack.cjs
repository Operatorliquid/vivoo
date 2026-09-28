const { execFileSync } = require('node:child_process');
const path = require('node:path');

/**
 * Finder and browser downloads can attach resource forks or provenance xattrs
 * to native binaries. macOS refuses to sign an update bundle containing them.
 * CI normally starts clean, but applying the same cleanup everywhere makes the
 * release reproducible and prevents publishing a package ShipIt cannot install.
 */
module.exports = async function afterPack(context) {
  if (context.electronPlatformName !== 'darwin') return;
  const appName = `${context.packager.appInfo.productFilename}.app`;
  const appPath = path.join(context.appOutDir, appName);
  execFileSync('xattr', ['-cr', appPath], { stdio: 'inherit' });
};
