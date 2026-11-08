import React, { useEffect, useState } from 'react';
import { evidenceFreshness } from './evidence-freshness.js';
import { EvidenceInspection } from './evidence-inspection.jsx';

/** @typedef {{id: string, productId: string, subjectId: string, capability: string, environment: string, targetRevision: string, collectorRevision: string, collectorImage: string, provenance: {sourceRef?: string}, value: unknown, observedAt: string, expiresAt: string, ttlSeconds: number}} Evidence */
/** @typedef {{id: string, name: string}} Product */
/** @typedef {{items: Evidence[], nextOffset: number | null}} Page */
const PAGE_SIZE = 10;

/** @param {string} org @param {number} offset @param {string} [id] */
function evidenceUrl(org, offset, id = '') {
  const params = new URLSearchParams({ organization: org });
  if (offset) params.set('offset', String(offset));
  if (id) params.set('evidence', id);
  return `/evidence?${params}`;
}

/** @param {{organizationId: string, accessToken?: string}} props */
export function EvidenceRegistry({ organizationId, accessToken = '' }) {
  const params = new URLSearchParams(window.location.search);
  const evidenceId = params.get('evidence') || '';
  const view = params.get('view') || '';
  const assessmentId = params.get('assessment') || '';
  const findingId = params.get('finding') || '';
  const rawOffset = Number(params.get('offset') || 0);
  const offset = Number.isSafeInteger(rawOffset) && rawOffset >= 0 ? rawOffset : 0;
  const [page, setPage] = useState(/** @type {Page | null} */ (null));
  const [item, setItem] = useState(/** @type {Evidence | null} */ (null));
  const [products, setProducts] = useState(/** @type {Product[]} */ ([]));
  const [error, setError] = useState('');
  const [now, setNow] = useState(Date.now());
  const root = `/api/organizations/${encodeURIComponent(organizationId)}/evidence`;

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    /** @type {Record<string, string>} */
    const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
    const path = evidenceId ? `${root}/${encodeURIComponent(evidenceId)}` : `${root}?${new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) })}`;
    fetch(path, { signal: controller.signal, headers })
      .then((response) => { if (!response.ok) throw new Error(response.status === 403 ? 'Für diese Evidence fehlen die erforderlichen Rechte.' : response.status === 404 ? 'Evidence nicht gefunden oder nicht sichtbar.' : 'Evidence konnte nicht geladen werden.'); return response.json(); })
      .then(evidenceId ? setItem : setPage)
      .catch((failure) => { if (!controller.signal.aborted) setError(failure.message); });
    fetch(`/api/organizations/${encodeURIComponent(organizationId)}/products`, { signal: controller.signal, headers })
      .then((response) => response.ok ? response.json() : []).then(setProducts).catch(() => {});
    return () => controller.abort();
  }, [root, evidenceId, offset, organizationId, accessToken]);

  /** @param {string} id */
  function productName(id) { return products.find((product) => product.id === id)?.name || id; }
  return <section className="evidence-screen" aria-labelledby="evidence-heading">
    {error ? <p role="alert" className="alert">{error}</p> : evidenceId ? !item ? <p role="status">Evidence wird geladen …</p> : view === 'detail' ? <EvidenceInspection item={item} organizationId={organizationId} productName={productName(item.productId)} accessToken={accessToken} assessmentId={assessmentId} findingId={findingId} now={now} /> : <>
      <p className="eyebrow">EVIDENCE / OBSERVATION</p><div className="page-heading"><div><h1 id="evidence-heading">Gespeicherte Observation</h1><p>Scope, Herkunft und zeitliche Gültigkeit der gespeicherten Evidence.</p></div><span className="team-role">{evidenceFreshness(item, now)}</span></div>
      <div className="discovery-columns"><div className="panel"><h2>Evidence · {item.id}</h2><pre className="provider-code">{JSON.stringify({ subjectId: item.subjectId, capability: item.capability, value: item.value, observedAt: item.observedAt, expiresAt: item.expiresAt, provenance: item.provenance }, null, 2)}</pre></div>
        <div className="discovery-side"><div className="panel"><h2>Scope und Herkunft</h2><dl className="team-role-list evidence-details"><div><dt>Produkt</dt><dd>{productName(item.productId)}</dd></div><div><dt>Umgebung</dt><dd>{item.environment}</dd></div><div><dt>Produktrevision</dt><dd>{item.targetRevision}</dd></div><div><dt>Provider-/Packrevision</dt><dd>{item.collectorRevision}</dd></div><div><dt>Collector-Image</dt><dd>{item.collectorImage}</dd></div><div><dt>Quelle</dt><dd>{item.provenance?.sourceRef || 'UNKNOWN'}</dd></div><div><dt>Gültig bis</dt><dd>{item.expiresAt}</dd></div></dl><div className="team-info">Zeitliche Gültigkeit allein bestätigt weder Vertrauen noch die inhaltliche Richtigkeit. Eine Provider-ID ist in diesem Datensatz nicht gespeichert.</div></div>
          <div className="panel"><h2>Verwendung</h2><p>Ein Bezug zu konkreten Bewertungen wird hier nicht angenommen. Assessment-Berichte zeigen ihre tatsächlich verknüpfte Evidence.</p></div></div></div>
      <a className="team-back" href={evidenceUrl(organizationId, offset)}>← Zurück zum Evidence-Register</a>
    </> : !page ? <p role="status">Evidence wird geladen …</p> : <>
      <p className="eyebrow">PLATTFORM / EVIDENCE</p><div className="page-heading"><div><h1 id="evidence-heading">Evidence-Register</h1><p>Gespeicherte Observationen mit Scope, Herkunft und Frische.</p></div><a className="primary-link" href={`/providers?${new URLSearchParams({ organization: organizationId })}`}>Provider-Verzeichnis →</a></div>
      <div className="panel team-table-panel"><h2>Observationen</h2>{page.items.length === 0 ? <p className="product-empty">Keine Evidence auf dieser Seite vorhanden. Evidenzlage: UNKNOWN.</p> : <><p className="pack-scroll-hint">Tabelle horizontal scrollen, um alle Spalten zu sehen.</p><div className="team-table-scroll" tabIndex={0} aria-label="Evidence, horizontal scrollbar"><table className="team-table"><thead><tr><th>EVIDENCE</th><th>PRODUKT / SUBJECT</th><th>CAPABILITY</th><th>BEOBACHTET</th><th>FRISCHE</th></tr></thead><tbody>{page.items.map((record) => <tr key={record.id}><td><a href={evidenceUrl(organizationId, offset, record.id)}>{record.id}</a></td><td>{productName(record.productId)}<small>{record.subjectId}</small></td><td>{record.capability}</td><td>{record.observedAt}</td><td>{evidenceFreshness(record, now)}</td></tr>)}</tbody></table></div></>}</div>
      <div className="evidence-pages">{offset > 0 && <a className="team-back" href={evidenceUrl(organizationId, Math.max(0, offset - PAGE_SIZE))}>← Vorherige Seite</a>}{page.nextOffset !== null && <a className="primary-link" href={evidenceUrl(organizationId, page.nextOffset)}>Nächste Seite →</a>}</div>
      <div className="team-info">Abgelaufene oder nicht bestimmbar datierte Evidence ist UNKNOWN. Ergebnisse behalten ihre konkreten Produkt- und Collector-Revisionen.</div>
    </>}
  </section>;
}
