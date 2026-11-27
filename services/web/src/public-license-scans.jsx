import React, { useEffect, useState } from 'react';
import { ScanSource } from './assessment-governance.jsx';
import { runDate } from './run-list.jsx';

/** @typedef {{sourceUrl?: string, sourceKind?: string, artifactSha256?: string}} Artifact */
/** @typedef {{name: string, version: string, path: string, status: string, licenseExpression: string | null, metadata?: {status?: string, reason?: string, artifacts?: Artifact[]}}} PackageResult */
/** @typedef {{sourceRevision: string, coverage: string, reason: string, files: string[], unsupportedFiles: string[], packages: PackageResult[], assessmentError?: string}} Result */
/** @typedef {{id: string, status: string, ref: string, createdAt: string, errorCode: string | null, assessmentId: string | null, governanceContext?: import('./assessment-governance.jsx').FrozenContext | null, result: Result | null}} Scan */

/** @param {{organizationId: string, productId: string, bindingId: string, repository: string, accessToken: string, canEdit: boolean, profileManaged?: boolean}} props */
export function PublicLicenseScans({ organizationId, productId, bindingId, repository, accessToken, canEdit, profileManaged = false }) {
  const [runs, setRuns] = useState(/** @type {Scan[] | null} */ (null));
  const [ref, setRef] = useState('main');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const url = `/api/products/${encodeURIComponent(productId)}/repositories/${encodeURIComponent(bindingId)}/public-license-scans`;

  useEffect(() => {
    const controller = new AbortController();
    /** @type {ReturnType<typeof setTimeout> | undefined} */ let timer;
    async function load() {
      try {
        const response = await fetch(url, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} });
        if (!response.ok) throw new Error(response.status === 403 ? 'Für diese Scans fehlen die erforderlichen Rechte.' : 'Scanergebnisse konnten nicht geladen werden.');
        /** @type {Scan[]} */ const data = await response.json();
        if (!Array.isArray(data)) throw new Error('Ungültige Scanantwort.');
        if (controller.signal.aborted) return;
        setRuns(data); setError('');
        if (data.some((item) => item.status === 'pending' || item.status === 'running')) timer = setTimeout(load, 2500);
      } catch (failure) { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Scanergebnisse konnten nicht geladen werden.'); }
    }
    void load();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [url, accessToken, refresh]);

  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function start(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) }, body: JSON.stringify({ ref }) });
      if (!response.ok) throw new Error(response.status === 409 ? 'Für dieses Repository läuft bereits ein Scan.' : response.status === 403 ? 'Für diesen Scan fehlen die erforderlichen Rechte.' : 'Scan konnte nicht gestartet werden.');
      setRefresh((value) => value + 1);
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Scan konnte nicht gestartet werden.'); }
    finally { setBusy(false); }
  }

  const latest = runs?.[0];
  const profile = latest?.governanceContext?.mode === 'profile' ? latest.governanceContext.profile : null;
  const active = runs?.some((run) => run.status === 'pending' || run.status === 'running');
  const states = /** @type {Record<string, string>} */ ({ pending: 'Wartet auf den lokalen Worker', running: 'Wird ausgeführt', completed: 'Abgeschlossen', failed: 'Fehlgeschlagen' });
  const errors = /** @type {Record<string, string>} */ ({ 'rate-limited': 'GitHub-Anfragelimit erreicht.', 'source-not-found': 'Öffentliches Repository oder Ref nicht gefunden.', 'source-unavailable': 'GitHub oder die Quelle ist nicht verfügbar.', 'source-changed': 'Die Repository-Zuordnung wurde geändert.', 'scanner-failed': 'Der Scanner konnte nicht abgeschlossen werden.', timeout: 'Zeitlimit erreicht.', 'attempts-exhausted': 'Wiederholungsversuche ausgeschöpft.' });
  return <section className="panel public-license-scan" aria-label={`Lizenzscan für ${repository}`}>
    <h2>Öffentlicher Python-Lizenzscan</h2>
    {canEdit && <form onSubmit={start}><label className="field">Git-Ref<input required maxLength={200} value={ref} onChange={(event) => setRef(event.target.value)} /></label><button type="submit" disabled={busy || !runs || Boolean(active)}>Öffentlichen Lizenzscan starten</button></form>}
    <details className="assessment-disclosure scan-scope">
      <summary>Scanumfang und Richtlinie</summary>
      <p>Der manuelle Scan prüft <code>uv.lock</code> in einer Revision eines öffentlichen GitHub-Repositories.</p>
      <p>{profileManaged ? 'Der Scan fixiert das geltende Produktprofil beim Start. Nicht unterstützte Controls bleiben als Lücke sichtbar.' : 'Die Beispielrichtlinie erlaubt MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause und ISC. Andere erkannte Lizenzen führen zu einem Verstoß. Mehrdeutige Angaben bleiben ungeklärt.'}</p>
    </details>
    {error && <p role="alert" className="alert">{error}</p>}
    {runs === null ? !error && <p role="status">Scans werden geladen …</p> : !latest ? <p>Noch kein Lizenzscan gestartet.</p> : <div><p aria-live="polite">Letzter Scan · <time dateTime={latest.createdAt}>{runDate(latest.createdAt)}</time> · <strong>{states[latest.status] || latest.status}</strong></p>
      {latest.errorCode && <p>{errors[latest.errorCode] || 'Scan nicht verfügbar.'}</p>}
      {latest.assessmentId ? <p><a href={`/products?${new URLSearchParams({ organization: organizationId, product: productId, view: 'requirements', assessment: latest.assessmentId })}`}>Assessment und Findings ansehen →</a></p> : latest.status === 'completed' && <p>Für diesen Scan ist kein Assessment verfügbar.</p>}
      {latest.result?.assessmentError && <p role="alert" className="alert">Das Assessment konnte nicht erstellt werden; die Scanvorschau bleibt erhalten.</p>}
      <details className="assessment-disclosure" key={latest.id}>
        <summary>Details zum letzten Lauf</summary>
        {profile && <p>Fixiertes Profil: <strong>{profile.name} · {profile.version}</strong></p>}
        {latest.governanceContext?.mode === 'legacy-example' && <p>Dieser Lauf verwendet die fixierte Beispielrichtlinie.</p>}
        {latest.result ? <>
          <ScanSource sourceScan={{ id: latest.id, repository, ref: latest.ref, ...latest.result }} />
          {latest.result.packages.length > 0 && <div className="team-table-scroll">
            <table className="team-table">
              <thead><tr><th>PAKET</th><th>LIZENZ</th><th>{profile ? 'METADATEN' : 'ERGEBNIS'}</th><th>QUELLE</th></tr></thead>
              <tbody>{latest.result.packages.map((pkg, index) => {
                const sources = pkg.metadata?.artifacts?.flatMap(({ sourceUrl }) => sourceUrl && /^https?:\/\//i.test(sourceUrl) ? [sourceUrl] : []) || [];
                return <tr key={`${pkg.path}-${pkg.name}-${pkg.version}-${index}`}>
                  <td>{pkg.name} · {pkg.version}<small>{pkg.path}</small></td>
                  <td>{pkg.licenseExpression || 'UNKNOWN'}</td>
                  <td>{profile ? pkg.metadata?.status || 'UNKNOWN' : pkg.status}</td>
                  <td>{sources.length ? sources.map((url, i) => <div key={i}><a href={url}>{sources.length === 1 ? 'Metadaten öffnen' : `Metadaten ${i + 1} öffnen`}</a></div>) : pkg.metadata?.reason || 'UNKNOWN'}</td>
                </tr>;
              })}</tbody>
            </table>
          </div>}
        </> : <p>Git-Ref: {latest.ref}</p>}
      </details>
    </div>}
  </section>;
}
