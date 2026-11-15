import React, { useEffect, useState } from 'react';
import { ProviderTestRuns } from './provider-test-runs.jsx';

/** @typedef {{id: string, version: string, outputSchema: string}} Capability */
/** @typedef {{id: string, repository: string, tag: string, commit: string, kind: string, manifest: {metadata: {id: string, version: string, title?: string}, runtime: {kind: string, image: string, input: string, output: string}, capabilities: Capability[], tests?: string[]}}} ProviderPack */
/** @typedef {{id: string, ownerPrincipalId?: string}} Organization */

/** @param {string} org @param {string} [pack] @param {string} [view] @param {string} [capability] */
function providerUrl(org, pack = '', view = '', capability = '') {
  const params = new URLSearchParams({ organization: org });
  if (pack) params.set('pack', pack);
  if (view) params.set('view', view);
  if (capability) params.set('capability', capability);
  return `/providers?${params}`;
}

/** @param {{organizationId: string, organization?: Organization, accessToken?: string, onBusyChange: (busy: boolean) => void}} props */
export function ProviderPacks({ organizationId, organization, accessToken = '', onBusyChange }) {
  const params = new URLSearchParams(window.location.search);
  const selected = params.get('pack') || '';
  const view = params.get('view') || (selected ? 'manifest' : 'directory');
  const selectedCapability = params.get('capability') || '';
  const [packs, setPacks] = useState(/** @type {ProviderPack[]} */ ([]));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [principal, setPrincipal] = useState(/** @type {{id: string, kind: string} | null} */ (null));
  const [permissionError, setPermissionError] = useState('');
  const [repository, setRepository] = useState('');
  const [tag, setTag] = useState('');
  const [busy, setBusy] = useState(false);
  const root = `/api/organizations/${encodeURIComponent(organizationId)}/packs`;
  /** @type {Record<string, string>} */ const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
  const isOwner = Boolean(principal?.kind === 'user' && principal.id === organization?.ownerPrincipalId);
  const pack = packs.find((item) => item.id === selected);
  const capability = selectedCapability ? pack?.manifest.capabilities.find((item) => `${item.id}/${item.version}` === selectedCapability) : pack?.manifest.capabilities[0];
  const catalogUrl = providerUrl(organizationId, '', 'catalog');
  const directoryUrl = providerUrl(organizationId);
  const evidenceUrl = `/evidence?${new URLSearchParams({ organization: organizationId })}`;

  useEffect(() => { onBusyChange(busy); return () => onBusyChange(false); }, [busy, onBusyChange]);
  useEffect(() => {
    const controller = new AbortController();
    fetch(root, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then((response) => { if (!response.ok) throw new Error(response.status === 403 ? 'Für diesen Katalog fehlen die erforderlichen Rechte.' : 'Provider-Packs konnten nicht geladen werden.'); return response.json(); })
      .then((/** @type {ProviderPack[]} */ data) => setPacks(data.filter((item) => item.kind === 'provider')))
      .catch((failure) => { if (!controller.signal.aborted) setError(failure.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    fetch('/api/auth/me', { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then((response) => { if (!response.ok) throw new Error(); return response.json(); }).then(setPrincipal)
      .catch(() => { if (!controller.signal.aborted) setPermissionError('Berechtigungen konnten nicht geladen werden.'); });
    return () => controller.abort();
  }, [root, accessToken]);

  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function connect(event) {
    event.preventDefault();
    if (!isOwner || !repository.trim() || !tag.trim()) return;
    setBusy(true); setError('');
    try {
      const response = await fetch(root, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify({ repository: repository.trim(), tag: tag.trim(), kind: 'provider' }) });
      if (!response.ok) {
        const messages = { 403: 'Für diese Aktion fehlen die erforderlichen Rechte.', 409: 'Der Tag wurde verschoben oder gehört zu einem anderen Pack-Typ.', 422: 'Provider-Manifest, Schema oder Repository ist ungültig.', 503: 'Die Git-Quelle ist nicht verfügbar oder nicht konfiguriert.' };
        throw new Error(messages[/** @type {403 | 409 | 422 | 503} */ (response.status)] || 'Provider-Pack konnte nicht verbunden werden.');
      }
      /** @type {ProviderPack} */ const saved = await response.json();
      window.location.assign(providerUrl(organizationId, saved.id));
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Provider-Pack konnte nicht verbunden werden.'); setBusy(false); }
  }

  return <section className="provider-screen" aria-labelledby="providers-heading">
    {error && <p className="alert" role="alert">{error}</p>}{permissionError && <p className="alert" role="alert">{permissionError}</p>}
    {loading ? <p role="status">Provider-Packs werden geladen …</p> : error && view !== 'connect' ? null : view === 'directory' ? <>
      <p className="eyebrow">PLATTFORM / PROVIDER</p><div className="page-heading"><div><h1 id="providers-heading">Evidence Provider</h1><p>Deklarierte Provider-Releases und ihre Capabilities.</p></div><a className="primary-link" href={catalogUrl}>Provider-Packs ansehen →</a></div>
      <div className="team-metrics team-detail-metrics"><div className="panel"><span>Registrierte Pack-Revisionen</span><strong>{packs.length}</strong></div><div className="panel"><span>Deklarierte Capabilities</span><strong>{packs.reduce((sum, item) => sum + item.manifest.capabilities.length, 0)}</strong></div><div className="panel"><span>Betriebszustand</span><strong>UNKNOWN</strong></div><div className="panel"><span>Letzter Healthcheck</span><strong>UNKNOWN</strong></div></div>
      <div className="panel team-table-panel"><h2>Provider-Verzeichnis</h2>{packs.length === 0 ? <p className="product-empty">Noch keine Provider-Packs verbunden.</p> : <><p className="pack-scroll-hint">Tabelle horizontal scrollen, um alle Spalten zu sehen.</p><div className="team-table-scroll" tabIndex={0} aria-label="Provider-Verzeichnis, horizontal scrollbar"><table className="team-table"><thead><tr><th>PROVIDER-RELEASE</th><th>CAPABILITIES</th><th>RUNTIME</th><th>HEALTH</th></tr></thead><tbody>{packs.map((item) => <tr key={item.id}><td><a href={providerUrl(organizationId, item.id, 'provider')}>{item.manifest.metadata.title || item.manifest.metadata.id}</a><small>{item.repository} · {item.tag}</small></td><td>{item.manifest.capabilities.map((cap) => `${cap.id}/${cap.version}`).join(', ') || 'Keine'}</td><td>{item.manifest.runtime.kind} · deklariert</td><td>UNKNOWN</td></tr>)}</tbody></table></div></>}</div>
      <div className="team-info">Ein importiertes Pack beschreibt eine Runtime; es belegt keinen laufenden, freigegebenen oder fehlerfreien Provider.</div>
    </> : view === 'catalog' ? <>
      <p className="eyebrow">PLATTFORM / ERWEITERUNGEN</p><div className="page-heading"><div><h1 id="providers-heading">Evidence Provider Packs</h1><p>Git-Releases beschreiben Capabilities; Evidence entsteht separat bei einer Ausführung.</p></div>{isOwner && <a className="primary-link" href={providerUrl(organizationId, '', 'connect')}>+ Git-Repository verbinden</a>}</div>
      <div className="team-metrics team-detail-metrics"><div className="panel"><span>Verbundene Provider-Packs</span><strong>{packs.length}</strong></div><div className="panel"><span>Deklarierte Capabilities</span><strong>{packs.reduce((sum, item) => sum + item.manifest.capabilities.length, 0)}</strong></div><div className="panel"><span>Capability-Abgleich</span><strong>Nicht verfügbar</strong></div><div className="panel"><span>Betriebszustand</span><strong>Nicht verfügbar</strong></div></div>
      <div className="panel team-table-panel"><h2>Provider-Packs</h2>{packs.length === 0 ? <p className="product-empty">Noch keine Provider-Packs verbunden.</p> : <><p className="pack-scroll-hint">Tabelle horizontal scrollen, um alle Spalten zu sehen.</p><div className="team-table-scroll" tabIndex={0} aria-label="Provider-Packs, horizontal scrollbar"><table className="team-table"><thead><tr><th>PROVIDER PACK</th><th>GIT-REPOSITORY</th><th>RELEASE</th><th>CAPABILITIES</th><th>RUNTIME</th></tr></thead><tbody>{packs.map((item) => <tr key={item.id}><td><a href={providerUrl(organizationId, item.id)}>{item.manifest.metadata.title || item.manifest.metadata.id}</a><small>{item.manifest.metadata.id}</small></td><td className="break-value">{item.repository}</td><td>{item.tag}</td><td>{item.manifest.capabilities.map((cap) => `${cap.id}/${cap.version}`).join(', ') || 'Keine'}</td><td>{item.manifest.runtime.kind}</td></tr>)}</tbody></table></div></>}</div>
      <div className="team-columns product-summary"><div className="panel"><h2>Pack-Kategorien</h2><dl className="team-role-list"><div><dt>Governance-Pack</dt><dd>Definiert Kontrollen</dd></div><div><dt>Provider-Pack</dt><dd>Deklariert Capabilities</dd></div><div><dt>Observation</dt><dd>Gespeicherte Evidence</dd></div></dl></div><div className="panel"><h2>Getrennte Verantwortung</h2><p>Ein Pack beschreibt Schnittstellen. Sein Import startet keine Ausführung und erteilt keine Berechtigungen.</p></div></div>
    </> : view === 'connect' ? <>
      <p className="eyebrow">PROVIDER / GIT VERBINDEN</p><div className="page-heading"><div><h1 id="providers-heading">Evidence Provider Pack verbinden</h1><p>Ein Release auf eine feste Git-Revision auflösen und validieren.</p></div></div>
      <ol className="team-steps" aria-label="Provider-Pack-Verbindung"><li aria-current="step"><span>1</span>Repository verbinden</li><li><span>2</span>Manifest prüfen</li><li><span>3</span>Vertrag ansehen</li></ol>
      <div className="team-columns"><div className="panel"><h2>Quelle in Git</h2>{principal === null && !permissionError ? <p role="status">Berechtigungen werden geladen …</p> : isOwner ? <form onSubmit={connect}><label className="field">Repository<input value={repository} onChange={(event) => setRepository(event.target.value)} required maxLength={200} placeholder="owner/repository" /></label><label className="field">Release-Tag<input value={tag} onChange={(event) => setTag(event.target.value)} required maxLength={200} placeholder="v1.0.0" /></label><button type="submit" disabled={busy}>Provider-Pack verbinden</button></form> : <p>Nur Organisationseigentümer können Provider-Packs verbinden.</p>}<div className="team-info">Manifest und referenzierte Schemata werden beim Import validiert und der Commit wird gepinnt.</div></div>
        <div className="panel"><h2>Grenzen des Imports</h2><p>Der Import ist keine Ausführungsfreigabe. Zugangsdaten, Collector-Rechte und externe Dienste werden dadurch nicht eingerichtet.</p><p>Signaturen und Tag-Schutz werden hier nicht geprüft. Schema- und Fixture-Inhalte werden im Katalog nicht gespeichert.</p></div></div><a className="team-back" href={catalogUrl}>← Zurück zum Provider-Katalog</a>
    </> : !pack ? <><h1 id="providers-heading">Provider-Pack nicht verfügbar</h1><p>Die Revision existiert nicht oder ist für dich nicht sichtbar.</p><a href={catalogUrl}>Zum Provider-Katalog</a></> : view === 'provider' ? <>
      <p className="eyebrow">PROVIDER / DETAILS</p><div className="page-heading"><div><h1 id="providers-heading">{pack.manifest.metadata.title || pack.manifest.metadata.id}</h1><p>Deklaration aus {pack.repository} · {pack.tag}.</p></div></div>
      <div className="team-metrics team-detail-metrics"><div className="panel"><span>Version</span><strong>{pack.manifest.metadata.version}</strong></div><div className="panel"><span>Runtime-Deklaration</span><strong>{pack.manifest.runtime.kind}</strong></div><div className="panel"><span>Letzter Erfolg</span><strong>UNKNOWN</strong></div><div className="panel"><span>Vertrauensstatus</span><strong>UNKNOWN</strong></div></div>
      <div className="team-columns"><div className="panel"><h2>Deklarierte Capabilities</h2>{pack.manifest.capabilities.length ? <ul>{pack.manifest.capabilities.map((item) => <li key={`${item.id}/${item.version}`}><a href={providerUrl(organizationId, pack.id, 'contract', `${item.id}/${item.version}`)}>{item.id}/{item.version}</a></li>)}</ul> : <p>Keine Capabilities deklariert.</p>}<h2>Runtime und Zugriff</h2><p className="break-value">Image-Deklaration: {pack.manifest.runtime.image}</p><p>Ausführungsfreigabe und Zugangsdaten: UNKNOWN.</p><a href={providerUrl(organizationId, pack.id)}>Manifest ansehen →</a></div><div className="panel"><h2>Abdeckung und Zustand</h2><p>Healthchecks, verbundene Umgebungen und Zuordnungen sind nicht verfügbar.</p><div className="team-info">Fehlende Provider-Daten sind UNKNOWN und kein erfolgreicher Nachweis.</div><p><a href={evidenceUrl}>Evidence-Register öffnen →</a></p></div></div><a className="team-back" href={directoryUrl}>← Zurück zum Provider-Verzeichnis</a>
    </> : view === 'contract' ? <>
      <p className="eyebrow">PROVIDER / CAPABILITY</p><div className="page-heading"><div><h1 id="providers-heading">Capability-Vertrag und Testreferenzen</h1><p>Deklarierte Pfade aus dem validierten Provider-Manifest.</p></div></div>
      <ProviderSteps active={2} /><div className="discovery-columns"><div className="panel"><h2>Capability-Schema</h2>{capability ? <><p><strong>{capability.id}/{capability.version}</strong></p><p className="break-value">Schema-Referenz: {capability.outputSchema}</p><div className="provider-code">Schema-Inhalt im Katalog nicht gespeichert.</div></> : <p>{selectedCapability ? 'Diese Capability ist in der Revision nicht vorhanden.' : 'Keine Capability deklariert.'}</p>}</div>
        <div className="discovery-side"><div className="panel"><h2>Test-Fixtures</h2>{pack.manifest.tests?.length ? <ul>{pack.manifest.tests.map((test) => <li key={test} className="break-value">{test}</li>)}</ul> : <p>Keine Test-Fixtures deklariert.</p>}<p>Fixture-Inhalte und Testergebnisse sind im Katalog nicht gespeichert.</p></div><div className="panel"><h2>Herkunft</h2><p>{pack.repository} · {pack.tag}</p><p className="break-value">Gepinnter Commit: {pack.commit}</p><p>Ein validierter Vertrag ist keine Freigabe zur Ausführung.</p></div></div></div>
      <a className="team-back" href={providerUrl(organizationId, pack.id)}>← Zum Manifest</a>
    </> : <>
      <p className="eyebrow">PROVIDER / MANIFEST</p><div className="page-heading"><div><h1 id="providers-heading">Provider-Manifest</h1><p>Validierte Manifestdaten der gepinnten Revision.</p></div></div>
      <div className="pack-metrics"><div className="panel"><span>Pack</span><strong>{pack.manifest.metadata.id}</strong></div><div className="panel"><span>Repository</span><strong>{pack.repository}</strong></div><div className="panel"><span>Release</span><strong>{pack.tag}</strong></div><div className="panel"><span>Commit</span><strong>{pack.commit}</strong></div></div>
      <div className="discovery-columns"><div className="panel"><h2>provider.yaml · eingelesenes Manifest</h2><pre className="provider-code">{JSON.stringify(pack.manifest, null, 2)}</pre></div><div className="discovery-side"><div className="panel"><h2>Capability-Referenzen</h2>{pack.manifest.capabilities.length ? <ul>{pack.manifest.capabilities.map((item) => <li key={`${item.id}/${item.version}`}><a href={providerUrl(organizationId, pack.id, 'contract', `${item.id}/${item.version}`)}>{item.id}/{item.version}</a><p className="break-value">{item.outputSchema}</p></li>)}</ul> : <p>Keine Capability deklariert.</p>}</div><div className="panel"><h2>Runtime-Deklaration</h2><p>Typ: {pack.manifest.runtime.kind}</p><p className="break-value">Image: {pack.manifest.runtime.image}</p><p className="break-value">Input: {pack.manifest.runtime.input}</p><p className="break-value">Output: {pack.manifest.runtime.output}</p><p>Eine Deklaration bestätigt weder Freigabe noch Verfügbarkeit.</p></div></div></div><a className="team-back" href={catalogUrl}>← Zurück zum Provider-Katalog</a>
    </>}
    {pack && view === 'manifest' && pack.repository === 'arturmiller/specbound-example-provider' && pack.manifest.capabilities.some((item) => item.id === 'demo.fixture' && item.version === 'v1') && (principal ? <ProviderTestRuns key={pack.id} organizationId={organizationId} revisionId={pack.id} accessToken={accessToken} isOwner={isOwner} /> : !permissionError && <p role="status">Berechtigungen werden geladen …</p>)}
  </section>;
}

/** @param {{active: number}} props */
function ProviderSteps({ active }) {
  return <ol className="team-steps" aria-label="Provider-Vertrag">{['Provider-Manifest', 'Capability-Schema', 'Observation'].map((label, index) => <li key={label} aria-current={index + 1 === active ? 'step' : undefined}><span>{index + 1}</span>{label}</li>)}</ol>;
}
