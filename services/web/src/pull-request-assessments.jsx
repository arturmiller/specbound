import React, { useEffect, useState } from 'react';

/** @typedef {{id: string, productId: string, context: string, pullRequestNumber: number | null, gitSha: string, environment: string, createdAt: string}} Snapshot */
/** @typedef {{products: {id: string, name: string}[], assessments: Snapshot[]}} Overview */

/** @param {{organizationId: string, accessToken?: string}} props */
export function PullRequestAssessments({ organizationId, accessToken = '' }) {
  const [data, setData] = useState(/** @type {Overview | null} */ (null));
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/organizations/${encodeURIComponent(organizationId)}/overview`, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then((response) => { if (!response.ok) throw new Error(response.status === 403 ? 'Für diese Assessments fehlen die erforderlichen Rechte.' : 'Assessments konnten nicht geladen werden.'); return response.json(); })
      .then(setData).catch((failure) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [organizationId, accessToken]);
  const snapshots = data?.assessments.filter((item) => item.context === 'pull_request') || [];
  return <section className="pr-screen" aria-labelledby="pr-heading">
    <p className="eyebrow">ENTWICKLUNG / PULL REQUESTS</p><div className="page-heading"><div><h1 id="pr-heading">PR-Assessments</h1><p>Gespeicherte Bewertungen einzelner Revisionen. Eine vollständige PR-Inbox ist nicht verfügbar.</p></div></div>
    <div className="pr-columns"><div className="panel"><h2>Gespeicherte PR-Assessments</h2>
      {error ? <p role="alert" className="alert">{error}</p> : !data ? <p role="status">Assessments werden geladen …</p> : snapshots.length === 0 ? <p>Keine sichtbaren PR-Assessments gespeichert.</p> : <><p className="pack-scroll-hint">Tabelle horizontal scrollen, um alle Spalten zu sehen.</p><div className="team-table-scroll" tabIndex={0} aria-label="PR-Assessments, horizontal scrollbar"><table className="team-table"><thead><tr><th>PRODUKT / PR</th><th>REVISION</th><th>UMGEBUNG</th><th>ASSESSMENT</th></tr></thead><tbody>{snapshots.map((snapshot) => <tr key={snapshot.id}><td>{data.products.find((product) => product.id === snapshot.productId)?.name || snapshot.productId}<small>{snapshot.pullRequestNumber ? `PR #${snapshot.pullRequestNumber}` : 'PR unbekannt'}</small></td><td className="break-value">{snapshot.gitSha}</td><td>{snapshot.environment}</td><td><a href={`/assessments/${encodeURIComponent(snapshot.id)}`}>Bericht öffnen</a><small>{snapshot.createdAt}</small></td></tr>)}</tbody></table></div></>}
    </div><div className="panel"><h2>Unabhängige Rollen</h2><dl className="team-role-list"><div><dt>Git-Autoren</dt><dd>Ändern den Code in Git</dd></div><div><dt>Specbound</dt><dd>Speichert revisionsgenaue Assessments</dd></div><div><dt>Review und Merge</dt><dd>Unterliegen den Git-Regeln</dd></div></dl><div className="team-info">GitHub-PR-Inbox, Live-Checks und ein manueller Recheck sind hier nicht verfügbar. Die Plattform verteilt keine Aufgaben an Menschen oder Agenten.</div></div></div>
  </section>;
}
