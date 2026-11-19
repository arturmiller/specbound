import React, { useEffect, useState } from 'react';
import { ManifestProvenance } from './manifest-source.jsx';
import { organizationHref } from './portal-shell.jsx';
import { GovernancePlans } from './governance-plans.jsx';

/** @typedef {{id: string, repository: string, tag: string, commit: string, kind: string, manifestPath?: string, schemaUrl?: string, manifestUrl?: string, commitUrl?: string, manifest: {metadata: {id: string, version: string}}, controls: {id: string}[]}} Pack */

/** @param {{organizationId: string, accessToken: string, entry?: boolean}} props */
export function GovernancePackArchive({ organizationId, accessToken, entry = false }) {
  const path = location.pathname.startsWith('/packs') ? '/packs' : '/catalogs?view=archive';
  const listUrl = organizationHref(path, organizationId);
  const query = new URLSearchParams(location.search);
  const selected = entry ? null : query.get('pack');
  const legacyView = query.get('view') || '';
  const root = `/api/organizations/${encodeURIComponent(organizationId)}/packs`;
  const [packs, setPacks] = useState(/** @type {Pack[] | null} */ (null));
  const [error, setError] = useState('');
  const [approval, setApproval] = useState(/** @type {{approved: boolean, approvedBy: string | null, approvedAt?: string | null} | null} */ (null));
  const [approvalError, setApprovalError] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');
  const detail = packs?.find((pack) => pack.id === selected);

  useEffect(() => {
    const controller = new AbortController();
    fetch(root, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then(async (response) => {
        if (!response.ok) throw new Error(response.status === 403 ? 'Für diese Packs fehlen die erforderlichen Rechte.' : 'Packs konnten nicht geladen werden.');
        /** @type {Pack[]} */ const data = await response.json();
        if (!controller.signal.aborted) setPacks(data);
      })
      .catch((failure) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [root, accessToken]);

  useEffect(() => {
    if (detail?.kind !== 'governance') return;
    const controller = new AbortController();
    fetch(`${root}/${encodeURIComponent(detail.id)}/approval`, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        const value = await response.json();
        if (!controller.signal.aborted) setApproval(value);
      })
      .catch(() => { if (!controller.signal.aborted) setApprovalError(true); });
    return () => controller.abort();
  }, [root, detail, accessToken]);

  /** @param {boolean} includeBindings */
  async function download(includeBindings) {
    if (!detail || exporting) return;
    setExporting(true);
    setExportError('');
    try {
      const endpoint = `${root}/${encodeURIComponent(detail.id)}/manifests?include_bindings=${includeBindings}`;
      const response = await fetch(endpoint, { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} });
      if (!response.ok) {
        const failure = await response.json().catch(() => ({}));
        throw new Error(response.status === 422 && typeof failure.detail === 'string'
          ? failure.detail : 'Manifeste konnten nicht heruntergeladen werden.');
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = 'governance-manifeste.zip';
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (failure) {
      setExportError(failure instanceof Error ? failure.message : 'Manifeste konnten nicht heruntergeladen werden.');
    } finally {
      setExporting(false);
    }
  }

  const governance = packs?.filter((pack) => pack.kind === 'governance') || [];
  if (entry) return governance.length > 0 && <p><a href="/catalogs?view=archive">Archiv der Governance-Packs</a></p>;
  if (path === '/packs' && ['releases', 'impact', 'activation', 'baseline-impact'].includes(legacyView)) {
    if (error) return <p role="alert" className="alert">{error}</p>;
    if (!packs) return <p role="status">Packs werden geladen …</p>;
    return <GovernancePlans organizationId={organizationId} packs={governance} selected={selected || ''} view={legacyView} />;
  }
  return <section aria-labelledby="packs-heading">
    <div className="page-heading"><div>
      <h1 id="packs-heading">{detail?.kind === 'governance' ? detail.manifest.metadata.id : 'Archiv der Governance-Packs'}</h1>
      <p>Gespeicherte Revisionen und Freigaben.</p>
    </div><a href="/catalogs">Alle Kataloge</a></div>
    {error ? <p role="alert" className="alert">{error}</p>
      : !packs ? <p role="status">Packs werden geladen …</p>
      : selected ? detail?.kind === 'provider' ? <p><a href={organizationHref(`/providers?pack=${encodeURIComponent(detail.id)}`, organizationId)}>Evidence Pack ansehen</a></p>
        : !detail ? <p>Die Pack-Revision ist nicht verfügbar.</p>
        : <>
          <p>Version {detail.manifest.metadata.version} · {detail.repository} · {detail.tag}</p>
          <ManifestProvenance source={detail} defaultPath="pack.yaml" />
          {approvalError ? <p role="alert">Freigabestatus konnte nicht geladen werden.</p>
            : !approval ? <p role="status">Freigabestatus wird geladen …</p>
            : <p>{approval.approved ? `Freigegeben von ${approval.approvedBy}${approval.approvedAt ? ` · ${approval.approvedAt}` : ''}` : 'Nicht freigegeben'}</p>}
          <h2>Controls</h2>
          {detail.controls.map((control) => <details className="panel" key={control.id}>
            <summary>{control.id}</summary>
            <pre className="pack-json">{JSON.stringify(control, null, 2)}</pre>
          </details>)}
          <details className="panel"><summary>Manifest</summary><pre className="pack-json">{JSON.stringify(detail.manifest, null, 2)}</pre></details>
          <section className="panel" aria-label="Manifeste für Git">
            <h2>Manifeste für Git</h2>
            <p>Exportiere einen Katalog und ein Profil. Prüfe ihre Inhalte und lege die Dateien gemeinsam im gewünschten Repository ab.</p>
            <div className="resource-actions">
              <button type="button" disabled={exporting} onClick={() => { void download(true); }}>Mit Prüfbindungen herunterladen</button>
              <button type="button" disabled={exporting} onClick={() => { void download(false); }}>Ohne Prüfbindungen herunterladen</button>
            </div>
            {exportError && <p className="alert" role="alert">{exportError}</p>}
          </section>
          <a href={listUrl}>Alle archivierten Governance-Packs</a>
        </>
      : governance.length ? <ul>{governance.map((pack) => <li key={pack.id}>
        <a href={`${listUrl}&pack=${encodeURIComponent(pack.id)}`}>{pack.manifest.metadata.id} · {pack.manifest.metadata.version} · {pack.tag}</a>
      </li>)}</ul> : <p>Keine alten Governance-Packs vorhanden.</p>}
  </section>;
}
