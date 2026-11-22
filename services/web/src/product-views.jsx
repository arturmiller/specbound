import React, { useEffect, useState } from 'react';
import { RequirementParts } from './resources.jsx';
import { ProductGovernance } from './product-governance.jsx';
import { PublicLicenseScans } from './public-license-scans.jsx';
import { ManifestProvenance } from './manifest-source.jsx';
import { ScanSource } from './assessment-governance.jsx';
import { RunList, resultBadge, runDate } from './run-list.jsx';

/** @typedef {{id: string, name: string, configurationStatus?: string}} Product */
/** @typedef {{id: string, status: string, reason: string, evidenceIds: string[], subject: {id: string, labels?: {name?: string, version?: string, lockfile?: string}}, control: unknown, coverage?: {status: string, revision: string | null, errors: {path: string, reason: string}[]} | null}} Evaluation */
/** @typedef {{id: string, capability: string, producerKind: string, producerScanId?: string, collectorRevision?: string, collectorImage?: string, provenance?: {sourceRef?: string}, observedAt: string, expiresAt: string, freshness: string, value: unknown}} Evidence */
/** @typedef {import('./resources.jsx').ResourceControl & {result: import('./assessment-governance.jsx').ControlResult, evaluations: Evaluation[], definitionVariants?: unknown[]}} Control */
/** @typedef {{id: string, createdAt: string, status: string, context: string, repository?: string, pullRequestNumber?: number | null, counts?: import('./run-list.jsx').EvaluationCounts | null}} RunOption */
/** @typedef {{productId: string, selectionId: string, options: RunOption[], run: {status: string, errorCode?: string, coverage?: string, reason?: string, files?: string[], unsupportedFiles?: string[]} | null, context: import('./assessment-governance.jsx').FrozenContext | null, provenanceStatus: string, groups: import('./resources.jsx').ResourceGroup[], controls: Control[], evidence: Evidence[], findings: {id: string, evaluationId: string, state: string, reason?: string}[], sourceScan: import('./assessment-governance.jsx').SourceScan | null, asOf: string}} Requirements */

/** @param {string} org @param {string} product @param {string} view @param {string} [assessment] */
export function productViewUrl(org, product, view, assessment) {
  const params = new URLSearchParams({ organization: org, product, view });
  if (assessment) params.set('assessment', assessment);
  return `/products?${params}`;
}

/** @param {unknown} value */
function sourceUrl(value) {
  if (typeof value !== 'string') return null;
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; }
}

/** @param {{evidence: Evidence, organizationId: string, productId: string}} props */
function EvidenceDetails({ evidence, organizationId, productId }) {
  const value = evidence.value && typeof evidence.value === 'object' ? /** @type {{licenseExpression?: string, artifacts?: {sourceUrl?: string, sourceKind?: string, artifactSha256?: string, metadataSha256?: string}[]}} */ (evidence.value) : {};
  const artifacts = Array.isArray(value.artifacts) ? value.artifacts.filter((item) => item && typeof item === 'object') : [];
  const url = sourceUrl(evidence.provenance?.sourceRef);
  return <article className="requirements-evidence" aria-label={`Nachweis ${evidence.id}`}>
    <p><strong>{evidence.capability}</strong> · {evidence.freshness === 'expired' ? 'Beim Abruf abgelaufen' : evidence.freshness === 'current' ? 'Beim Abruf gültig' : 'Gültigkeit unbekannt'}</p>
    {value.licenseExpression && <p>Lizenz: <strong>{value.licenseExpression}</strong></p>}
    {!value.licenseExpression && <pre className="pack-json">{JSON.stringify(evidence.value, null, 2)}</pre>}
    <p>Erhoben: {evidence.observedAt} · Ablauf: {evidence.expiresAt}</p>
    <p>Erzeuger: {evidence.producerKind === 'public-license-scan' ? 'Öffentlicher Python-Lizenzscanner' : evidence.producerKind || 'Unbekannt'}{evidence.producerScanId && <> · <a href={productViewUrl(organizationId, productId, 'requirements', `scan:${evidence.producerScanId}`)}>Erzeugenden Lauf ansehen</a></>}</p>
    <p className="break-value">Quelle: {url ? <a href={url}>{evidence.provenance?.sourceRef}</a> : evidence.provenance?.sourceRef || 'Nicht gespeichert'}</p>
    <details><summary>Wert, Integrität und technische Herkunft</summary><p className="break-value">Evidence-ID: {evidence.id}</p><pre className="pack-json">{JSON.stringify(evidence.value, null, 2)}</pre>
      {artifacts.map((artifact, index) => <div key={index} className="break-value"><p>Metadatenquelle: {sourceUrl(artifact.sourceUrl) ? <a href={sourceUrl(artifact.sourceUrl) || undefined}>{artifact.sourceUrl}</a> : 'Nicht gespeichert'} · {artifact.sourceKind}</p><p>Artefakt SHA-256: {artifact.artifactSha256 || 'Nicht gespeichert'}</p><p>Metadaten SHA-256: {artifact.metadataSha256 || 'Nicht gespeichert'}</p></div>)}
      <p className="break-value">Collector-Revision: {evidence.collectorRevision || 'Nicht gespeichert'} · Image: {evidence.collectorImage || 'Nicht gespeichert'}</p><p>Quellrepository der Collector-Revision: nicht gespeichert.</p>
    </details>
  </article>;
}


const runLabels = /** @type {Record<string, string>} */ ({ pending: 'Wartend', running: 'Wird ausgef\u00fchrt', completed: 'Abgeschlossen', failed: 'Fehlgeschlagen' });
const contextLabels = /** @type {Record<string, string>} */ ({ repository: 'Repositorypr\u00fcfung', pull_request: 'Pull Request', baseline: 'Basisstand' });

/** @param {RunOption} option */
function runLabel(option) {
  const target = option.repository || contextLabels[option.context] || 'Prüfung';
  return option.pullRequestNumber == null ? target : option.repository
    ? `${target} · PR #${option.pullRequestNumber}`
    : `PR #${option.pullRequestNumber}`;
}
/** @param {import('./resources.jsx').ResourceGroup} group @param {import('./resources.jsx').ResourceGroup[]} groups */
function groupLabel(group, groups) {
  const byKey = new Map(groups.map((item) => [item.key, item]));
  const path = [];
  /** @type {import('./resources.jsx').ResourceGroup | undefined} */ let current = group;
  for (let count = 0; current && count < groups.length; count += 1) {
    if (current.key !== '$root' || group.key === '$root') path.unshift(current.title);
    current = byKey.get(current.parent || '');
  }
  return path.join(' / ');
}

const executionLabels = /** @type {Record<string, string>} */ ({ evaluated: 'Bewertet', unsupported: 'Nicht unterstützt', not_evaluated: 'Nicht bewertet' });
const reasons = /** @type {Record<string, string>} */ ({ 'individual-evaluations': 'Gespeicherte Einzelbewertungen', 'method-not-configured': 'Keine Prüfmethode definiert', 'scanner-does-not-support-binding': 'Dieser Scanner unterstützt die Bindung nicht', 'no-evaluable-observations': 'Keine bewertbaren Beobachtungen', 'evaluation-limit': 'Bewertungsgrenze erreicht', 'no-assessment': 'Noch kein ausgewähltes Assessment', 'scan-pending': 'Prüfung wartet auf Ausführung', 'scan-running': 'Prüfung läuft', 'scan-failed': 'Prüfung fehlgeschlagen', 'scan-completed': 'Lauf ohne gespeichertes Assessment' });

/** @param {{control: Control, data: Requirements, organizationId: string, productId: string}} props */
function ControlDetails({ control, data, organizationId, productId }) {
  const profile = data.context?.profile;
  const definitionPath = profile?.resolved.catalog?.manifestPath;
  const definitionUrl = profile?.source.files.find((file) => file.path === definitionPath)?.url;
  const bindingUrl = profile?.source.files.find((file) => file.path === profile.resolved.bindingPath)?.url;
  const evidenceById = new Map(data.evidence.map((item) => [item.id, item]));
  return <>
    <RequirementParts parts={control.parts} /><p>{executionLabels[control.result.executionStatus] || control.result.executionStatus} · {reasons[control.result.reason] || control.result.reason}</p>
    <p>{control.evaluations.length} Einzelbewertungen · {control.result.evidenceIds.length} ausgewählte Nachweise</p>
    {(definitionUrl || bindingUrl) && <p>{definitionUrl && <a href={definitionUrl}>Anforderung in Git</a>}{definitionUrl && bindingUrl && ' · '}{bindingUrl && <a href={bindingUrl}>Prüfbindung in Git</a>}</p>}
    {control.parameters.length > 0 && <details><summary>Wirksame Parameter</summary><pre className="pack-json">{JSON.stringify(control.parameters, null, 2)}</pre></details>}
    <details><summary>Prüfregel und Definitionsstand</summary><pre className="pack-json">{JSON.stringify(control.definitionVariants || control.binding, null, 2)}</pre></details>
    {control.evaluations.length === 0 ? <p>Keine Einzelbewertung für dieses Control. UNKNOWN ist kein bestandener Nachweis.</p> : control.evaluations.map((evaluation) => <article className="requirements-evaluation" key={evaluation.id} aria-label={`Bewertung ${evaluation.subject.labels?.name || evaluation.subject.id}`}>
      <h4>{evaluation.subject.labels?.name || evaluation.subject.id}{evaluation.subject.labels?.version && ` · ${evaluation.subject.labels.version}`} <span className={`assessment-status status-${evaluation.status.toLowerCase()}`}>{evaluation.status}</span></h4>
      <p>Grund: {evaluation.reason}</p>
      <p className="break-value">Historische Quellabdeckung: {evaluation.coverage?.status || 'Nicht gespeichert'} · Scan-Revision: {evaluation.coverage?.revision && data.sourceScan ? <a href={`https://github.com/${data.sourceScan.repository}/commit/${evaluation.coverage.revision}`}>{evaluation.coverage.revision}</a> : evaluation.coverage?.revision || 'Nicht gespeichert'}</p>
      {evaluation.coverage?.errors?.length ? <details><summary>Abdeckungsfehler ({evaluation.coverage.errors.length})</summary><ul>{evaluation.coverage.errors.map((error, index) => <li key={index}>{error.path || 'Gesamte Quelle'} · {error.reason}</li>)}</ul></details> : null}
      {evaluation.status === 'PASS' && evaluation.coverage?.status === 'partial' && <p>Der Gesamtscan ist unvollständig. Ein partieller PASS schließt vorhandene Findings nicht.</p>}
      {data.findings.filter((finding) => finding.evaluationId === evaluation.id).map((finding) => <div key={finding.id}><p>Finding beim Prüfstand: {finding.state} · <a href={`/findings?${new URLSearchParams({ organization: organizationId, finding: finding.id })}`}>Aktuelles Finding ansehen</a></p>{finding.reason && <p>{finding.reason}</p>}</div>)}
      {evaluation.subject.labels?.lockfile && <p>Lockfile: {data.sourceScan?.sourceRevision ? <a href={`https://github.com/${data.sourceScan.repository}/blob/${data.sourceScan.sourceRevision}/${evaluation.subject.labels.lockfile.split('/').map(encodeURIComponent).join('/')}`}>{evaluation.subject.labels.lockfile}</a> : evaluation.subject.labels.lockfile}</p>}
      {evaluation.evidenceIds.length === 0 ? <p>Kein Nachweis für diese Einzelbewertung ausgewählt. Der gespeicherte Grund beschreibt fehlende oder mehrdeutige Daten.</p> : evaluation.evidenceIds.map((id) => { const evidence = evidenceById.get(id); return evidence ? <EvidenceDetails key={id} evidence={evidence} organizationId={organizationId} productId={productId} /> : <p key={id} role="alert">Referenzierter Nachweis nicht verfügbar: {id}</p>; })}
    </article>)}
  </>;
}

/** @param {{product: Product, organizationId: string, accessToken: string, view: string, canEdit: boolean, canManage?: boolean}} props */
export function ProductViews({ product, organizationId, accessToken, view, canEdit, canManage = false }) {
  const query = new URLSearchParams(location.search);
  const [selection, setSelection] = useState(query.get('assessment') || (view === 'scans' ? 'current' : ''));
  const [status, setStatus] = useState(['FAIL', 'UNKNOWN', 'PASS', 'NOT_APPLICABLE'].includes(query.get('status') || '') ? query.get('status') || 'all' : 'all');
  const [search, setSearch] = useState(query.get('search') || '');
  const [expanded, setExpanded] = useState(new Set(query.get('control') ? [query.get('control') || ''] : []));
  const identity = `${product.id}:${accessToken}`;
  const scope = `${identity}:${selection}`;
  const [state, setState] = useState(/** @type {{identity: string, scope: string, data: Requirements | null, error: string}} */ ({ identity: '', scope: '', data: null, error: '' }));
  const [sources, setSources] = useState(/** @type {{identity: string, items: {id: string, repository: string, provider: string}[], error: string}} */ ({ identity: '', items: [], error: '' }));
  const data = state.scope === scope ? state.data : null;
  const options = state.identity === identity ? state.data?.options || [] : [];

  useEffect(() => {
    if (view === 'scope') return;
    const controller = new AbortController();
    /** @type {ReturnType<typeof setTimeout> | undefined} */ let timer;
    async function load() {
      try {
        const response = await fetch(`/api/products/${encodeURIComponent(product.id)}/requirements?${new URLSearchParams({ assessment: selection })}`, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} });
        if (!response.ok) throw new Error(response.status === 404 ? 'Die gewählte Prüfung ist für dieses Produkt nicht verfügbar.' : response.status === 403 ? 'Für diese Anforderungen fehlen die erforderlichen Rechte.' : 'Anforderungen konnten nicht geladen werden.');
        /** @type {Requirements} */ const value = await response.json();
        if (value.productId !== product.id) throw new Error('Die Prüfung gehört zu einem anderen Produkt.');
        if (controller.signal.aborted) return;
        setState({ identity, scope, data: value, error: '' });
        const ids = new Set(value.controls.map((item) => item.id));
        setExpanded((current) => new Set([...current].filter((id) => ids.has(id))));
        if (view === 'requirements') { const url = new URL(location.href); url.searchParams.set('assessment', value.selectionId); history.replaceState(null, '', url); }
        if (view === 'scans' || (value.run && ['pending', 'running'].includes(value.run.status))) timer = setTimeout(load, 2500);
      } catch (failure) { if (!controller.signal.aborted) setState({ identity, scope, data: null, error: failure instanceof Error ? failure.message : 'Anforderungen nicht verfügbar.' }); }
    }
    void load();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [product.id, accessToken, selection, scope, identity, view]);

  useEffect(() => {
    if (view !== 'scans') return;
    const controller = new AbortController();
    fetch(`/api/products/${encodeURIComponent(product.id)}/repositories`, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then(async (response) => { if (!response.ok) throw new Error('Produktquellen konnten nicht geladen werden.'); return response.json(); })
      .then((items) => { if (!controller.signal.aborted) setSources({ identity, items, error: '' }); }).catch((failure) => { if (!controller.signal.aborted) setSources({ identity, items: [], error: failure.message }); });
    return () => controller.abort();
  }, [product.id, accessToken, identity, view]);

  /** @param {string} key @param {string} value */
  function updateQuery(key, value) { const url = new URL(location.href); if (value) url.searchParams.set(key, value); else url.searchParams.delete(key); history.replaceState(null, '', url); }
  const controls = data?.controls.filter((item) => (status === 'all' || item.result.status === status) && `${item.id} ${item.title} ${JSON.stringify(item.parts)}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())) || [];
  const sourceScan = data?.sourceScan;
  const currentSelection = data?.selectionId || selection || '';
  const runs = view === 'scans' ? options.map((option) => ({
    id: option.id,
    href: option.id.startsWith('scan:')
      ? productViewUrl(organizationId, product.id, 'requirements', option.id)
      : '/assessments/' + encodeURIComponent(option.id),
    label: runLabel(option),
    createdAt: option.createdAt,
    ...(option.status === 'failed'
      ? { status: 'Scan fehlgeschlagen', tone: 'fail' }
      : option.counts ? resultBadge(option.counts) : { status: runLabels[option.status] || option.status }),
  })) : [];
  return <section className="product-views" aria-labelledby="products-heading">
    <h1 id="products-heading">{product.name}</h1>
    <nav className="product-detail-nav" aria-label="Produktansichten">{[['requirements', 'Anforderungen'], ['scans', 'Prüfungen'], ['scope', 'Geltungsbereich']].map(([id, label]) => <a key={id} href={productViewUrl(organizationId, product.id, id)} aria-current={view === id ? 'page' : undefined}>{label}</a>)}</nav>
    {view === 'scope' ? <ProductGovernance canManage={canManage} key={product.id} productId={product.id} organizationId={organizationId} accessToken={accessToken} /> : view === 'scans' ? <>
      <h2>Prüfungen</h2>
      {state.scope !== scope ? <p role="status">Prüfungen werden geladen …</p> : state.error ? <p role="alert">{state.error}</p> : runs.length ? <RunList runs={runs} label="Produktprüfungen" /> : <p>Noch keine gespeicherten Prüfungen.</p>}
      {sources.identity !== identity ? <p role="status">Produktquellen werden geladen …</p> : sources.error ? <p role="alert">{sources.error}</p> : sources.items.filter((item) => item.provider.toLowerCase() === 'github').map((binding) => <PublicLicenseScans organizationId={organizationId} key={binding.id} productId={product.id} bindingId={binding.id} repository={binding.repository} accessToken={accessToken} canEdit={canEdit} profileManaged={product.configurationStatus === 'manifest_managed'} />)}
    </> : <>
      <h2>Anforderungen</h2><div className="requirements-filters">
        <label className="field">Prüfung<select aria-label="Prüfung" value={currentSelection} onChange={(event) => { setSelection(event.target.value); updateQuery('assessment', event.target.value); }}><option value="current">Aktuelle Anforderungen · ohne Prüfung</option>{options.map((item) => <option key={item.id} value={item.id}>{runLabel(item)} · {runDate(item.createdAt)} · {runLabels[item.status] || item.status}</option>)}{currentSelection && currentSelection !== 'current' && !options.some((item) => item.id === currentSelection) && <option value={currentSelection}>Gewählte Prüfung</option>}</select></label>
        <label className="field">Status<select aria-label="Status" value={status} onChange={(event) => { setStatus(event.target.value); updateQuery('status', event.target.value === 'all' ? '' : event.target.value); }}>{['all', 'FAIL', 'UNKNOWN', 'PASS', 'NOT_APPLICABLE'].map((value) => <option key={value} value={value}>{value === 'all' ? 'Alle' : value}</option>)}</select></label>
        <label className="field">Controls suchen<input type="search" value={search} onChange={(event) => { setSearch(event.target.value); updateQuery('search', event.target.value); }} /></label>
      </div>
      {state.scope !== scope ? <p role="status">Anforderungen werden geladen …</p> : state.error ? <p role="alert">{state.error} <button onClick={() => { setSelection('current'); updateQuery('assessment', 'current'); }}>Aktuelle Anforderungen anzeigen</button></p> : data && <>
        {data.context?.profile && <p>Profil: {data.context.profile.name} · {data.context.profile.version}{data.selectionId === 'current' ? ' · aktueller Konfigurationsstand' : ' · gespeicherter Prüfstand'}</p>}
        {data.run && <p role="status">Lauf: {runLabels[data.run.status] || data.run.status}{data.run.errorCode && ` · ${data.run.errorCode}`}</p>}
        {sourceScan ? <section className="panel" aria-label="Quellabdeckung"><h3>Gespeicherter Scanumfang</h3><ScanSource sourceScan={sourceScan} /></section> : data.run && <section className="panel" aria-label="Quellabdeckung"><h3>Gespeicherter Scanumfang</h3><p>Quellabdeckung: {data.run.coverage || 'Noch nicht gespeichert'}</p><p>{data.run.reason}</p>{Boolean(data.run.unsupportedFiles?.length) && <p>Nicht unterstützte Dateien: {data.run.unsupportedFiles?.join(', ')}</p>}</section>}
        {data.provenanceStatus === 'profile-unassigned' && <p>Ohne Profilzuordnung. Ein Produktmanifest legt die geltenden Controls ausdrücklich fest.</p>}
        {data.provenanceStatus === 'historical-unknown' && <p>Historische Profilgeltung und Quellzuordnung wurden nicht gespeichert. Gezeigt werden ausschließlich die damaligen Control-Definitionen der Einzelbewertungen.</p>}
        {data.provenanceStatus === 'legacy-policy' && <p>Expliziter Legacy-Beispielstand; keine Produktprofilzuordnung belegt.</p>}
        <p>{data.controls.length} Controls · {data.controls.reduce((total, item) => total + item.evaluations.length, 0)} Einzelbewertungen · {data.evidence.length} ausgewählte Nachweise</p>
        {data.context?.profile && <details className="panel"><summary>Konfiguration und Herkunft</summary>{data.context.product && <ManifestProvenance source={data.context.product.source} defaultPath={data.context.product.source.manifestPath} />}<ManifestProvenance source={data.context.profile.source} defaultPath={data.context.profile.source.manifestPath} /></details>}
        {controls.length === 0 ? data.controls.length ? <p>Keine Controls für diese Filter. <button onClick={() => { setStatus('all'); setSearch(''); updateQuery('status', ''); updateQuery('search', ''); }}>Filter zurücksetzen</button></p> : <p>Keine gespeicherten Controls für diesen Stand.</p> : data.groups.map((group) => { const items = controls.filter((control) => control.groupKey === group.key); return items.length > 0 && <section key={group.key}><h3>{groupLabel(group, data.groups)}</h3>{items.map((control) => <details key={control.id} open={expanded.has(control.id)} className="panel requirements-control" onToggle={(event) => { const open = event.currentTarget.open; setExpanded((current) => { if (current.has(control.id) === open) return current; const next = new Set(current); if (open) next.add(control.id); else next.delete(control.id); return next; }); if (open || new URLSearchParams(location.search).get('control') === control.id) updateQuery('control', open ? control.id : ''); }}><summary><strong>{control.id}</strong> · {control.title} <span className={`assessment-status status-${control.result.status.toLowerCase()}`}>{control.result.status}</span></summary>{expanded.has(control.id) && <ControlDetails control={control} data={data} organizationId={organizationId} productId={product.id} />}</details>)}</section>; })}
        <p className="requirements-asof">Gültigkeitsanzeige zum Abruf: {data.asOf}. Gespeicherte Bewertungen bleiben unverändert.</p>
      </>}
    </>}
  </section>;
}
