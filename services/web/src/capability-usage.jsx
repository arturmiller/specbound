import React, { useEffect, useState } from 'react';

/** @typedef {{revisionId: string, resourceType: string, resourceId: string, version: string, name: string, controlId: string, capability: string, status: string, providerRevisionIds: string[], incompatibleProviderRevisionIds: string[]}} Usage */
/** @param {{organizationId: string, accessToken: string, resourceId?: string | null, packId?: string}} props */
export function CapabilityUsage({ organizationId, accessToken, resourceId, packId }) {
  const scope = `${organizationId}:${accessToken}`;
  const [state, setState] = useState(/** @type {{scope: string, controls: Usage[], providers: {revisionId: string, name: string, version: string}[], error: string}} */ ({ scope: '', controls: [], providers: [], error: '' }));
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/organizations/${encodeURIComponent(organizationId)}/evidence-pack-usage`, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then(async (response) => { if (!response.ok) throw new Error('Capability-Zuordnungen konnten nicht geladen werden.'); return response.json(); })
      .then((value) => { if (!controller.signal.aborted) setState({ scope, controls: value.controls || [], providers: value.providers || [], error: '' }); })
      .catch((failure) => { if (!controller.signal.aborted) setState({ scope, controls: [], providers: [], error: failure.message }); });
    return () => controller.abort();
  }, [organizationId, accessToken, scope]);
  const controls = state.controls.filter((item) => resourceId ? item.revisionId === resourceId : packId ? item.providerRevisionIds.includes(packId) || item.incompatibleProviderRevisionIds.includes(packId) : true);
  return <section className="panel" aria-label="Capability-Zuordnung"><h2>{packId ? 'Verwendung durch Controls' : 'Benötigte Nachweise und Anbieter'}</h2>
    {state.scope !== scope ? <p role="status">Zuordnungen werden geladen …</p> : state.error ? <p role="alert">{state.error}</p> : controls.length === 0 ? <p>Keine gespeicherten Control-Bindungen für diese Auswahl.</p> : <ul>{controls.map((item) => <li key={`${item.revisionId}:${item.controlId}`}>
      <a href={`/${item.resourceType === 'Profile' ? 'profiles' : 'catalogs'}?${new URLSearchParams({ organization: organizationId, resource: item.revisionId })}`}>{item.name} · {item.version} · {item.controlId}</a>
      <p className="break-value">{item.capability} · {item.status === 'available' ? 'Passende Capability registriert' : item.status === 'incompatible_version' ? 'Keine passende Version; andere Version registriert' : 'Kein passender Anbieter registriert'}</p>
      {item.providerRevisionIds.map((id) => { const provider = state.providers.find((value) => value.revisionId === id); return <p key={id}><a href={`/evidence-packs?${new URLSearchParams({ organization: organizationId, pack: id })}`}>{provider?.name || id} · {provider?.version}</a></p>; })}
    </li>)}</ul>}
    <p>Der Abgleich prüft die genaue Capability-Version. Eine registrierte Capability belegt weder eine Ausführungsfreigabe noch einen erhobenen Nachweis.</p>
  </section>;
}

/** @param {{pack: import('./provider-packs.jsx').ProviderPack}} props */
export function PackContracts({ pack }) {
  const directory = (pack.manifestPath || 'provider.yaml').split('/').slice(0, -1);
  /** @param {string} path */
  const fileUrl = (path) => `https://github.com/${pack.repository}/blob/${pack.commit}/${[...directory, ...path.split('/')].map(encodeURIComponent).join('/')}`;
  const contracts = [...new Set([pack.manifest.runtime.input, pack.manifest.runtime.output, ...pack.manifest.capabilities.map((item) => item.outputSchema)])];
  return <section className="panel" aria-label="Datenverträge und Berechtigungen"><h2>Datenverträge und Berechtigungen</h2>
    <p>Registrierung: gespeichert · Struktur: validiert</p><p>Allgemeine Ausführungsfreigabe: nicht verfügbar (separater Freigabeprozess).</p>
    <p className="break-value">Deklariertes Image: {pack.manifest.runtime.image}</p>
    <details><summary>Deklarierte Berechtigungen</summary><pre className="pack-json">{JSON.stringify(pack.manifest.permissions || {}, null, 2)}</pre></details>
    {contracts.map((path) => <details key={path}><summary className="break-value">{path}</summary><a href={fileUrl(path)}>Datei in Git</a>{pack.schemas?.[path] ? <pre className="pack-json">{JSON.stringify(pack.schemas[path], null, 2)}</pre> : <p>Für diese historische Revision wurde kein Schema gespeichert.</p>}</details>)}
    <p>Öffentliche Python-Lizenzscans werden vom öffentlichen Scanner erzeugt. Synthetische Provider-Tests sind gesonderte Testläufe; der Import erzeugt keine Evidence.</p>
  </section>;
}
