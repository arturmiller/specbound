import React, { useEffect, useState } from 'react';

/** @typedef {{sourceUrl?: string, sourceKind?: string, artifactSha256?: string}} Artifact */
/** @typedef {{name: string, version: string, path: string, status: string, licenseExpression: string | null, metadata?: {reason?: string, artifacts?: Artifact[]}}} PackageResult */
/** @typedef {{sourceRevision: string, coverage: string, reason: string, files: string[], unsupportedFiles: string[], packages: PackageResult[]}} Result */
/** @typedef {{id: string, status: string, ref: string, createdAt: string, errorCode: string | null, result: Result | null}} Scan */

/** @param {{productId: string, bindingId: string, repository: string, accessToken: string, canEdit: boolean}} props */
export function PublicLicenseScans({ productId, bindingId, repository, accessToken, canEdit }) {
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
  const active = runs?.some((run) => run.status === 'pending' || run.status === 'running');
  const states = /** @type {Record<string, string>} */ ({ pending: 'Wartet auf den lokalen Worker', running: 'Wird ausgeführt', completed: 'Abgeschlossen', failed: 'Fehlgeschlagen' });
  const errors = /** @type {Record<string, string>} */ ({ 'rate-limited': 'GitHub-Anfragelimit erreicht.', 'source-not-found': 'Öffentliches Repository oder Ref nicht gefunden.', 'source-unavailable': 'GitHub oder die Quelle ist nicht verfügbar.', 'source-changed': 'Die Repository-Zuordnung wurde geändert.', 'scanner-failed': 'Der Scanner konnte nicht abgeschlossen werden.', timeout: 'Zeitlimit erreicht.', 'attempts-exhausted': 'Wiederholungsversuche ausgeschöpft.' });
  return <section className="panel public-license-scan" aria-label={`Lizenzscan für ${repository}`}>
    <h2>Öffentlicher Python-Lizenzscan</h2>
    <p>Nur öffentliche GitHub-Quellen und <code>uv.lock</code>. Die Vorschau ist noch kein gespeichertes Assessment und erzeugt keine Findings.</p>
    <p>Beispielrichtlinie: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause und ISC sind freigegeben. Weitere erkannte Lizenzen sind nicht freigegeben; unklare Angaben bleiben UNKNOWN.</p>
    {canEdit && <form onSubmit={start}><label className="field">Git-Ref<input required maxLength={200} value={ref} onChange={(event) => setRef(event.target.value)} /></label><button type="submit" disabled={busy || !runs || Boolean(active)}>Öffentlichen Lizenzscan starten</button></form>}
    {error && <p role="alert" className="alert">{error}</p>}
    {runs === null ? !error && <p role="status">Scans werden geladen …</p> : !latest ? <p>Noch kein Lizenzscan gestartet.</p> : <div aria-live="polite"><h3>Letzter Scan</h3><p>Status: <strong>{states[latest.status] || latest.status}</strong> · Ref: {latest.ref}</p>
      {latest.errorCode && <p>{errors[latest.errorCode] || 'Scan nicht verfügbar.'}</p>}
      {latest.result && <><p className="break-value">Git-Commit: {latest.result.sourceRevision}</p><p>Abdeckung: {latest.result.coverage} · Lockfiles: {latest.result.files.join(', ') || 'Keine'}</p><p>{latest.result.reason}</p>{latest.result.unsupportedFiles.length > 0 && <p>Nicht unterstützte Lockfiles: {latest.result.unsupportedFiles.join(', ')}</p>}
        <div className="team-table-scroll"><table className="team-table"><thead><tr><th>PAKET</th><th>LIZENZ</th><th>ERGEBNIS</th><th>QUELLE</th></tr></thead><tbody>{latest.result.packages.map((pkg, index) => <tr key={`${pkg.path}-${pkg.name}-${pkg.version}-${index}`}><td>{pkg.name} · {pkg.version}<small>{pkg.path}</small></td><td>{pkg.licenseExpression || 'UNKNOWN'}</td><td>{pkg.status}</td><td className="break-value">{pkg.metadata?.artifacts?.map((a) => a.sourceUrl).filter(Boolean).join(', ') || pkg.metadata?.reason || 'UNKNOWN'}</td></tr>)}</tbody></table></div>
      </>}
    </div>}
  </section>;
}
