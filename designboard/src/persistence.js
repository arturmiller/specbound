const WORKSPACE_STORAGE = 'specbound-workspace-v1';
let storageProblem = false;
function workspaceSnapshot() {
  return {
    format: 'specbound-workspace', version: 1,
    board: snapshot(), roadmapProgress: clone(roadmap.done),
    draftNote: { screenId: state.selected, text: $('#note-text').value },
    view: { main: mainView, architectureTab: archTab, architectureNode: selectedArch, deployment: deployProfile },
  };
}
function persistWorkspace() {
  const label = $('#storage-status');
  try {
    localStorage.setItem(WORKSPACE_STORAGE, JSON.stringify(workspaceSnapshot()));
    storageProblem = false;
    label.textContent = 'Lokal gespeichert · keine Cloud-Synchronisierung';
    label.dataset.state = 'saved';
  } catch {
    storageProblem = true;
    label.textContent = 'Nur in dieser Sitzung · bitte Sicherung exportieren';
    label.dataset.state = 'session';
  }
}
function applyTransfer(transfer) {
  Object.assign(state, transfer.board);
  if (transfer.roadmapProgress) roadmap.done = transfer.roadmapProgress;
  if (transfer.draftNote) $('#note-text').value = transfer.draftNote.text;
  if (transfer.view) {
    archTab = transfer.view.architectureTab;
    selectedArch = transfer.view.architectureNode;
    deployProfile = transfer.view.deployment;
    changeView(transfer.view.main);
  }
}
function validateWorkspace(value) {
  return validateTransfer(value, defaults, allTasks.map(t => t.id), ARCH_NODES.map(n => n.id));
}
// Restore before the first render/save. Legacy storage keys remain readable.
try {
  const saved = localStorage.getItem(WORKSPACE_STORAGE);
  if (saved) {
    const transfer = validateWorkspace(JSON.parse(saved));
    applyTransfer(transfer);
    stored = transfer.board;
  }
} catch {
  storageProblem = true;
  notice('Gespeicherter Zustand nicht lesbar. Bitte vorhandene Sicherung prüfen.');
}
$('#export-workspace').addEventListener('click', () => {
  downloadArtifact('specbound-workspace.json', workspaceSnapshot());
  notice('Sicherung enthält Board, Notizen, Notizentwurf, Ansicht und Planungsfortschritt.');
});
// Include unplaced feedback and the same complete payload in the copied request.
$('#copy-brief').onclick = async () => {
  const text = [
    'Bitte überarbeite das Specbound-Designboard im Repository anhand dieser Notizen.',
    'Erhalte stabile IDs, Inhalte, Positionen und nicht betroffene Interaktionen.',
    'Berücksichtige auch den noch unplatzierten Notizentwurf.',
    '', 'AKTUELLER ARBEITSSTAND (JSON):', JSON.stringify(workspaceSnapshot(), null, 2),
  ].join('\n');
  try {
    await navigator.clipboard.writeText(text);
    notice('Änderungsauftrag kopiert. Hier im Chat einfügen.');
  } catch {
    const dialog = document.createElement('dialog');
    const instructions = document.createElement('p');
    instructions.textContent = 'Bitte den markierten Änderungsauftrag kopieren und im Chat einfügen.';
    const field = document.createElement('textarea');
    field.value = text;
    field.style.cssText = 'width:70vw;height:55vh';
    const close = document.createElement('button');
    close.textContent = 'Schließen';
    close.onclick = () => { dialog.close(); dialog.remove(); };
    dialog.append(instructions, field, close);
    document.body.append(dialog);
    dialog.showModal();
    field.focus(); field.select();
  }
};
$('#import-workspace').addEventListener('click', () => $('#workspace-file').click());
$('#workspace-file').addEventListener('change', async event => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    if (file.size > 5 * 1024 * 1024) throw new Error('Die Sicherung ist größer als 5 MB.');
    const transfer = validateWorkspace(JSON.parse(await file.text()));
    if (!window.confirm('Lokalen Arbeitsstand durch diese Sicherung ersetzen? Exportiere bei Bedarf zuerst eine Sicherung.')) return;
    applyTransfer(transfer);
    past = []; future = [];
    rerender();
    if (mainView === 'plan') renderRoadmap();
    notice('Sicherung importiert.');
  } catch (error) {
    notice(`Import abgebrochen: ${error.message}`);
  } finally { event.target.value = ''; }
});
$('#note-text').addEventListener('input', save);
$('#view-mode').addEventListener('change', save);
$('#architecture-surface').addEventListener('click', save);
$('#architecture-surface').addEventListener('keydown', save);
$('#deploy-target').addEventListener('change', save);
window.addEventListener('pagehide', () => { if (!storageProblem) save(); });
