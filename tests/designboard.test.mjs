import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { validateTransfer } from '../designboard/src/transfer.js';

const data = async name => JSON.parse(await fs.readFile(new URL(`../designboard/data/${name}.json`, import.meta.url), 'utf8'));
const screens = await data('screens');
const stories = await data('stories');
const epics = await data('roadmap');
const nodes = await data('architecture-nodes');
const edges = await data('architecture-edges');
const tasks = epics.flatMap(e => e.features.flatMap(f => f.tasks));
const taskIds = tasks.map(t => t.id);
const nodeIds = nodes.map(n => n.id);
const archive = await fs.readFile(new URL('../docs/original/specbound-designboard.html', import.meta.url), 'utf8');

test('original screens and architecture remain unchanged while roadmap evolves', () => {
  for (const [name, value] of Object.entries({ defaults: screens, stories, ARCH_NODES: nodes, ARCH_EDGES: edges })) {
    assert.deepEqual(value, JSON.parse(archive.match(new RegExp(`^const ${name}=(.*);$`, 'm'))[1]));
  }
  const original = JSON.parse(archive.match(/^const VIEW_EPICS=(.*);$/m)[1]);
  for (const originalEpic of original) {
    const current = structuredClone(epics.find(e => e.id === originalEpic.id));
    assert.ok(current, `Original epic ${originalEpic.id} missing`);
    if (current.id === 'E08') current.phase = originalEpic.phase;
    for (const feature of current.features) for (const task of feature.tasks) delete task.phase;
    assert.deepEqual(current, originalEpic);
  }
  assert.equal(screens.length, 44);
  assert.equal(stories.length, 9);
});

test('phase 1 covers every reference screen and former later tasks use phase 3', () => {
  const uiEpic = epics.find(e => e.id === 'E11');
  assert.equal(uiEpic.phase, 'Phase 1');
  const uiTasks = uiEpic.features.flatMap(f => f.tasks);
  assert.equal(uiTasks.length, 16);
  const covered = uiTasks.flatMap(t => t.screens);
  assert.deepEqual(covered.sort(), screens.map(s => s.id).sort());
  assert.equal(new Set(covered).size, covered.length);
  for (const id of ['T024', 'T026', 'T027', 'T046', 'T047']) {
    assert.equal(tasks.find(t => t.id === id).phase, 'Phase 3');
  }
  assert.equal(tasks.filter(t => t.phase === 'Phase 3').length, 5);
  assert.equal(epics.find(e => e.id === 'E08').phase, 'Phase 2');
});

test('stories and architecture have no missing references; tasks form a DAG', () => {
  assert.equal(new Set(taskIds).size, tasks.length);
  assert.deepEqual(stories.flatMap(s => s.screenIds).sort(), screens.map(s => s.id).sort());
  for (const [from, to] of edges) assert.ok(nodeIds.includes(from) && nodeIds.includes(to));
  const visited = new Set();
  function visit(id, visiting = new Set()) {
    assert.ok(taskIds.includes(id), `Unknown dependency ${id}`);
    assert.ok(!visiting.has(id), `Cycle at ${id}`);
    if (visited.has(id)) return;
    const next = new Set(visiting).add(id);
    for (const dep of tasks.find(t => t.id === id).deps) visit(dep, next);
    visited.add(id);
  }
  taskIds.forEach(id => visit(id));
});

const backup = () => ({
  format: 'specbound-workspace', version: 1,
  board: { format: 'atelier-designboard', version: 3, screens: structuredClone(screens), notes: [{ id: 'note-test', screenId: 'packs', text: 'Feedback', x: 555, y: 502 }], selected: 'packs', zoom: .4, tx: -15, ty: 80, tool: 'note' },
  roadmapProgress: { T001: true, T002: false },
  draftNote: { screenId: 'packs', text: 'Noch nicht platziert' },
  view: { main: 'architecture', architectureTab: 'deploy', architectureNode: 'evaluate', deployment: 'ecs' },
});
const validate = value => validateTransfer(value, screens, taskIds, nodeIds);

test('backup round trip preserves notes, drafts, viewport, and progress', () => {
  const source = backup();
  const result = validate(JSON.parse(JSON.stringify(source)));
  assert.deepEqual(result.board, source.board);
  assert.deepEqual(result.roadmapProgress, source.roadmapProgress);
  assert.deepEqual(result.view, source.view);
  assert.deepEqual(result.draftNote, source.draftNote);
  assert.notEqual(result.board.screens, source.board.screens);
});

test('legacy Board JSON imports without overwriting roadmap progress', () => {
  assert.deepEqual(validate(backup().board), { board: backup().board });
});

test('invalid imports are rejected before application state changes', () => {
  for (const corrupt of [
    b => { b.version = 99; },
    b => { b.board.screens.pop(); },
    b => { b.board.screens[1].id = b.board.screens[0].id; },
    b => { b.board.notes[0].x = NaN; },
    b => { b.board.notes[0].screenId = 'missing'; },
    b => { b.board.notes[0].id = '\" onclick=\"bad'; },
    b => { b.roadmapProgress.T999 = true; },
    b => { b.view.deployment = 'missing'; },
    b => { b.board.zoom = 0; },
  ]) {
    const input = backup(); corrupt(input);
    assert.throws(() => validate(input));
  }
});
