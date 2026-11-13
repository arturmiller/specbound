import React, { useEffect, useState } from 'react';

/** @typedef {{id: string, packRevisionId: string, packCommit: string, status: string, createdAt: string, synthetic: boolean}} TestRun */

/** @param {{organizationId: string, revisionId: string, accessToken: string, isOwner: boolean}} props */
export function ProviderTestRuns({ organizationId, revisionId, accessToken, isOwner }) {
  const [runs, setRuns] = useState(/** @type {TestRun[] | null} */ (null));
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const url = `/api/organizations/${encodeURIComponent(organizationId)}/packs/${encodeURIComponent(revisionId)}/test-runs`;
  useEffect(() => {
    if (!isOwner) return;
    const controller = new AbortController();
    fetch(url, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then((response) => { if (!response.ok) throw new Error(response.status === 403 ? 'Für Testläufe fehlen die erforderlichen Rechte.' : 'Testläufe konnten nicht geladen werden.'); return response.json(); })
      .then(setRuns).catch((failure) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [url, accessToken, isOwner]);

  async function requestRun() {
    setBusy(true); setError('');
    try {
      const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) }, body: '{}' });
      if (!response.ok) throw new Error(response.status === 403 ? 'Für Testläufe fehlen die erforderlichen Rechte.' : 'Testlauf konnte nicht vorgemerkt werden.');
      const run = await response.json();
      setRuns((current) => [run, ...(current || [])]);
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Testlauf konnte nicht vorgemerkt werden.'); }
    finally { setBusy(false); }
  }

  return <section className="panel journey-note" aria-labelledby="provider-test-runs-heading">
    <h2 id="provider-test-runs-heading">Synthetische Testläufe</h2>
    <p>Die Ausführung ist noch nicht verfügbar. Ein vorgemerkter Testlauf startet keinen Collector und erzeugt keine Evidence.</p>
    {!isOwner ? <p>Nur Organisationseigentümer können Testläufe vormerken und ansehen.</p> : <>
      {error && <p role="alert" className="alert">{error}</p>}
      <button type="button" disabled={busy || runs === null} onClick={requestRun}>Testlauf vormerken</button>
      {runs === null && !error ? <p role="status">Testläufe werden geladen …</p> : runs?.length === 0 ? <p>Noch keine Testläufe vorgemerkt.</p> : runs && <ul className="journey-events">{runs.map((run) => <li key={run.id}><strong>Vorgemerkt · synthetisch</strong><p>ID: {run.id}</p><p className="break-value">Pack-Commit: {run.packCommit}</p><p>Zeit: {new Date(run.createdAt).toLocaleString()}</p></li>)}</ul>}
    </>}
  </section>;
}
