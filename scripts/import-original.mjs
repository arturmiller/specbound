// One-time, reproducible extraction. The archived HTML is never rewritten.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const source = process.argv[2];
if (!source) throw new Error('Usage: node scripts/import-original.mjs <original.html>');
const bytes = await fs.readFile(source);
const html = bytes.toString('utf8').replace(/\r\n/g, '\n');
for (const dir of ['docs/original', 'designboard/src', 'designboard/data']) {
  await fs.mkdir(path.join(root, dir), { recursive: true });
}
const archive = path.join(root, 'docs/original/specbound-designboard.html');
await fs.writeFile(archive, bytes, { flag: 'wx' });
let js = html.match(/<script>([\s\S]*?)<\/script>/)[1];
js = js.replace("(function(){'use strict';", '').replace(/\}\)\(\);\s*$/, '');
for (const [name, file] of Object.entries({ stories: 'stories', defaults: 'screens', VIEW_EPICS: 'roadmap', ARCH_NODES: 'architecture-nodes', ARCH_EDGES: 'architecture-edges' })) {
  const regex = new RegExp(`^const ${name}=(.*);$`, 'm');
  const match = js.match(regex);
  if (!match) throw new Error(`Missing dataset: ${name}`);
  const value = JSON.parse(match[1]);
  await fs.writeFile(path.join(root, `designboard/data/${file}.json`), JSON.stringify(value, null, 2) + '\n');
  js = js.replace(regex, '');
}
const prototypeStart = js.indexOf('const status=');
const canvasStart = js.indexOf('function switchScreen(');
const architectureStart = js.indexOf('// ---- Separate workspaces:');
const bootStart = js.lastIndexOf('renderStage();renderSide();updateTool();requestAnimationFrame');
const sections = {
  'state.js': js.slice(0, prototypeStart),
  'prototype.js': js.slice(prototypeStart, canvasStart),
  'canvas.js': js.slice(canvasStart, architectureStart),
  'architecture-roadmap.js': js.slice(architectureStart, bootStart),
  'bootstrap.js': js.slice(bootStart),
};
for (const [file, text] of Object.entries(sections)) {
  await fs.writeFile(path.join(root, 'designboard/src', file), text.trim() + '\n');
}
await fs.writeFile(path.join(root, 'designboard/src/styles.css'), html.match(/<style>([\s\S]*?)<\/style>/)[1].trim() + '\n');
const template = html.replace(/<style>[\s\S]*?<\/style>/, '<link rel="stylesheet" href="./assets/styles.css">')
  .replace(/<script>[\s\S]*?<\/script>/, '<script type="module" src="./assets/app.js"></script>');
await fs.writeFile(path.join(root, 'designboard/index.html'), template);
console.log('Archived original and extracted five datasets, styles, and application sections.');
