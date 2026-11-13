import React, { useEffect, useState } from 'react';

/** @typedef {{id: string, name: string}} Team */
/** @typedef {{id: string, name: string, teamId: string}} Product */
/** @typedef {{id: string, productId: string, subjectId: string, controlId: string, environment: string, status: string, snapshotId: string, context: string, pullRequestNumber: number | null}} Finding */
/** @typedef {{id: string, productId: string, context: string, environment: string, pullRequestNumber: number | null, gitSha: string}} Assessment */
/** @typedef {{products: Product[], findings: Finding[], assessments: Assessment[]}} Overview */

/** @param {{organizationId: string, teams: Team[], teamsLoading: boolean, teamsError: string, accessToken?: string}} props */
export function FindingInbox({ organizationId, teams, teamsLoading, teamsError, accessToken = '' }) {
  const [data, setData] = useState(/** @type {Overview | null} */ (null));
  const [error, setError] = useState('');
  const [origin, setOrigin] = useState('pull_request');
  const [status, setStatus] = useState('all');
  const [team, setTeam] = useState('');
  const [search, setSearch] = useState('');
  const params = new URLSearchParams(window.location.search);
  const view = params.get('view') || 'inbox';
  /** @param {string} target */
  const link = (target) => `/findings?${new URLSearchParams({ organization: organizationId, ...(target ? { view: target } : {}) })}`;
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/organizations/${encodeURIComponent(organizationId)}/overview`, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then((response) => { if (!response.ok) throw new Error(response.status === 403 ? 'Für diese Findings fehlen die erforderlichen Rechte.' : 'Findings konnten nicht geladen werden.'); return response.json(); })
      .then(setData).catch((failure) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [organizationId, accessToken]);
  const prFindings = data?.findings.filter((finding) => finding.context === 'pull_request') || [];
  const visible = prFindings.filter((finding) => {
    const product = data?.products.find((item) => item.id === finding.productId);
    const term = search.trim().toLocaleLowerCase();
    return (!team || product?.teamId === team) && (status === 'all' || finding.status === status) && [finding.controlId, finding.subjectId, finding.environment, product?.name || '', String(finding.pullRequestNumber ?? '')].some((value) => value.toLocaleLowerCase().includes(term));
  });
  const navigation = <nav className="pr-tabs" aria-label="Finding-Ansichten"><a href={link('')} aria-current={view === 'inbox' ? 'page' : undefined}>Inbox</a><a href={link('repository')} aria-current={view === 'repository' ? 'page' : undefined}>Repository-Scans</a><a href={link('triage')} aria-current={view === 'triage' ? 'page' : undefined}>Baseline-Triage</a><a href={link('closure')} aria-current={view === 'closure' ? 'page' : undefined}>Baseline-Abschluss</a></nav>;
  if (view === 'repository') {
    const repositoryFindings = data?.findings.filter((finding) => finding.context === 'repository') || [];
    return <section className="finding-screen" aria-labelledby="repository-findings-heading">
      <div className="page-heading"><div><h1 id="repository-findings-heading">Findings aus Repository-Scans</h1><p>Gespeicherte Findings aus Bewertungen einzelner Repository-Revisionen.</p></div></div>
      {navigation}
      {error ? <p role="alert" className="alert">{error}</p> : !data ? <p role="status">Findings werden geladen …</p> : <div className="panel team-table-panel">
        {repositoryFindings.length === 0 ? <p>Keine sichtbaren Repository-Findings gespeichert.</p> : <div className="team-table-scroll" tabIndex={0} aria-label="Repository-Findings, horizontal scrollbar"><table className="team-table"><thead><tr><th>FINDING</th><th>PRODUKT / REVISION</th><th>STATUS</th></tr></thead><tbody>{repositoryFindings.map((finding) => {
          const product = data.products.find((item) => item.id === finding.productId);
          const snapshot = data.assessments.find((item) => item.id === finding.snapshotId && item.productId === finding.productId && item.context === 'repository');
          return <tr key={finding.id}><td><a href={`/findings?${new URLSearchParams({ organization: organizationId, finding: finding.id })}`}>{finding.controlId} · {finding.subjectId}</a></td><td>{product?.name || finding.productId}<small className="break-value">{snapshot?.gitSha || 'Revision nicht verfügbar'}</small></td><td>{finding.status}</td></tr>;
        })}</tbody></table></div>}
      </div>}
    </section>;
  }
  const planned = <div className="team-info">Baseline-Reassessment und Governance-Auswirkungen sind noch nicht verfügbar. Geplant in <a href="https://github.com/arturmiller/specbound/issues/65">#65</a>, <a href="https://github.com/arturmiller/specbound/issues/66">#66</a>, <a href="https://github.com/arturmiller/specbound/issues/67">#67</a> und <a href="https://github.com/arturmiller/specbound/issues/68">#68</a>.</div>;
  return <section className="finding-screen" aria-labelledby="inbox-heading">
    <p className="eyebrow">FINDINGS / {view === 'triage' ? 'BASELINE-TRIAGE' : view === 'closure' ? 'BASELINE-ABSCHLUSS' : 'INBOX'}</p><div className="page-heading"><div><h1 id="inbox-heading">{view === 'triage' ? 'Baseline-Triage' : view === 'closure' ? 'Baseline-Abschluss' : 'Finding-Inbox'}</h1><p>{view === 'inbox' ? 'Gespeicherte Findings aus Pull-Request-Assessments.' : 'Geplante Ansicht; es wird keine Zuweisung oder Abschlussaktion ausgeführt.'}</p></div><a className="primary-link" href={`/pr-checks?${new URLSearchParams({ organization: organizationId })}`}>PR-Assessments →</a></div>
    {navigation}
    {view !== 'inbox' && error && <p role="alert" className="alert">{error}</p>}
    {view === 'triage' ? <><div className="team-metrics team-detail-metrics"><div className="panel"><span>Auslöser</span><strong>UNKNOWN</strong></div><div className="panel"><span>Produkt</span><strong>UNKNOWN</strong></div><div className="panel"><span>Team</span><strong>UNKNOWN</strong></div><div className="panel"><span>Control</span><strong>UNKNOWN</strong></div></div><div className="team-columns"><div className="panel"><h2>Herkunft der Baseline</h2><p>Eine neue Governance-Anforderung und ihre Auswirkungen werden hier noch nicht berechnet.</p>{planned}</div><div className="panel"><h2>Zuweisung und Frist</h2><p>Eine verantwortliche Person, Frist oder automatische Aufgabenzuweisung kann hier nicht festgelegt werden.</p><a href={link('closure')}>Geplanten Abschluss ansehen →</a></div></div></> : view === 'closure' ? <><div className="panel journey-steps"><div><strong>Governance-Änderung</strong><span>UNKNOWN</span></div><div><strong>Baseline-Finding</strong><span>Nicht verfügbar</span></div><div><strong>Deployment</strong><span>UNKNOWN</span></div><div><strong>Aktuelle Evidence</strong><span>UNKNOWN</span></div></div><div className="team-columns"><div className="panel"><h2>Deployment und Evidence</h2><p>Ein Deployment oder aktueller Produktionsnachweis wird hier nicht behauptet.</p>{planned}</div><div className="panel"><h2>Abschluss</h2><p>Eine Abschlussaktion für Baseline-Findings ist nicht verfügbar. Ein PR-Ergebnis belegt keinen Produktionszustand.</p><a href={link('')}>Zur Finding-Inbox →</a></div></div></> : <>{error ? <p role="alert" className="alert">{error}</p> : !data ? <p role="status">Findings werden geladen …</p> : <><div className="team-metrics team-detail-metrics"><div className="panel"><span>Offene PR-Findings</span><strong>{prFindings.filter((finding) => finding.status === 'open').length}</strong></div><div className="panel"><span>Gespeicherte PR-Findings</span><strong>{prFindings.length}</strong></div><div className="panel"><span>Baseline-Triage</span><strong>Nicht verfügbar</strong></div><div className="panel"><span>Produktions-Recheck</span><strong>Nicht verfügbar</strong></div></div><div className="inbox-filters"><label>Herkunft<select value={origin} onChange={(event) => setOrigin(event.target.value)}><option value="pull_request">Pull Requests</option><option value="baseline">Baseline (geplant)</option></select></label><label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">Alle</option><option value="open">Offen</option><option value="resolved">Resolved</option></select></label><label>Team<select value={team} disabled={teamsLoading || Boolean(teamsError)} onChange={(event) => setTeam(event.target.value)}><option value="">Alle sichtbaren Teams</option>{teams.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Suche<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} /></label></div>{teamsError && <p role="alert" className="alert">Teamfilter nicht verfügbar: {teamsError}</p>}<div className="panel team-table-panel"><h2>Gespeicherte Findings</h2>{origin === 'baseline' ? <><p>Baseline-Findings und ihre Triage sind in dieser Ansicht noch nicht verfügbar.</p>{planned}</> : visible.length === 0 ? <p>{prFindings.length ? 'Keine PR-Findings für diese Filter.' : 'Keine sichtbaren PR-Findings gespeichert.'}</p> : <><p className="pack-scroll-hint">Tabelle horizontal scrollen, um alle Spalten zu sehen.</p><div className="team-table-scroll" tabIndex={0} aria-label="Findings, horizontal scrollbar"><table className="team-table inbox-table"><thead><tr><th>FINDING</th><th>HERKUNFT</th><th>PRODUKT / REVISION</th><th>CONTROL</th><th>STATUS</th><th>TEAM</th></tr></thead><tbody>{visible.map((finding) => { const product = data.products.find((item) => item.id === finding.productId); const snapshot = data.assessments.find((item) => item.id === finding.snapshotId && item.productId === finding.productId && item.context === 'pull_request' && item.environment === finding.environment && item.pullRequestNumber === finding.pullRequestNumber); const owner = teams.find((item) => item.id === product?.teamId); return <tr key={finding.id}><td><a href={`/findings?${new URLSearchParams({ organization: organizationId, finding: finding.id })}`}>{finding.controlId} · {finding.subjectId}</a></td><td>{finding.pullRequestNumber == null ? 'PR unbekannt' : `PR #${finding.pullRequestNumber}`}</td><td>{product?.name || finding.productId}<small className="break-value">{snapshot?.gitSha || 'Revision nicht verfügbar'}</small></td><td>{finding.controlId}</td><td>{finding.status}</td><td>{owner?.name || product?.teamId || 'Nicht verfügbar'}</td></tr>; })}</tbody></table></div></>}</div><div className="team-info">PR-Findings beziehen sich auf gespeicherte Assessment-Snapshots. Baseline-Triage, Zuweisung und Produktions-Recheck werden hier nicht vorgetäuscht. <a href={link('triage')}>Geplante Baseline-Triage ansehen →</a></div></>}</>}
  </section>;
}
