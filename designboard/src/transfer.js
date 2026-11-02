// Pure validation shared by the browser importer and Node regression tests.
export function validateTransfer(input, screens, taskIds, nodeIds) {
  const require = (condition, message) => { if (!condition) throw new Error(message); };
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  require(input && typeof input === 'object', 'Keine gültige Sicherung.');
  const full = input.format === 'specbound-workspace';
  require(!full || input.version === 1, 'Unbekannte Sicherungsversion.');
  const board = structuredClone(full ? input.board : input);
  require(board?.format === 'atelier-designboard' && board.version === 3, 'Bitte einen Specbound-Export oder Board-JSON Version 3 wählen.');
  require(Array.isArray(board.screens) && board.screens.length === screens.length, 'Die Sicherung muss alle aktuellen Screens enthalten.');
  const known = new Map(screens.map(s => [s.id, s]));
  const ids = new Set();
  for (const screen of board.screens) {
    require(screen && known.has(screen.id) && !ids.has(screen.id), 'Unbekannte oder doppelte Screen-ID.');
    ids.add(screen.id);
    require(typeof screen.name === 'string' && typeof screen.subtitle === 'string', 'Screen-Text fehlt.');
    require(screen.story === known.get(screen.id).story && finite(screen.x) && finite(screen.y), 'Ungültige Screen-Position oder Story.');
  }
  require(Array.isArray(board.notes), 'Notizen fehlen.');
  const noteIds = new Set();
  for (const note of board.notes) {
    require(note && typeof note.id === 'string' && /^[\w-]+$/.test(note.id) && !noteIds.has(note.id), 'Ungültige oder doppelte Notiz-ID.');
    noteIds.add(note.id);
    require(known.has(note.screenId) && typeof note.text === 'string', 'Ungültige Notizreferenz.');
    require(finite(note.x) && finite(note.y) && note.x >= 0 && note.x <= 1160 && note.y >= 0 && note.y <= 760, 'Notizposition außerhalb des Screens.');
  }
  require(known.has(board.selected) && finite(board.zoom) && board.zoom >= .065 && board.zoom <= 1.5 && finite(board.tx) && finite(board.ty), 'Ungültige Board-Ansicht.');
  require(['select', 'hand', 'note'].includes(board.tool), 'Ungültiges Werkzeug.');
  if (!full) return { board };
  const progress = input.roadmapProgress;
  require(progress && !Array.isArray(progress) && typeof progress === 'object', 'Planungsfortschritt fehlt.');
  for (const [id, done] of Object.entries(progress)) require(taskIds.includes(id) && typeof done === 'boolean', 'Unbekannter Task oder ungültiger Status.');
  const view = input.view;
  require(view && ['screens', 'architecture', 'plan'].includes(view.main) && ['system', 'flow', 'deploy'].includes(view.architectureTab) && ['k8s', 'ecs', 'local'].includes(view.deployment) && nodeIds.includes(view.architectureNode), 'Ungültiger Arbeitsbereich.');
  const draft = input.draftNote;
  require(draft && known.has(draft.screenId) && typeof draft.text === 'string', 'Ungültiger Notizentwurf.');
  return { board, roadmapProgress: structuredClone(progress), view: structuredClone(view), draftNote: structuredClone(draft) };
}
