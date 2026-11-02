import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
export async function build() {
  const read = file => fs.readFile(path.join(root, file), 'utf8');
  const datasets = { stories: 'stories', defaults: 'screens', VIEW_EPICS: 'roadmap', ARCH_NODES: 'architecture-nodes', ARCH_EDGES: 'architecture-edges' };
  const declarations = [];
  for (const [name, file] of Object.entries(datasets)) {
    declarations.push(`const ${name}=${JSON.stringify(JSON.parse(await read(`designboard/data/${file}.json`)))};`);
  }
  const sections = [];
  for (const file of ['state', 'prototype', 'canvas', 'architecture-roadmap', 'persistence', 'bootstrap']) {
    sections.push(`// Source: designboard/src/${file}.js\n${await read(`designboard/src/${file}.js`)}`);
  }
  await fs.mkdir(path.join(root, 'dist/assets'), { recursive: true });
  await fs.writeFile(path.join(root, 'dist/index.html'), await read('designboard/index.html'));
  await fs.writeFile(path.join(root, 'dist/assets/styles.css'), await read('designboard/src/styles.css') + '\n' + await read('designboard/src/persistence.css'));
  await fs.writeFile(path.join(root, 'dist/assets/transfer.js'), await read('designboard/src/transfer.js'));
  await fs.writeFile(path.join(root, 'dist/assets/app.js'), `import { validateTransfer } from './transfer.js';\n(function(){'use strict';\n${declarations.join('\n')}\n${sections.join('\n')}\n})();\n`);
  console.log('Built dist/: 44-screen designboard with architecture and roadmap.');
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await build();
