import React, { useEffect, useState } from 'react';

/** @typedef {{id: string, repository: string, tag: string, commit: string, kind: string, manifest: {metadata: {id: string, version: string}}, controls: {id: string}[], capabilities: (string | {id: string, version: string})[]}} Pack */

/** @param {{organizationId: string, accessToken?: string}} props */
export function PackWorkspace({ organizationId, accessToken = '' }) {
  const [packs, setPacks] = useState(/** @type {Pack[]} */ ([]));
  const [selected, setSelected] = useState('');
  const [repository, setRepository] = useState('');
  const [tag, setTag] = useState('');
  const [kind, setKind] = useState('governance');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [approval, setApproval] = useState(/** @type {{revisionId: string, approved: boolean, approvedBy: string | null} | null} */ (null));
  const [approvalError, setApprovalError] = useState('');
  const currentApproval = approval?.revisionId === selected ? approval : null;
  const root = `/api/organizations/${encodeURIComponent(organizationId)}/packs`;

  /** @param {string} id */
  function selectPack(id) {
    setSelected(id);
    const url = new URL(location.href);
    url.searchParams.set('pack', id);
    history.replaceState(null, '', url);
  }

  useEffect(() => {
    const controller = new AbortController();
    fetch(root, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then((response) => { if (!response.ok) throw new Error('load failed'); return response.json(); })
      .then((/** @type {Pack[]} */ data) => {
        const requested = new URLSearchParams(location.search).get('pack');
        setPacks(data); setSelected(data.some((item) => item.id === requested) ? requested || '' : (data[0]?.id || ''));
      })
      .catch(() => { if (!controller.signal.aborted) setError('Packs konnten nicht geladen werden.'); });
    return () => controller.abort();
  }, [root, accessToken]);

  useEffect(() => {
    setApproval(null); setApprovalError('');
    if (!selected) return;
    const controller = new AbortController();
    fetch(`${root}/${encodeURIComponent(selected)}/approval`, { signal: controller.signal,
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then((response) => { if (!response.ok) throw new Error('load failed'); return response.json(); })
      .then(setApproval).catch(() => { if (!controller.signal.aborted) setApprovalError('Freigabestatus konnte nicht geladen werden.'); });
    return () => controller.abort();
  }, [root, selected, accessToken]);

  async function changeApproval() {
    if (!selected || !currentApproval) return;
    setBusy(true); setApprovalError('');
    try {
      const response = await fetch(`${root}/${encodeURIComponent(selected)}/approval`, {
        method: currentApproval.approved ? 'DELETE' : 'PUT',
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
      });
      if (!response.ok) throw new Error('approval failed');
      if (currentApproval.approved) setApproval({ revisionId: selected, approved: false, approvedBy: null });
      else setApproval(await response.json());
    } catch { setApprovalError('Freigabe konnte nicht geändert werden. Nur Organisationsinhaber dürfen freigeben.'); }
    finally { setBusy(false); }
  }

  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function connect(event) {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const response = await fetch(root, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
        body: JSON.stringify({ repository: repository.trim(), tag: tag.trim(), kind }),
      });
      if (!response.ok) throw new Error(response.status === 409 ? 'Der Tag wurde verschoben; der gespeicherte Commit bleibt unverändert.' : 'Pack konnte nicht verbunden werden.');
      /** @type {Pack} */ const pack = await response.json();
      setPacks((current) => [...current.filter((item) => item.id !== pack.id), pack]);
      selectPack(pack.id);
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Pack konnte nicht verbunden werden.'); }
    finally { setBusy(false); }
  }

  const detail = packs.find((pack) => pack.id === selected);
  return <section aria-labelledby="packs-heading" className="workspace">
    <div className="workspace-heading"><div><p className="eyebrow">GOVERNANCE</p><h2 id="packs-heading">Pack-Katalog</h2></div>
      <p>Versionierte Manifeste und ihre Herkunft.</p></div>
    {error && <p role="alert" className="alert">{error}</p>}
    <div className="workspace-grid">
      <div className="panel">
        <h3>Packs</h3>
        {packs.length === 0 && <p>Noch keine Packs verbunden.</p>}
        <ul className="team-list">{packs.map((pack) => <li key={pack.id}><button className="team-choice" type="button" disabled={busy} aria-pressed={pack.id === selected} onClick={() => selectPack(pack.id)}>{pack.manifest.metadata.id} · {pack.tag}</button></li>)}</ul>
        <form onSubmit={connect}>
          <label className="field">Repository<input required maxLength={200} value={repository} onChange={(event) => setRepository(event.target.value)} placeholder="owner/repository" /></label>
          <label className="field">Release-Tag<input required maxLength={200} value={tag} onChange={(event) => setTag(event.target.value)} placeholder="v1.0.0" /></label>
          <label className="field">Pack-Typ<select value={kind} onChange={(event) => setKind(event.target.value)}><option value="governance">Governance</option><option value="provider">Evidence Provider</option></select></label>
          <button type="submit" disabled={busy}>Pack verbinden</button>
        </form>
      </div>
      <div className="panel"><h3>Pack-Details</h3>{detail ? <>
        <p><strong>{detail.manifest.metadata.id}</strong> · Version {detail.manifest.metadata.version}</p>
        <p>Repository: {detail.repository}</p><p>Tag: {detail.tag}</p><p>Commit: <code>{detail.commit}</code></p>
        <p>Strukturell validiert. Eine Freigabe gilt nur für diese Revision und startet keine Collector-Ausführung.</p>
        <p>Governance-Freigaben: nur Organisationsinhaber; Agenten haben kein Freigaberecht. Git-Rechte werden separat in Git verwaltet.</p>
        {detail.kind === 'governance' && <>
          <p>Freigabestatus: {currentApproval ? (currentApproval.approved ? `Freigegeben von ${currentApproval.approvedBy}` : 'Nicht freigegeben') : 'Wird geladen …'}</p>
          {currentApproval && <button type="button" disabled={busy} onClick={() => { void changeApproval(); }}>{currentApproval.approved ? 'Freigabe zurücknehmen' : 'Governance-Pack freigeben'}</button>}
        </>}
        {approvalError && <p role="alert">{approvalError}</p>}
        <h4>Kontrollen</h4>{detail.controls.length ? <ul>{detail.controls.map((control) => <li key={control.id}>{control.id}</li>)}</ul> : <p>Keine Governance-Kontrollen.</p>}
        <h4>Capabilities</h4><ul>{detail.capabilities.map((capability) => {
          const value = typeof capability === 'string' ? capability : `${capability.id}/${capability.version}`;
          return <li key={value}>{value}</li>;
        })}</ul>
      </> : <p>Wähle ein Pack aus.</p>}</div>
    </div>
  </section>;
}
