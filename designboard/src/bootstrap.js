renderStage();
renderSide();
updateTool();
requestAnimationFrame(() => {
  if (stored) {
    state.zoom = stored.zoom;
    state.tx = stored.tx;
    state.ty = stored.ty;
    updateTransform();
  } else if (!storageProblem) fit();
  if (!storageProblem) save();
});
