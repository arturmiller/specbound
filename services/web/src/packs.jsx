import React, { useEffect, useState } from 'react';
import { GovernancePlans } from './governance-plans.jsx';

/** @typedef {{id: string, description?: string, target?: {kind?: string}, requiredEvidence?: {capability?: string}, assertions?: unknown[]}} Control */
/** @typedef {{id: string, repository: string, tag: string, commit: string, kind: string, manifest: {metadata: {id: string, version: string}}, controls: Control[], capabilities: (string | {id: string, version: string})[]}} Pack */
/** @typedef {{revisionId: string, approved: boolean, approvedBy: string | null, approvedAt?: string | null}} Approval */
/** @typedef {{id: string, ownerPrincipalId?: string}} Organization */

/** @param {string} org @param {string} [pack] @param {string} [view] */
function packUrl(org, pack = '', view = '') {
  const params = new URLSearchParams({ organization: org });
  if (pack) params.set('pack', pack);
  if (view) params.set('view', view);
  return `/packs?${params}`;
}

/** @param {{organizationId: string, organization?: Organization, accessToken?: string, onBusyChange: (busy: boolean) => void}} props */
export function PackWorkspace({ organizationId, organization, accessToken = '', onBusyChange }) {
  const params = new URLSearchParams(window.location.search);
  const selected = params.get('pack') || '';
  const view = params.get('view') || (selected ? 'detail' : 'list');
  const [packs, setPacks] = useState(/** @type {Pack[]} */ ([]));
  const [loading, setLoading] = useState(true);
  const [repository, setRepository] = useState('');
  const [tag, setTag] = useState('');
  const [kind, setKind] = useState('governance');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [principal, setPrincipal] = useState(/** @type {{id: string, kind: string} | null} */ (null));
  const [permissionError, setPermissionError] = useState('');
  const [approval, setApproval] = useState(/** @type {Approval | null} */ (null));
  const [approvalError, setApprovalError] = useState('');
  const [search, setSearch] = useState('');
  const [controlId, setControlId] = useState('');
  const root = `/api/organizations/${encodeURIComponent(organizationId)}/packs`;
  /** @type {Record<string, string>} */
  const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
  const isOwner = Boolean(principal?.kind === 'user' && principal.id === organization?.ownerPrincipalId);
  const detail = packs.find((pack) => pack.id === selected);
  const control = detail?.controls.find((item) => item.id === controlId) || detail?.controls[0];
  const listUrl = packUrl(organizationId);
  const currentApproval = approval?.revisionId === selected ? approval : null;

  useEffect(() => { onBusyChange(busy); return () => onBusyChange(false); }, [busy, onBusyChange]);

  useEffect(() => {
    const controller = new AbortController();
    fetch(root, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then((response) => { if (!response.ok) throw new Error(response.status === 403 ? 'Für diese Packs fehlen die erforderlichen Rechte.' : 'Packs konnten nicht geladen werden.'); return response.json(); })
      .then(setPacks).catch((failure) => { if (!controller.signal.aborted) setError(failure.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    fetch('/api/auth/me', { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then((response) => { if (!response.ok) throw new Error(); return response.json(); })
      .then(setPrincipal).catch(() => { if (!controller.signal.aborted) setPermissionError('Berechtigungen konnten nicht geladen werden.'); });
    return () => controller.abort();
  }, [root, accessToken]);

  useEffect(() => {
    setApproval(null); setApprovalError('');
    if (!selected || detail?.kind !== 'governance') return;
    const controller = new AbortController();
    fetch(`${root}/${encodeURIComponent(selected)}/approval`, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then((response) => { if (!response.ok) throw new Error(); return response.json(); })
      .then(setApproval).catch(() => { if (!controller.signal.aborted) setApprovalError('Freigabestatus konnte nicht geladen werden.'); });
    return () => controller.abort();
  }, [root, selected, detail?.kind, accessToken]);

  async function changeApproval() {
    if (!isOwner || !selected || !currentApproval) return;
    setBusy(true); setApprovalError('');
    try {
      const response = await fetch(`${root}/${encodeURIComponent(selected)}/approval`, { method: currentApproval.approved ? 'DELETE' : 'PUT', headers });
      if (!response.ok) throw new Error(response.status === 403 ? 'Für die Freigabe fehlen die erforderlichen Rechte.' : 'Freigabe konnte nicht geändert werden.');
      if (currentApproval.approved) setApproval({ revisionId: selected, approved: false, approvedBy: null });
      else setApproval(await response.json());
    } catch (failure) { setApprovalError(failure instanceof Error ? failure.message : 'Freigabe konnte nicht geändert werden.'); }
    finally { setBusy(false); }
  }

  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function connect(event) {
    event.preventDefault();
    if (!isOwner || !repository.trim() || !tag.trim()) return;
    setBusy(true); setError('');
    try {
      const response = await fetch(root, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify({ repository: repository.trim(), tag: tag.trim(), kind }) });
      if (!response.ok) {
        const messages = { 403: 'Für diese Aktion fehlen die erforderlichen Rechte.', 409: 'Der Tag wurde verschoben oder gehört zu einem anderen Pack-Typ; der gespeicherte Commit bleibt unverändert.', 422: 'Pack-Manifest oder Repository ist ungültig.', 503: 'Die Git-Quelle ist nicht verfügbar oder nicht konfiguriert.' };
        throw new Error(messages[/** @type {403 | 409 | 422 | 503} */ (response.status)] || 'Pack konnte nicht verbunden werden.');
      }
      /** @type {Pack} */ const pack = await response.json();
      window.location.assign(pack.kind === 'provider' ? `/providers?${new URLSearchParams({ organization: organizationId, pack: pack.id })}` : packUrl(organizationId, pack.id));
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Pack konnte nicht verbunden werden.'); setBusy(false); }
  }

  const visible = packs.filter((pack) => `${pack.manifest.metadata.id} ${pack.repository} ${pack.tag}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  return <section className="packs-screen" aria-labelledby="packs-heading">
    {error && <p role="alert" className="alert">{error}</p>}{permissionError && <p role="alert" className="alert">{permissionError}</p>}
    {loading ? <p role="status">Packs werden geladen …</p> : error && view !== 'connect' ? null : view === 'list' ? <>
      <p className="eyebrow">GOVERNANCE / QUELLEN</p><div className="page-heading"><div><h1 id="packs-heading">Pack-Katalog</h1><p>Versionierte Packs und ihre geprüfte Git-Herkunft.</p></div><div><a className="team-back" href={packUrl(organizationId, '', 'releases')}>Governance-Releases →</a>{' '}{isOwner && <a className="primary-link" href={packUrl(organizationId, '', 'connect')}>+ Repository verbinden</a>}</div></div>
      <div className="product-filters"><label>Packs suchen<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} /></label></div>
      <div className="panel team-table-panel"><h2>Verbundene Packs</h2>{packs.length === 0 ? <p className="product-empty">Noch keine Packs verbunden.</p> : visible.length === 0 ? <p className="product-empty">Keine Packs für diese Suche.</p> : <div className="team-table-scroll"><table className="team-table"><thead><tr><th>PACK</th><th>GIT-REPOSITORY</th><th>RELEASE-TAG</th><th>KONTROLLEN</th><th>VALIDIERUNG</th></tr></thead><tbody>{visible.map((pack) => <tr key={pack.id}><td><a href={pack.kind === 'provider' ? `/providers?${new URLSearchParams({ organization: organizationId, pack: pack.id })}` : packUrl(organizationId, pack.id)}>{pack.manifest.metadata.id}</a><small>{pack.kind}</small></td><td className="break-value">{pack.repository}</td><td>{pack.tag}</td><td>{pack.controls.length}</td><td>Strukturell validiert</td></tr>)}</tbody></table></div>}</div>
    </> : view === 'connect' ? <>
      <p className="eyebrow">PACKS / REPOSITORY VERBINDEN</p><div className="page-heading"><div><h1 id="packs-heading">Pack verbinden</h1><p>Git-Repository und Release-Tag auswählen und validieren.</p></div></div>
      <ol className="team-steps" aria-label="Pack-Verbindung"><li aria-current="step"><span>1</span>Quelle auswählen</li><li><span>2</span>Revision prüfen</li><li><span>3</span>Freigabe</li></ol>
      <div className="team-columns"><div className="panel"><h2>Pack-Quelle</h2>{isOwner ? <form onSubmit={connect}><label className="field">Repository<input required maxLength={200} value={repository} onChange={(event) => setRepository(event.target.value)} placeholder="owner/repository" /></label><label className="field">Release-Tag<input required maxLength={200} value={tag} onChange={(event) => setTag(event.target.value)} placeholder="v1.0.0" /></label><label className="field">Pack-Typ<select aria-label="Pack-Typ" value={kind} onChange={(event) => setKind(event.target.value)}><option value="governance">Governance</option><option value="provider">Evidence Provider</option></select></label><button type="submit" disabled={busy}>Pack verbinden</button></form> : <p>Nur Organisationseigentümer können ein Pack verbinden.</p>}</div>
        <div className="panel"><h2>Integrität des Release</h2><p>Der Tag wird beim Verbinden auf einen Commit aufgelöst; ein später verschobener Tag ersetzt den gespeicherten Commit nicht.</p><div className="team-info">Manifest und Packstruktur werden vor dem Speichern validiert. Signatur und Tag-Schutz werden hier nicht geprüft.</div><p>Eine menschliche Freigabe aktiviert das Pack nicht und startet keine Collector-Ausführung.</p></div></div><a className="team-back" href={listUrl}>← Zurück zum Katalog</a>
    </> : ['releases', 'impact', 'activation', 'baseline-impact'].includes(view) ? <GovernancePlans organizationId={organizationId} packs={packs} selected={selected} view={view} /> : !detail ? <><h1 id="packs-heading">Pack nicht verfügbar</h1><p>Die Revision existiert nicht oder ist für dich nicht sichtbar.</p><a href={listUrl}>Zum Pack-Katalog</a></> : <>
      <p className="eyebrow">PACKS / REVISION</p><div className="page-heading"><div><h1 id="packs-heading">{detail.manifest.metadata.id}</h1><p>Version {detail.manifest.metadata.version} · {detail.kind === 'governance' ? 'Governance' : 'Evidence Provider'} · strukturell validiert</p></div></div>
      <div className="pack-metrics"><div className="panel"><span>Repository</span><strong>{detail.repository}</strong></div><div className="panel"><span>Release-Tag</span><strong>{detail.tag}</strong></div><div className="panel"><span>Gepinnter Commit</span><strong>{detail.commit}</strong></div><div className="panel"><span>Freigabe</span><strong>{detail.kind !== 'governance' ? 'Nicht anwendbar' : approvalError ? 'Nicht verfügbar' : currentApproval ? currentApproval.approved ? 'Freigegeben' : 'Nicht freigegeben' : 'Wird geladen …'}</strong></div></div>
      <div className="pack-notice"><p>Strukturell validiert. Freigabe gilt nur für diese Revision; sie aktiviert kein Pack und gewährt keine Collector-Rechte.</p>
        <p>Governance-Freigaben: nur menschliche Organisationseigentümer; Agenten haben kein Freigaberecht. Git-Rechte werden separat verwaltet.</p>
        {detail.kind === 'governance' && <><p>{approvalError ? 'Freigabestatus nicht verfügbar.' : currentApproval ? currentApproval.approved ? `Freigabestatus: Freigegeben von ${currentApproval.approvedBy}` : 'Freigabestatus: Nicht freigegeben' : 'Freigabestatus wird geladen …'}</p>
          {approvalError && <p role="alert" className="alert">{approvalError}</p>}{isOwner && currentApproval && <button type="button" disabled={busy} onClick={() => { void changeApproval(); }}>{currentApproval.approved ? 'Freigabe zurücknehmen' : 'Governance-Pack freigeben'}</button>}</>}</div>
      <div className="pack-detail-columns"><div className="panel team-table-panel"><h2>Kontrollen</h2>{detail.controls.length ? <><p className="pack-scroll-hint">Tabelle horizontal scrollen, um alle Spalten zu sehen.</p><div className="team-table-scroll" tabIndex={0} aria-label="Kontrollen, horizontal scrollbar"><table className="team-table"><thead><tr><th>CONTROL</th><th>ZIEL</th><th>CAPABILITY</th></tr></thead><tbody>{detail.controls.map((item) => <tr key={item.id}><td><button type="button" className="pack-control-link" aria-pressed={control?.id === item.id} onClick={() => setControlId(item.id)}>{item.id}</button></td><td>{item.target?.kind || 'Nicht angegeben'}</td><td>{item.requiredEvidence?.capability || 'Nicht angegeben'}</td></tr>)}</tbody></table></div></> : <p className="product-empty">Keine Governance-Kontrollen.</p>}</div>
        <div className="panel"><h2>{control?.id || 'Control-Herkunft'}</h2>{control ? <><p>Quelle: {detail.repository} · Tag {detail.tag}</p><p className="break-value">Commit: {detail.commit}</p><p>Ziel: {control.target?.kind || 'Nicht angegeben'}</p><p>Evidence: {control.requiredEvidence?.capability || 'Nicht angegeben'}</p><details><summary>Control-Daten</summary><pre className="pack-json">{JSON.stringify(control, null, 2)}</pre></details></> : <p>Keine Control ausgewählt.</p>}</div></div>
      <details className="panel pack-manifest"><summary>Manifest und Capabilities</summary><pre className="pack-json">{JSON.stringify(detail.manifest, null, 2)}</pre><ul>{detail.capabilities.map((capability) => { const value = typeof capability === 'string' ? capability : `${capability.id}/${capability.version}`; return <li key={value}>{value}</li>; })}</ul></details>
      {detail.kind === 'governance' && <a className="primary-link" href={packUrl(organizationId, detail.id, 'impact')}>Auswirkung und Aktivierung ansehen →</a>}{' '}
      <a className="team-back" href={listUrl}>← Zurück zum Katalog</a>
    </>}
  </section>;
}
