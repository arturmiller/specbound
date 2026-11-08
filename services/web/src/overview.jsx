import React, { useEffect, useState } from 'react';

/** @typedef {{id: string, name: string}} Team */
/** @typedef {{id: string, name: string, teamId: string}} Product */
/** @typedef {{id: string, repository: string, tag: string, kind: string, name: string}} Pack */
/** @typedef {{id: string, productId: string, subjectId: string, controlId: string, environment: string, status: string, snapshotId: string}} Finding */
/** @typedef {{id: string, productId: string, environment: string, context?: string, createdAt?: string, gitSha: string, counts: {PASS: number, FAIL: number, UNKNOWN: number, NOT_APPLICABLE: number}, evaluations: {status: string, reason: string}[]}} Assessment */
/** @typedef {{products: Product[], packs: Pack[], findings: Finding[], assessments: Assessment[]}} Data */
const states = /** @type {const} */ (['PASS', 'FAIL', 'UNKNOWN', 'NOT_APPLICABLE']);
const colors = { PASS: '#18b789', FAIL: '#ed7580', UNKNOWN: '#f3bd5b', NOT_APPLICABLE: '#a7b7c9' };

/** @param {{organizationId: string, teams: Team[], teamsLoading: boolean, teamsError: string, accessToken?: string}} props */
export function Overview({ organizationId, teams, teamsLoading, teamsError, accessToken = '' }) {
  const [data, setData] = useState(/** @type {Data | null} */ (null));
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [team, setTeam] = useState('');
  const [scope, setScope] = useState('');
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError('');
    fetch(`/api/organizations/${encodeURIComponent(organizationId)}/overview`, {
      signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    }).then((response) => { if (!response.ok) throw new Error(response.status === 403 ? 'Für diese Übersicht fehlen die erforderlichen Rechte.' : 'Übersicht konnte nicht geladen werden.'); return response.json(); })
      .then(setData).catch((failure) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [organizationId, accessToken, version]);

  const term = search.trim().toLocaleLowerCase();
  /** @param {...string} values */
  const matches = (...values) => values.some((value) => value.toLocaleLowerCase().includes(term));
  const products = data?.products.filter((item) => (!team || item.teamId === team) && matches(item.name, item.id)) || [];
  const teamProducts = data?.products.filter((item) => !team || item.teamId === team) || [];
  const productIds = new Set(teamProducts.map((item) => item.id));
  const findings = data?.findings.filter((item) => productIds.has(item.productId) && (!scope || item.environment === scope)
    && matches(item.controlId, item.subjectId, item.status, item.environment)) || [];
  const assessments = data?.assessments.filter((item) => productIds.has(item.productId) && (!scope || item.environment === scope)
    && (matches(item.id, item.gitSha, item.environment) || item.evaluations.some((result) => matches(result.status, result.reason)))) || [];
  const packs = data?.packs.filter((item) => matches(item.name, item.repository, item.tag, item.kind)) || [];
  const scopes = [...new Set([...(data?.findings || []), ...(data?.assessments || [])].filter((item) => productIds.has(item.productId)).map((item) => item.environment))].sort();
  const countsValid = assessments.every((item) => states.every((status) => Number.isFinite(item.counts[status]) && item.counts[status] >= 0));
  const counts = Object.fromEntries(states.map((status) => [status, assessments.reduce((sum, item) => sum + (countsValid ? item.counts[status] : 0), 0)]));
  const total = states.reduce((sum, status) => sum + counts[status], 0);
  const openFindings = findings.filter((item) => item.status.toLocaleLowerCase() === 'open');
  const history = assessments.filter((item) => item.createdAt && Number.isFinite(Date.parse(item.createdAt)))
    .sort((a, b) => Date.parse(a.createdAt || '') - Date.parse(b.createdAt || '')).slice(-6);
  const impacted = products.map((item) => ({ ...item, count: openFindings.filter((finding) => finding.productId === item.id).length })).filter((item) => item.count > 0).sort((a, b) => b.count - a.count);
  const root = `?organization=${encodeURIComponent(organizationId)}`;

  return <section className="overview-screen" aria-labelledby="overview-heading">
    <p className="eyebrow">PORTFOLIO / ÜBERSICHT</p><div className="page-heading"><div><h1 id="overview-heading">Übersicht und Suche</h1><p>Produkte, Findings und gespeicherte Assessment-Snapshots.</p></div><button type="button" onClick={() => setVersion((value) => value + 1)}>Aktualisieren</button></div>
    <div className="overview-filters"><label>Suche<input value={search} onChange={(event) => setSearch(event.target.value)} /></label><label>Teamfilter<select value={team} disabled={teamsLoading || Boolean(teamsError)} onChange={(event) => { setTeam(event.target.value); setScope(''); }}><option value="">Alle Teams</option>{teams.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Scope<select value={scope} onChange={(event) => setScope(event.target.value)}><option value="">Alle Umgebungen</option>{scopes.map((item) => <option key={item} value={item}>{item}</option>)}</select></label></div>
    {teamsError && <p role="alert" className="alert">Teamfilter nicht verfügbar. {teamsError}</p>}
    <p className="overview-note">Teamfilter gilt für Produkte, Findings und Assessments; Scope für Findings und Assessments. Packs sind organisationsweit.</p>
    {error && <p role="alert" className="alert">{error}</p>}{!data && !error && <p role="status">Übersicht wird geladen …</p>}
    {data && <>
      <div className="overview-metrics"><Metric label="Verbundene Packs" value={packs.length} /><Metric label="Passende Produkte" value={products.length} /><Metric label="Bewertungen in Snapshots" value={countsValid ? total : 'UNKNOWN'} /><Metric label="Offene Findings" value={openFindings.length} /><Metric label="UNKNOWN in Snapshots" value={!assessments.length || !countsValid ? 'Keine Daten' : counts.UNKNOWN} /></div>
      <div className="overview-charts"><div className="panel"><h2>Gespeicherte Assessment-Snapshots</h2><p>Jeder Punkt ist ein Snapshot; die Scopes können sich unterscheiden. Abstände sind kein Zeitmaß.</p>{!countsValid ? <p>Bewertungszahlen sind unvollständig: UNKNOWN.</p> : history.length ? <HistoryChart history={history} /> : <p>Keine zeitlich zuordenbaren Assessments vorhanden.</p>}</div>
        <div className="panel"><h2>Verteilung der Bewertungen</h2><p>Summe der passenden historischen Snapshots, kein aktuelles Produkturteil.</p>{!countsValid ? <p>Bewertungszahlen sind unvollständig: UNKNOWN.</p> : total ? <Distribution counts={counts} total={total} /> : <p>Keine Bewertungen vorhanden. Gesamtzustand: UNKNOWN.</p>}</div></div>
      <div className="overview-panels"><div className="panel"><h2>Produkte mit offenen Findings</h2>{impacted.length ? <ul>{impacted.map((item) => <li key={item.id}><a href={`/products${root}&product=${encodeURIComponent(item.id)}`}>{item.name}</a><span>{item.count} offen</span></li>)}</ul> : <p>Keine passenden offenen Findings.</p>}<a href={`/products${root}`}>Produkte ansehen →</a></div>
        <div className="panel"><h2>Verbundene Packs</h2><p>Organisationsweit; nicht nach Team oder Umgebung zugeordnet.</p>{packs.length ? <ul>{packs.map((item) => <li key={item.id}><a href={`${item.kind === 'provider' ? '/providers' : '/packs'}${root}&pack=${encodeURIComponent(item.id)}`}>{item.name} · {item.tag}</a></li>)}</ul> : <p>Keine passenden Packs.</p>}</div>
        <div className="panel"><h2>Findings</h2>{findings.length ? <ul>{findings.map((item) => <li key={item.id}><a href={`/findings?${new URLSearchParams({ organization: organizationId, finding: item.id })}`}>{item.controlId} · {item.status} · {item.environment}</a></li>)}</ul> : <p>Keine passenden Findings.</p>}</div></div>
      <div className="overview-panels overview-results"><div className="panel"><h2>Produkte</h2>{products.length ? <ul>{products.map((item) => <li key={item.id}><a href={`/products${root}&product=${encodeURIComponent(item.id)}#products-heading`}>{item.name}</a></li>)}</ul> : <p>Keine passenden Produkte.</p>}</div>
        <div className="panel"><h2>Assessments</h2><p>Gespeicherte historische Stände.</p>{assessments.length ? <ul>{assessments.map((item) => <li key={item.id}><div><a href={`/assessments/${encodeURIComponent(item.id)}`}>{item.environment} · {item.gitSha.slice(0, 12)}</a><p>{item.context || 'Kontext unbekannt'} · {item.createdAt || 'Zeit unbekannt'}</p><p>PASS: {item.counts.PASS ?? 'UNKNOWN'} · FAIL: {item.counts.FAIL ?? 'UNKNOWN'} · UNKNOWN: {item.counts.UNKNOWN ?? 'UNKNOWN'} · N/A: {item.counts.NOT_APPLICABLE ?? 'UNKNOWN'}</p>{item.evaluations.map((result, index) => <p key={index}>{result.status === 'NOT_APPLICABLE' ? 'N/A' : result.status}: {result.reason}</p>)}</div></li>)}</ul> : <p>Keine passenden Assessments.</p>}</div></div>
    </>}
  </section>;
}

/** @param {{label: string, value: string | number}} props */
function Metric({ label, value }) { return <div className="panel"><span>{label}</span><strong>{value}</strong></div>; }

/** @param {{history: Assessment[]}} props */
function HistoryChart({ history }) {
  const max = Math.max(1, ...history.flatMap((item) => states.map((status) => item.counts[status])));
  /** @param {number} index */ const x = (index) => history.length === 1 ? 290 : 25 + index * (530 / (history.length - 1));
  /** @param {number} value */ const y = (value) => 160 - (value / max) * 130;
  return <><svg className="overview-history" viewBox="0 0 580 180" role="img" aria-label="Bewertungen pro historischem Snapshot"><line x1="25" y1="160" x2="555" y2="160" stroke="#dce7f5" /><text x="3" y="30" fill="#8294a9" fontSize="10">{max}</text><text x="8" y="160" fill="#8294a9" fontSize="10">0</text>{states.map((status) => <g key={status}>{history.map((item, index) => <circle key={item.id} cx={x(index)} cy={y(item.counts[status])} r="4" fill={colors[status]} />)}</g>)}</svg><div className="overview-legend">{states.map((status) => <span key={status}><i style={{ background: colors[status] }} />{status === 'NOT_APPLICABLE' ? 'N/A' : status}</span>)}</div><ol className="overview-history-labels">{history.map((item) => <li key={item.id}><a href={`/assessments/${encodeURIComponent(item.id)}`}>{item.createdAt} · {item.environment}</a> · PASS {item.counts.PASS}, FAIL {item.counts.FAIL}, UNKNOWN {item.counts.UNKNOWN}, N/A {item.counts.NOT_APPLICABLE}</li>)}</ol></>;
}

/** @param {{counts: Record<string, number>, total: number}} props */
function Distribution({ counts, total }) {
  let position = 0;
  const stops = states.map((status) => { const from = position; position += counts[status] / total * 100; return `${colors[status]} ${from}% ${position}%`; }).join(', ');
  return <div className="overview-distribution"><div className="overview-donut" role="img" aria-label={`Verteilung von ${total} historischen Bewertungen`} style={{ background: `conic-gradient(${stops})` }}><div><strong>{total}</strong><small>Bewertungen</small></div></div><ul>{states.map((status) => <li key={status}><i style={{ background: colors[status] }} />{status === 'NOT_APPLICABLE' ? 'N/A' : status}: {counts[status]}</li>)}</ul></div>;
}
