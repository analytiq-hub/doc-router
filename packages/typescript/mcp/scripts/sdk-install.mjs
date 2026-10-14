/**
 * Install @docrouter/sdk for MCP builds without spawning a bare `npm` from PATH
 * (some setups have an ancient global npm in ~/node_modules/.bin).
 * Must be invoked from an npm lifecycle script so npm_execpath is set.
 */
import { spawnSync } from 'node:child_process';
import { mkdir, rm, symlink } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const mode = process.argv[2];
const mcpRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const sdkRoot = resolve(mcpRoot, '../sdk');
const npmExec = process.env.npm_execpath;

function runNpm(args, cwd = mcpRoot) {
  if (!npmExec) {
    console.error('Run via npm (e.g. npm run build:local). npm_execpath is unset.');
    process.exit(1);
  }
  const result = spawnSync(process.execPath, [npmExec, ...args], { cwd, stdio: 'inherit' });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

if (mode === 'local') {
  runNpm(['run', 'build'], sdkRoot);
  const linkPath = join(mcpRoot, 'node_modules/@docrouter/sdk');
  await mkdir(join(mcpRoot, 'node_modules/@docrouter'), { recursive: true });
  await rm(linkPath, { recursive: true, force: true });
  await symlink(sdkRoot, linkPath, 'dir');
  console.log(`Linked @docrouter/sdk -> ${sdkRoot}`);
} else if (mode === 'publish') {
  runNpm(['install', '@docrouter/sdk@^2.0.2'], mcpRoot);
} else {
  console.error('Usage: node scripts/sdk-install.mjs local|publish');
  process.exit(1);
}
