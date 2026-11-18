import React, { useEffect, useRef, useState } from 'react';
import { ManifestProvenance } from './manifest-source.jsx';

/** @typedef {{before: import('./resources.jsx').Resource, candidate: import('./resources.jsx').Resource, reviewDigest: string, changes: {path: string, change: string, before: unknown, after: unknown}[], references: {resources: {revisionId: string, resourceType: string, name: string, version: string, productId?: string | null}[], currentProducts: {productId: string, revisionId: string}[]}}} RevisionCheck */
/** @typedef {{id: string, actorId: string, occurredAt: string, details: {previousRevisionId: string, revisionId: string, previousCommit: string, commit: string}}} Adoption */

/** @param {{organizationId: string, revisionId: string, accessToken: string, isOwner?: boolean}} props */
export function ResourceRevisions({ organizationId, revisionId, accessToken, isOwner = false }) {
  const scope = `${organizationId}:${revisionId}:${accessToken}`;
  const root = `/api/organizations/${encodeURIComponent(organizationId)}/resources/${encodeURIComponent(revisionId)}`;
  const [state, setState] = useState(/** @type {{scope: string, resource: import('./resources.jsx').Resource | null, history: Adoption[], error: string} | null} */ (null));
  const [ref, setRef] = useState(/** @type {string | null} */ (null));
  const [refType, setRefType] = useState('');
  const [checked, setChecked] = useState(/** @type {{key: string, value: RevisionCheck} | null} */ (null));
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const controller = useRef(/** @type {AbortController | null} */ (null));
  const value = state?.scope === scope ? state : null;
  const resource = value?.resource;
  const key = JSON.stringify([scope, ref, refType]);
  const check = checked?.key === key ? checked.value : null;

  useEffect(() => {
    const current = new AbortController();
    /** @type {RequestInit} */ const options = { signal: current.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} };
    Promise.all([fetch(root, options), fetch(`${root}/adoptions`, options)]).then(async ([revision, events]) => {
      if (revision.status === 404) { if (!current.signal.aborted) setState({ scope, resource: null, history: [], error: '' }); return; }
      if (!revision.ok || !events.ok) throw new Error('Revision und Übernahmeprotokoll konnten nicht geladen werden.');
      const [item, history] = await Promise.all([revision.json(), events.json()]);
      if (!current.signal.aborted) setState({ scope, resource: item, history, error: '' });
    }).catch((failure) => { if (!current.signal.aborted) setState({ scope, resource: null, history: [], error: failure.message }); });
    return () => { current.abort(); controller.current?.abort(); };
  }, [root, accessToken, scope]);

  /** @param {boolean} adopt */
  async function submit(adopt) {
    if (!isOwner || !resource || (adopt && !check)) return;
    controller.current?.abort();
    const current = new AbortController(); controller.current = current;
    setBusy(true); setError('');
    const data = { ref: ref?.trim() ?? resource.source.ref, refType: refType || resource.source.refType, ...(adopt && check ? { commit: check.candidate.source.commit, reviewDigest: check.reviewDigest } : {}) };
    if (!adopt) setChecked(null);
    try {
      const response = await fetch(`${root}/${adopt ? 'adopt' : 'check'}`, { method: 'POST', signal: current.signal, headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) }, body: JSON.stringify(data) });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(`${response.status === 409 ? 'Quelle, Identität oder geltender Stand hat sich geändert. Bitte erneut prüfen.' : response.status === 403 ? 'Für die Übernahme fehlen die erforderlichen Rechte.' : 'Die neue Revision oder ihre Referenzen sind ungültig oder nicht verfügbar.'}${typeof body.detail === 'string' ? ` ${body.detail}` : ''} Der bisherige Stand bleibt erhalten.`);
      }
      const result = await response.json();
      if (current.signal.aborted) return;
      if (!adopt) setChecked({ key, value: result });
      else {
        const url = new URL(location.href);
        if (resource.resourceType !== 'Product') url.searchParams.set(resource.resourceType === 'EvidenceProviderPack' ? 'pack' : 'resource', result.id);
        location.assign(`${url.pathname}${url.search}${url.hash}`);
      }
    } catch (failure) { if (!current.signal.aborted) setError(failure instanceof Error ? failure.message : 'Die Revision konnte nicht verarbeitet werden.'); }
    finally { if (!current.signal.aborted) setBusy(false); }
  }

  if (!value) return <p role="status">Ressourcenrevision wird geladen …</p>;
  if (value.error) return <p role="alert">{value.error}</p>;
  if (!resource) return <p>Für diese ältere Quelle liegt keine native Ressourcenregistrierung vor.</p>;
  return <section aria-label="Ressourcenrevision" className="panel resource-revisions"><h2>Revision prüfen und übernehmen</h2>
    {error && <p role="alert">{error}</p>}
    {isOwner ? <form onSubmit={(event) => { event.preventDefault(); void submit(false); }}>
      <p>Quelle: {resource.source.repository} · {resource.source.manifestPath}. Die erwartete Ressourcen-ID bleibt {resource.resourceId}; die neue Version wird aus dem Manifest gelesen.</p>
      <div className="resource-source-form"><label className="field">Gewünschter Git-Ref<input value={ref ?? resource.source.ref} onChange={(event) => setRef(event.target.value)} required maxLength={200} disabled={busy} /></label><label className="field">Ref-Typ der neuen Revision<select value={refType || resource.source.refType} onChange={(event) => setRefType(event.target.value)} disabled={busy}><option value="branch">Branch</option><option value="tag">Release-Tag</option><option value="commit">Commit</option></select></label></div>
      <button type="submit" disabled={busy}>Neue Revision prüfen</button>
    </form> : <p>Nur Organisationseigentümer können Ressourcenrevisionen prüfen und übernehmen.</p>}
    {busy && <p role="status">Revision wird erneut gelesen und validiert …</p>}
    {check && <section aria-label="Revisionsvergleich"><h3>Struktur und Referenzen gültig</h3><h4>Bisher · {check.before.version}</h4><ManifestProvenance source={check.before.source} defaultPath={check.before.source.manifestPath} /><h4>Neu · {check.candidate.version}</h4><ManifestProvenance source={check.candidate.source} defaultPath={check.candidate.source.manifestPath} />
      {check.candidate.resourceType !== 'EvidenceProviderPack' ? <><p className="break-value">Controls bisher: {check.before.resolved.controls.map((item) => item.id).join(', ') || 'Keine'}</p><p className="break-value">Controls neu: {check.candidate.resolved.controls.map((item) => item.id).join(', ') || 'Keine'}</p></> : <><p>Capabilities bisher: {check.before.resolved.capabilities?.map((item) => `${item.id}/${item.version}`).join(', ')}</p><p>Capabilities neu: {check.candidate.resolved.capabilities?.map((item) => `${item.id}/${item.version}`).join(', ')}</p></>}
      <details><summary>Änderungen an Manifest, Parametern und Verträgen ({check.changes.length})</summary>{check.changes.length ? check.changes.map((item) => <div key={item.path}><h4 className="break-value">{item.path}</h4><p>Bisher</p><pre className="pack-json">{JSON.stringify(item.before, null, 2)}</pre><p>Neu</p><pre className="pack-json">{JSON.stringify(item.after, null, 2)}</pre></div>) : <p>Keine inhaltlichen Änderungen.</p>}</details>
      <h4>Gespeicherte Referenzen auf den bisherigen Stand</h4><ul>{check.references.resources.map((item) => <li key={item.revisionId}>{item.resourceType === 'Product' ? <>{item.name} · {item.version} (fest referenziert){item.productId && <> · <a href={`/products?${new URLSearchParams({ product: item.productId, view: 'scope' })}`}>Aktuelles Produkt öffnen</a></>}</> : <a href={`${item.resourceType === 'Profile' ? '/profiles' : '/catalogs'}?${new URLSearchParams({ resource: item.revisionId })}`}>{item.name} · {item.version} (fest referenziert)</a>}</li>)}{check.references.currentProducts.map((item) => <li key={item.productId}><a href={`/products?${new URLSearchParams({ product: item.productId, view: 'scope' })}`}>Aktuelles Produkt {item.productId}</a></li>)}</ul>
      {!check.references.resources.length && !check.references.currentProducts.length && <p>Keine gespeicherten direkten Referenzen.</p>}
      <p>Bewertungsfolgen wurden nicht berechnet. Gespeicherte Assessments und bestehende Profilreferenzen bleiben unverändert. Eine Produktübernahme gilt für künftig gestartete Prüfungen und aktualisiert seine Quellen; bereits gestartete Prüfungen behalten ihre Konfiguration. Die Übernahme erteilt keine Ausführungsfreigabe.</p>
      <p>Weiterführende Planung: <a href="https://github.com/arturmiller/specbound/issues/65">Deployment-Identität</a> · <a href="https://github.com/arturmiller/specbound/issues/66">Baseline</a> · <a href="https://github.com/arturmiller/specbound/issues/67">Regeländerungssimulation</a> · <a href="https://github.com/arturmiller/specbound/issues/68">Aktivierung und Reassessment</a></p>
      <button type="button" disabled={busy} onClick={() => { void submit(true); }}>Revision übernehmen</button>
    </section>}
    <details><summary>Übernahmeprotokoll ({value.history.length})</summary>{value.history.length ? <ul>{value.history.map((event) => <li key={event.id} className="break-value">{event.occurredAt} · {event.actorId} · <a href={`https://github.com/${resource.source.repository}/commit/${event.details.previousCommit}`}>{event.details.previousCommit.slice(0, 12)}</a> → <a href={`https://github.com/${resource.source.repository}/commit/${event.details.commit}`}>{event.details.commit.slice(0, 12)}</a></li>)}</ul> : <p>Noch keine Übernahme protokolliert.</p>}</details>
  </section>;
}
