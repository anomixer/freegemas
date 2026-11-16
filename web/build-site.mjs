// Assemble the Freegemas browser landing page.
//
//   node web/build-site.mjs
//   node web/build-site.mjs --out <dir> --wasm-dist <dir> --x16-dist <dir>
//
// This script does not compile either browser port.  Run the port builds first:
//   platform/wasm/build.sh (or platform/wasm/build.ps1 on Windows)
//   node x16/web/build.mjs
// Then run this script; it copies the landing page and both players into a
// single static directory suitable for GitHub Pages.

import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');

function arg(name) {
  const i = process.argv.indexOf(name);
  if (i < 0) return undefined;
  const value = process.argv[i + 1];
  if (!value || value.startsWith('--')) throw new Error(`${name} needs a directory argument`);
  return value;
}

const outDir = resolve(here, arg('--out') ?? '_site');
const wasmDir = resolve(here, arg('--wasm-dist') ?? join(root, 'build-wasm'));
const x16Dir = resolve(here, arg('--x16-dist') ?? join(root, 'x16', 'web', 'dist'));

function required(file, hint) {
  if (!existsSync(file)) {
    throw new Error(`missing ${file}\n${hint}`);
  }
  return file;
}

required(join(here, 'index.html'), 'The landing page source is missing.');
required(join(here, 'assets', 'freegemas-logo.png'), 'The landing-page logo is missing.');
const wasmHtml = required(join(wasmDir, 'freegemas.html'),
  'Build the native WebAssembly player first: platform/wasm/build.sh (Linux/macOS) or platform/wasm/build.ps1 (Windows).');
for (const name of ['freegemas.js', 'freegemas.wasm', 'freegemas.data']) {
  required(join(wasmDir, name), 'The native WebAssembly build is incomplete; rebuild it with platform/wasm/build.sh or platform/wasm/build.ps1.');
}
required(join(x16Dir, 'index.html'),
  'Build the Commander X16 browser player first: node x16/web/build.mjs.');
required(join(x16Dir, 'favicon.png'),
  'The Commander X16 build did not copy its favicon; rebuild with node x16/web/build.mjs.');

mkdirSync(outDir, { recursive: true });
for (const name of readdirSync(outDir)) {
  rmSync(join(outDir, name), { recursive: true, force: true });
}

// Landing page and its local images.
cpSync(join(here, 'index.html'), join(outDir, 'index.html'));
cpSync(join(here, 'assets'), join(outDir, 'assets'), { recursive: true });
writeFileSync(join(outDir, '.nojekyll'), '');

// The native build writes freegemas.html/.js/.wasm/.data. Publish the entry
// point as wasm/index.html so existing landing-page links keep working.
const wasmOut = join(outDir, 'wasm');
mkdirSync(wasmOut, { recursive: true });
cpSync(wasmHtml, join(wasmOut, 'index.html'));
for (const name of ['freegemas.js', 'freegemas.wasm', 'freegemas.data']) {
  cpSync(join(wasmDir, name), join(wasmOut, name));
}
if (existsSync(join(wasmDir, 'favicon.png'))) {
  cpSync(join(wasmDir, 'favicon.png'), join(wasmOut, 'favicon.png'));
}
cpSync(x16Dir, join(outDir, 'x16'), { recursive: true });

// A small map of the deployed pages, useful for later inspection without
// guessing at the workflow layout.
const players = {
  landing: 'index.html',
  wasm: 'wasm/index.html',
  x16: 'x16/index.html',
  a2vera: 'https://apple2ts.com/?slot2=vera&tab=vera#https://raw.githubusercontent.com/anomixer/freegemas/master/vera/freegemas.hdv',
  iigs: 'https://a2gsemu-ia.pages.dev/?lang=en&game=https%3A%2F%2Fgithub.com%2Fanomixer%2Ffreegemas',
};
writeFileSync(join(outDir, 'players.json'), `${JSON.stringify(players, null, 2)}\n`);

function size(path) {
  const s = statSync(path);
  return s.isDirectory() ? 0 : s.size;
}

const wasmBytes = statSync(join(wasmOut, 'freegemas.js')).size
  + statSync(join(wasmOut, 'freegemas.wasm')).size
  + statSync(join(wasmOut, 'freegemas.data')).size;
const x16Index = readFileSync(join(outDir, 'x16', 'index.html'), 'utf8');
console.log(`site: ${outDir}`);
console.log(`players: WebAssembly (${wasmBytes} bytes) + X16 (${size(join(outDir, 'x16', 'game', 'game'))} byte game)`);
console.log(`landing refs: ${/wasm\/index\.html/.test(readFileSync(join(outDir, 'index.html'), 'utf8')) ? 'wasm' : '?'} and ${/x16\/index\.html/.test(readFileSync(join(outDir, 'index.html'), 'utf8')) ? 'x16' : '?'}`);
if (!x16Index.includes('app.js')) console.log('warning: X16 index.html does not reference app.js');
