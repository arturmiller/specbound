import React, { useEffect, useRef, useState } from 'react';
import { CapabilityUsage } from './capability-usage.jsx';
import { ResourceRevisions } from './resource-revisions.jsx';
import { ManifestProvenance, ManifestSourceFields } from './manifest-source.jsx';

/** @typedef {{prose?: string, parts?: NativePart[]}} NativePart */
/** @typedef {{id: string, title: string, parts: NativePart[], parameters: unknown[], groupKey: string, methodStatus: string, binding: {target: {kind: string}, requiredEvidence: {capability: string}, assertions: unknown[]} | null}} ResourceControl */
/** @typedef {{key: string, id: string | null, title: string, parent: string | null}} ResourceGroup */
/** @typedef {{repository: string, ref: string, refType: string, commit: string, manifestPath: string, manifestUrl: string, commitUrl: string, schemaUrl: string, files: {path: string, url: string}[]}} ResourceSource */
/** @typedef {{id: string | null, resourceType: string, resourceId: string, version: string, name: string, state: string, validationStatus: string, contentDigest: string, source: ResourceSource, manifest: Record<string, unknown>, resolved: {groups: ResourceGroup[], controls: ResourceControl[], bindingPath: string | null, capabilities?: {id: string, version: string}[], productId?: string, repositories?: {provider: string, repository: string}[], profile?: {name: string, version: string}, catalog?: {resourceId: string, version: string, name: string, contentDigest: string, manifestPath: string, revisionId: string}}}} Resource */

/** @param {{parts: NativePart[]}} props */
export function RequirementParts({ parts }) {
  return <>{parts.map((part, index) => <React.Fragment key={index}>{part.prose && <p className="break-value">{part.prose}</p>}{part.parts && <RequirementParts parts={part.parts} />}</React.Fragment>)}</>;
}

/** @param {{resource: Resource}} props */
export function CatalogControls({ resource }) {
  const [search, setSearch] = useState('');
  const controls = resource.resolved.controls.filter((control) => `${control.id} ${control.title} ${JSON.stringify(control.parts)}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  const requirementUrl = resource.resolved.catalog ? resource.source.files.find((file) => file.path === resource.resolved.catalog?.manifestPath)?.url : resource.source.manifestUrl;
  const groupsByKey = new Map(resource.resolved.groups.map((group) => [group.key, group]));
  const visibleGroups = new Set();
  for (const control of controls) {
    let group = groupsByKey.get(control.groupKey);
    while (group && !visibleGroups.has(group.key)) { visibleGroups.add(group.key); group = group.parent ? groupsByKey.get(group.parent) : undefined; }
  }
  /** @param {ResourceGroup} group @param {number} depth @returns {React.ReactNode} */
  function groupView(group, depth) {
    if (!visibleGroups.has(group.key)) return null;
    const direct = controls.filter((control) => control.groupKey === group.key);
    const children = resource.resolved.groups.filter((candidate) => candidate.parent === group.key);
    const Heading = depth === 0 ? 'h2' : depth === 1 ? 'h3' : depth === 2 ? 'h4' : depth === 3 ? 'h5' : 'h6';
    return <section key={group.key} className="resource-group">
      {(group.key !== '$root' || direct.length > 0) && <Heading>{group.title}{group.id && <small> · {group.id}</small>}</Heading>}
      {direct.map((control) => <details key={control.id} className="resource-control panel"><summary><strong>{control.id}</strong>{' · '}{control.title}</summary>
        <RequirementParts parts={control.parts} />
        {control.binding ? <><dl className="resource-definition"><div><dt>Zieltyp</dt><dd>{control.binding.target.kind}</dd></div><div><dt>Benötigter Nachweistyp</dt><dd>{control.binding.requiredEvidence.capability}</dd></div></dl><details><summary>Prüflogik anzeigen</summary><pre className="pack-json">{JSON.stringify(control.binding.assertions, null, 2)}</pre></details></> : <p>Keine automatisierte Prüfmethode definiert. Das Control bleibt im Katalog erhalten.</p>}
        {control.parameters.length > 0 && <details><summary>Parameter</summary><pre className="pack-json">{JSON.stringify(control.parameters, null, 2)}</pre></details>}
        <p><a href={requirementUrl}>Anforderung in Git</a>{resource.resolved.bindingPath && <>{' · '}<a href={resource.source.files.find((file) => file.path === resource.resolved.bindingPath)?.url}>Prüfbindungen in Git</a></>}</p>
      </details>)}
      {children.map((child) => groupView(child, group.key === '$root' ? 0 : depth + 1))}
    </section>;
  }
  return <div key={resource.id || resource.contentDigest} className="resource-controls">
    <label className="field">Controls suchen<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
    {controls.length === 0 ? search ? <p>Keine Controls für diese Suche. <button type="button" onClick={() => setSearch('')}>Suche zurücksetzen</button></p> : <p>Der Katalog enthält keine Controls.</p> : resource.resolved.groups.filter((group) => group.parent === null).map((group) => groupView(group, 0))}
  </div>;
}

/** @param {{organizationId: string, organization?: {ownerPrincipalId?: string}, accessToken?: string, resourceType?: 'Catalog' | 'Profile' | 'Product' | 'EvidenceProviderPack', onBusyChange: (busy: boolean) => void}} props */
export function ResourceWorkspace({ organizationId, organization, accessToken = '', resourceType = 'Catalog', onBusyChange }) {
  const isProfile = resourceType === 'Profile';
  const isProduct = resourceType === 'Product';
  const isEvidence = resourceType === 'EvidenceProviderPack';
  const plural = isEvidence ? 'Evidence Packs' : isProduct ? 'Produkte' : isProfile ? 'Profile' : 'Kataloge';
  const noun = isEvidence ? 'Evidence Pack' : isProduct ? 'Produkt' : isProfile ? 'Profil' : 'Katalog';
  const description = isEvidence ? 'Ein Evidence Pack beschreibt versionierte Capabilities und ihre Datenverträge. Die Registrierung erteilt keine Ausführungsrechte.' : isProduct ? 'Das Produktmanifest definiert die Produktquellen und die genaue geltende Profilversion.' : isProfile ? 'Profile wählen Controls und Parameter aus einem Katalog.' : 'Gruppierte Anforderungen und ihre gespeicherten Quellen.';
  const defaultPath = isEvidence ? 'provider.yaml' : isProduct ? 'products/audio-visualizer.json' : isProfile ? 'profiles/application-baseline.json' : 'catalogs/application.json';
  const selected = new URLSearchParams(location.search).get('resource') || '';
  const view = (isProduct || isEvidence) ? 'connect' : new URLSearchParams(location.search).get('view') || (selected ? 'detail' : 'list');
  const scope = `${organizationId}:${accessToken}:${resourceType}`;
  const root = `/api/organizations/${encodeURIComponent(organizationId)}/resources`;
  const listUrl = `${isEvidence ? '/evidence-packs' : isProduct ? '/products' : isProfile ? '/profiles' : '/catalogs'}?${new URLSearchParams({ organization: organizationId })}`;
  const [state, setState] = useState(/** @type {{scope: string, resources: Resource[], principal: {id: string, kind: string} | null, error: string}} */ ({ scope: '', resources: [], principal: null, error: '' }));
  const [repository, setRepository] = useState('');
  const [ref, setRef] = useState('main');
  const [refType, setRefType] = useState('branch');
  const [path, setPath] = useState(defaultPath);
  const [expectedId, setExpectedId] = useState('');
  const [version, setVersion] = useState('1.0.0');
  const [busy, setBusy] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [failure, setFailure] = useState('');
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [previewState, setPreviewState] = useState(/** @type {{key: string, value: Resource} | null} */ (null));
  const controller = useRef(/** @type {AbortController | null} */ (null));
  const configKey = JSON.stringify([scope, repository, ref, refType, path, expectedId, version]);
  const preview = previewState?.key === configKey ? previewState.value : null;
  const allResources = state.scope === scope ? state.resources : [];
  const resources = allResources.filter((item) => item.resourceType === resourceType && item.state !== 'archived');
  const archivedCatalogs = allResources.filter((item) => item.resourceType === 'Catalog' && item.state === 'archived');
  const loading = state.scope !== scope;
  const principal = state.scope === scope ? state.principal : null;
  const isOwner = principal?.kind === 'user' && principal.id === organization?.ownerPrincipalId;
  const resource = allResources.find((item) => item.resourceType === resourceType && item.id === selected);
  const usingProfiles = resource ? allResources.filter((item) => item.resourceType === 'Profile' && item.resolved.catalog?.resourceId === resource.resourceId && item.resolved.catalog.version === resource.version && item.resolved.catalog.contentDigest === resource.contentDigest) : [];
  /** @type {Record<string, string>} */ const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : {};

  useEffect(() => { onBusyChange(busy); return () => onBusyChange(false); }, [busy, onBusyChange]);
  useEffect(() => () => { controller.current?.abort(); controller.current = null; setBusy(false); }, [scope]);
  useEffect(() => {
    const readController = new AbortController();
    /** @type {RequestInit} */ const options = { signal: readController.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} };
    Promise.all([fetch(resourceType === 'Catalog' ? `${root}?include_archived=true` : root, options), fetch('/api/auth/me', options)]).then(async ([response, me]) => {
      if (!response.ok || !me.ok) throw new Error(response.status === 403 ? 'Für diese Ressourcen fehlen die erforderlichen Rechte.' : 'Ressourcen konnten nicht geladen werden.');
      const [items, current] = await Promise.all([response.json(), me.json()]);
      if (!readController.signal.aborted) setState({ scope, resources: items, principal: current, error: '' });
    }).catch((error) => { if (!readController.signal.aborted) setState({ scope, resources: [], principal: null, error: error.message }); });
    return () => readController.abort();
  }, [root, accessToken, scope, resourceType]);

  /** @param {boolean} archived */
  async function changeCatalogArchive(archived) {
    if (!isOwner || busy || resource?.resourceType !== 'Catalog') return;
    const current = new AbortController(); controller.current = current;
    setBusy(true); setPreviewBusy(false); setFailure('');
    const timeout = setTimeout(() => current.abort(), 45000);
    try {
      const response = await fetch(`${root}/${encodeURIComponent(resource.id || '')}${archived ? '' : '/restore'}`, { method: archived ? 'DELETE' : 'POST', headers, signal: current.signal });
      if (!response.ok) throw new Error(response.status === 403 ? 'Für diese Aktion fehlen die erforderlichen Rechte.' : 'Der Katalog konnte nicht geändert werden. Bitte erneut versuchen.');
      const saved = archived ? { ...resource, state: 'archived' } : await response.json();
      if (!current.signal.aborted) {
        setState((previous) => previous.scope === scope ? { ...previous, resources: previous.resources.map((item) => item.id === saved.id ? saved : item) } : previous);
        setConfirmRemove(false);
      }
    } catch (error) {
      if (controller.current === current) setFailure(current.signal.aborted ? 'Zeitlimit erreicht. Bitte die Seite neu laden und den Katalogstatus prüfen.' : error instanceof Error ? error.message : 'Der Katalog konnte nicht geändert werden.');
    } finally {
      clearTimeout(timeout);
      if (controller.current === current) setBusy(false);
    }
  }

  /** @param {boolean} previewOnly */
  async function submit(previewOnly) {
    if (!isOwner) return;
    controller.current?.abort();
    const current = new AbortController(); controller.current = current;
    setBusy(true); setPreviewBusy(previewOnly); setFailure('');
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; current.abort(); }, 45000);
    const config = { apiVersion: 'specbound.example/v1alpha1', kind: 'ResourceSource', metadata: { id: isEvidence ? 'evidence-source' : expectedId.trim(), version: isEvidence ? '1.0.0' : version.trim(), name: expectedId.trim() }, spec: { resourceType, provider: 'github', repository: repository.trim(), ref: ref.trim(), refType, manifestPath: path.trim() || defaultPath, expected: { id: expectedId.trim(), version: version.trim() } } };
    try {
      const response = await fetch(`${root}?preview=${previewOnly}`, { method: 'POST', signal: current.signal, headers: { ...headers, 'Content-Type': 'application/json', ...(!previewOnly && preview ? { 'X-Expected-Commit': preview.source.commit } : {}) }, body: JSON.stringify(config) });
      if (!response.ok) {
        const messages = { 403: 'Für diese Aktion fehlen die erforderlichen Rechte.', 409: 'Die Quelle hat sich verändert oder ID und Version bezeichnen andere Inhalte. Prüfe die Quelle erneut oder veröffentliche eine neue Version.', 422: 'Manifest, Prüfbindungen oder Referenzen sind ungültig oder noch nicht unterstützt. Prüfe auch die erwartete ID und Version.', 503: 'Die Git-Quelle ist nicht verfügbar oder nicht konfiguriert.', 504: 'Zeitlimit beim Lesen der Git-Quelle erreicht. Bitte erneut versuchen.' };
        const body = await response.json().catch(() => ({}));
        if (response.status === 409 && typeof body.detail === 'string' && body.detail.startsWith('Catalog is archived;')) throw new Error('Dieser Katalog ist archiviert. Stelle ihn unter „Entfernte Kataloge“ wieder her.');
        const detail = typeof body.detail === 'string' ? ` ${body.detail}` : '';
        throw new Error((messages[/** @type {403 | 409 | 422 | 503 | 504} */ (response.status)] || 'Die Quelle konnte nicht verarbeitet werden.') + detail);
      }
      /** @type {Resource} */ const saved = await response.json();
      if (current.signal.aborted) return;
      if (previewOnly) setPreviewState({ key: configKey, value: saved });
      else window.location.assign(isEvidence ? `${listUrl}&pack=${encodeURIComponent(saved.id || '')}` : isProduct ? `${listUrl}&product=${encodeURIComponent(saved.resolved.productId || '')}&view=scope` : `${listUrl}&resource=${encodeURIComponent(saved.id || '')}`);
    } catch (error) {
      if (controller.current === current) {
        if (timedOut) setFailure(previewOnly ? 'Zeitlimit beim Lesen der Quelle erreicht. Bitte erneut versuchen.' : 'Zeitlimit der Registrierung erreicht. Bitte zuerst in der Ressourcenliste prüfen, ob die Registrierung bereits abgeschlossen wurde.');
        else if (!current.signal.aborted) setFailure(error instanceof Error ? error.message : 'Die Quelle konnte nicht verarbeitet werden.');
      }
    } finally {
      clearTimeout(timeout);
      if (controller.current === current) setBusy(false);
    }
  }

  function cancel() {
    if (!previewBusy) return;
    controller.current?.abort(); controller.current = null;
    setBusy(false); setFailure('');
  }

  return <section className="resource-workspace" aria-labelledby="resources-heading">
    {(failure || (state.scope === scope && state.error)) && <p role="alert" className="alert">{failure || state.error}</p>}
    {loading ? <p role="status">{plural} werden geladen …</p> : state.error ? null : view === 'connect' ? <>
      <h1 id="resources-heading">{noun}quelle konfigurieren</h1><p>{description}</p>
      {isOwner ? <form className="panel resource-source-form" onSubmit={(event) => { event.preventDefault(); void submit(false); }}>
        <label className="field">Repository<input required maxLength={200} value={repository} onChange={(event) => setRepository(event.target.value)} placeholder="owner/repository" /></label>
        <label className="field">Git-Ref<input required maxLength={200} value={ref} onChange={(event) => setRef(event.target.value)} /></label>
        <ManifestSourceFields path={path} onPath={setPath} refType={refType} onRefType={setRefType} defaultPath={defaultPath} />
        <label className="field">Erwartete {noun}-ID<input required maxLength={isEvidence ? 200 : 128} value={expectedId} onChange={(event) => setExpectedId(event.target.value)} placeholder={isEvidence ? 'org.example.provider' : isProduct ? 'audio-visualizer' : isProfile ? 'application-baseline' : 'application-controls'} /></label>
        <label className="field">Erwartete Version<input required value={version} onChange={(event) => setVersion(event.target.value)} maxLength={isEvidence ? undefined : 128} /></label>
        <div className="resource-actions"><button type="button" disabled={busy || !repository.trim() || !expectedId.trim()} onClick={() => { void submit(true); }}>Vorschau prüfen</button><button type="submit" disabled={busy}>{noun} registrieren</button>{busy && previewBusy && <button type="button" onClick={cancel}>Abbrechen</button>}</div>
        {busy && <p role="status">Quelle wird gelesen und geprüft …</p>}
        <p>Der Import prüft die Struktur und speichert eine feste Revision. Ein Produktprofil legt die geltenden Controls fest.</p>
      </form> : <p>Nur Organisationseigentümer können neue Quellen registrieren.</p>}
      {preview && <section className="panel" aria-label={`${noun}vorschau`}><h2>Vorschau · {preview.name}</h2><p>Struktur geprüft · noch nicht registriert</p><ManifestProvenance source={preview.source} defaultPath={preview.source.manifestPath} />{isEvidence ? <p>{preview.resolved.capabilities?.map((item) => `${item.id}/${item.version}`).join(', ')} · Struktur geprüft, keine Ausführungsfreigabe</p> : isProduct ? <><p>{preview.resolved.controls.length} geltende Controls aus {preview.resolved.profile?.name} · {preview.resolved.profile?.version}</p><p>Produktquellen: {preview.resolved.repositories?.map((item) => item.repository).join(', ')}</p></> : <CatalogControls key={preview.contentDigest} resource={preview} />}</section>}
      <a href={listUrl}>Zu den {plural}</a>
    </> : selected ? resource ? <>
      <div className="page-heading"><div><h1 id="resources-heading">{resource.name}</h1><p>{resource.resourceId} · Version {resource.version} · {resource.state === 'archived' ? 'Archiviert' : 'Registriert'} · Struktur geprüft</p></div><a href={listUrl}>Alle {plural}</a></div>
      {resourceType === 'Catalog' && (isOwner || resource.state === 'archived') && <section className="panel" aria-label="Katalogregistrierung">
        {resource.state === 'archived' ? <><p role="status">Dieser Katalog wurde aus der aktiven Liste entfernt. Bestehende Profile und Prüfungen behalten ihre feste Referenz.</p>{isOwner && <button type="button" disabled={busy} onClick={() => { void changeCatalogArchive(false); }}>Katalog wiederherstellen</button>}</> : isOwner && (confirmRemove ? <><h2>Katalog entfernen?</h2><p>Diese registrierte Revision wird archiviert. Bestehende Profile, Prüfungen und Quellenlinks bleiben erhalten. Du kannst den Katalog später wiederherstellen.</p><div className="resource-actions"><button type="button" disabled={busy} onClick={() => { void changeCatalogArchive(true); }}>Entfernen bestätigen</button><button type="button" disabled={busy} onClick={() => setConfirmRemove(false)}>Abbrechen</button></div></> : <button type="button" disabled={busy} onClick={() => setConfirmRemove(true)}>Katalog entfernen</button>)}
        {busy && <p role="status">Katalogregistrierung wird geändert …</p>}
      </section>}
      <ManifestProvenance source={resource.source} defaultPath={resource.source.manifestPath} />
      {resource.state !== 'archived' && <ResourceRevisions key={`revision-${resource.id}`} organizationId={organizationId} revisionId={resource.id || ''} accessToken={accessToken} isOwner={isOwner} />}
      {resource.resolved.catalog && <p>Katalogdefinition: <a href={`/catalogs?${new URLSearchParams({ organization: organizationId, resource: resource.resolved.catalog.revisionId })}`}>{resource.resolved.catalog.name} · {resource.resolved.catalog.version}</a>{' · '}<a href={resource.source.files.find((file) => file.path === resource.resolved.catalog?.manifestPath)?.url}>Eingebundene Katalogdatei</a></p>}
      <p>{resource.resolved.controls.length} Controls · Produktgeltung durch ausdrückliche Profilauswahl.</p>
      <CatalogControls key={resource.id} resource={resource} />
      {!isProfile && <section className="panel"><h2>Verwendet in Profilen</h2>{usingProfiles.length ? <ul>{usingProfiles.map((profile) => <li key={profile.id}><a href={`/profiles?${new URLSearchParams({ organization: organizationId, resource: profile.id || '' })}`}>{profile.name} · {profile.version}</a></li>)}</ul> : <p>Noch keine gespeicherten Profile für diese Katalogversion.</p>}</section>}
      <CapabilityUsage key={`capability-${resource.id}`} organizationId={organizationId} accessToken={accessToken} resourceId={resource.id} /><details className="panel"><summary>Manifest und Quellen</summary><pre className="pack-json">{JSON.stringify(resource.manifest, null, 2)}</pre><ul>{resource.source.files.map((file) => <li key={file.path}><a href={file.url}>{file.path}</a></li>)}</ul><p className="break-value">Quelldigest (SHA-256): {resource.contentDigest}</p></details>
    </> : <><h1 id="resources-heading">{noun} nicht verfügbar</h1><p>Die Revision existiert nicht oder ist für dich nicht sichtbar.</p><a href={listUrl}>Alle {plural}</a></> : <>
      <div className="page-heading"><div><h1 id="resources-heading">{plural}</h1><p>{description}</p></div>{isOwner && <a className="primary-link" href={`${listUrl}&view=connect`}>{noun} registrieren</a>}</div>
      {resources.length ? <div className="resource-product-grid">{resources.map((item) => <article className="panel" key={item.id}><h2><a href={`${listUrl}&resource=${encodeURIComponent(item.id || '')}`}>{item.name}</a></h2><p className="break-value">{item.resourceId} · Version {item.version}</p><p>{item.resolved.controls.length} Controls · Registriert · Struktur geprüft</p><p className="break-value">Repository: <a href={`https://github.com/${item.source.repository}`}>{item.source.repository}</a></p><ManifestProvenance source={item.source} defaultPath={item.source.manifestPath} /></article>)}</div> : <p>Noch keine nativen {plural} registriert.</p>}
      {resourceType === 'Catalog' && archivedCatalogs.length > 0 && <details className="panel"><summary>Entfernte Kataloge ({archivedCatalogs.length})</summary><ul>{archivedCatalogs.map((item) => <li key={item.id}><a href={`${listUrl}&resource=${encodeURIComponent(item.id || '')}`}>{item.name} · {item.version}</a></li>)}</ul></details>}
      {!isProfile && <p><a href={`/packs?${new URLSearchParams({ organization: organizationId })}`}>Bestehende Governance-Packs ansehen</a></p>}
    </>}
  </section>;
}
