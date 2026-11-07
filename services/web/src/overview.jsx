import React, { useEffect, useState } from 'react';

/** @typedef {{id: string, name: string}} Team */
/** @typedef {{id: string, name: string, teamId: string}} Product */
/** @typedef {{id: string, repository: string, tag: string, kind: string, name: string}} Pack */
/** @typedef {{id: string, productId: string, subjectId: string, controlId: string, environment: string, status: string, snapshotId: string}} Finding */
/** @typedef {{products: Product[], packs: Pack[], findings: Finding[]}} Data */

/** @param {{organizationId: string, teams: Team[], accessToken?: string}} props */
export function Overview({ organizationId, teams, accessToken = '' }) {
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
    }).then((response) => { if (!response.ok) throw new Error('load failed'); return response.json(); })
      .then(setData).catch(() => { if (!controller.signal.aborted) setError('Übersicht konnte nicht geladen werden.'); });
    return () => controller.abort();
  }, [organizationId, accessToken, version]);

  const term = search.trim().toLocaleLowerCase();
  /** @param {...string} values */
  const matches = (...values) => values.some((value) => value.toLocaleLowerCase().includes(term));
  const products = data?.products.filter((item) => (!team || item.teamId === team) && matches(item.name, item.id)) || [];
  const allTeamProducts = data?.products.filter((item) => !team || item.teamId === team) || [];
  const productIds = new Set(allTeamProducts.map((item) => item.id));
  const findings = data?.findings.filter((item) => productIds.has(item.productId) && (!scope || item.environment === scope)
    && matches(item.controlId, item.subjectId, item.status, item.environment)) || [];
  const packs = data?.packs.filter((item) => matches(item.name, item.repository, item.tag, item.kind)) || [];
  const scopes = [...new Set((data?.findings || []).filter((item) => productIds.has(item.productId)).map((item) => item.environment))].sort();
  const root = `/?organization=${encodeURIComponent(organizationId)}`;

  return <section className="workspace" aria-labelledby="overview-heading">
    <div className="workspace-heading"><div><p className="eyebrow">ÜBERSICHT</p><h2 id="overview-heading">Übersicht und Suche</h2></div>
      <button type="button" onClick={() => setVersion((value) => value + 1)}>Aktualisieren</button></div>
    <label className="field">Suche<input value={search} onChange={(event) => setSearch(event.target.value)} /></label>
    <label className="field">Teamfilter<select value={team} onChange={(event) => { setTeam(event.target.value); setScope(''); }}>
      <option value="">Alle Teams</option>{teams.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <label className="field">Scope<select value={scope} onChange={(event) => setScope(event.target.value)}>
      <option value="">Alle Umgebungen</option>{scopes.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
    <p>Teamfilter gilt für Produkte und Findings; Scope für Findings.</p>
    {error && <p role="alert">{error}</p>}{!data && !error && <p>Übersicht wird geladen …</p>}
    {data && <div className="workspace-grid">
      <div className="panel"><h3>Produkte</h3>{products.length ? <ul>{products.map((item) => <li key={item.id}>
        <a href={`${root}&product=${encodeURIComponent(item.id)}#products-heading`}>{item.name}</a></li>)}</ul> : <p>Keine passenden Produkte.</p>}</div>
      <div className="panel"><h3>Packs</h3><p>Organisationsweit; nicht nach Team oder Umgebung zugeordnet.</p>{packs.length ? <ul>{packs.map((item) => <li key={item.id}>
        <a href={`${root}&pack=${encodeURIComponent(item.id)}#packs-heading`}>{item.name} · {item.tag}</a></li>)}</ul> : <p>Keine passenden Packs.</p>}</div>
      <div className="panel"><h3>Findings</h3>{findings.length ? <ul>{findings.map((item) => <li key={item.id}>
        <a href={`/assessments/${encodeURIComponent(item.snapshotId)}`}>{item.controlId} · {item.status} · {item.environment}</a></li>)}</ul> : <p>Keine passenden Findings.</p>}</div>
    </div>}
  </section>;
}
