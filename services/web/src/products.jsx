import React, { useEffect, useState } from 'react';
import { ProductDetail } from './product-detail.jsx';

/** @typedef {{id: string, name: string, ownerTeamId: string}} Product */
/** @typedef {{id: string, repository: string, provider: string}} Binding */
/** @typedef {{id: string, name: string}} Team */
/** @typedef {{principalId: string, role: string}} Member */
/** @typedef {{id: string, ownerPrincipalId?: string}} Organization */

/** @param {string} path @param {string} token @param {RequestInit} [options] */
async function request(path, token, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

/** @param {string} organization @param {string} [product] @param {string} [view] */
function productUrl(organization, product = '', view = '') {
  const params = new URLSearchParams({ organization });
  if (product) params.set('product', product);
  if (view) params.set('view', view);
  return `/products?${params}`;
}

/** @param {{organizationId: string, organization?: Organization, teams: Team[], teamsLoading: boolean, accessToken?: string, onBusyChange: (busy: boolean) => void}} props */
export function ProductWorkspace({ organizationId, organization, teams, teamsLoading, accessToken = '', onBusyChange }) {
  const params = new URLSearchParams(window.location.search);
  const productId = params.get('product') || '';
  const view = params.get('view') || (productId ? 'detail' : 'list');
  const [products, setProducts] = useState(/** @type {Product[]} */ ([]));
  const [ready, setReady] = useState(false);
  const [productError, setProductError] = useState('');
  const [principal, setPrincipal] = useState('');
  const [permissionsLoading, setPermissionsLoading] = useState(true);
  const [permissionsError, setPermissionsError] = useState('');
  const [teamRoles, setTeamRoles] = useState(/** @type {Record<string, string>} */ ({}));
  const [bindings, setBindings] = useState(/** @type {Binding[]} */ ([]));
  const [bindingsLoading, setBindingsLoading] = useState(false);
  const [bindingsError, setBindingsError] = useState('');
  const [name, setName] = useState('');
  const [ownerTeam, setOwnerTeam] = useState('');
  const [repository, setRepository] = useState('');
  const [verification, setVerification] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [teamFilter, setTeamFilter] = useState('');
  const product = products.find((item) => item.id === productId);

  useEffect(() => { onBusyChange(busy); return () => onBusyChange(false); }, [busy, onBusyChange]);

  useEffect(() => {
    const controller = new AbortController();
    request(`/organizations/${encodeURIComponent(organizationId)}/products`, accessToken, { signal: controller.signal })
      .then((/** @type {Product[]} */ data) => { setProducts(data); setReady(true); })
      .catch((failure) => { if (!controller.signal.aborted) setProductError(failure.message === 'HTTP 403' ? 'Für diese Produkte fehlen die erforderlichen Rechte.' : 'Produkte konnten nicht geladen werden.'); });
    return () => controller.abort();
  }, [organizationId, accessToken]);

  useEffect(() => {
    if (teamsLoading) return;
    const controller = new AbortController();
    setPermissionsLoading(true); setPermissionsError('');
    request('/auth/me', accessToken, { signal: controller.signal })
      .then(async (user) => {
        const entries = await Promise.all(teams.map(async (team) => {
          try {
            /** @type {Member[]} */ const members = await request(`/teams/${encodeURIComponent(team.id)}/members`, accessToken, { signal: controller.signal });
            return [team.id, members.find((member) => member.principalId === user.id)?.role || ''];
          } catch { return [team.id, '']; }
        }));
        if (!controller.signal.aborted) { setPrincipal(user.id); setTeamRoles(Object.fromEntries(entries)); }
      })
      .catch(() => { if (!controller.signal.aborted) setPermissionsError('Berechtigungen konnten nicht geladen werden.'); })
      .finally(() => { if (!controller.signal.aborted) setPermissionsLoading(false); });
    return () => controller.abort();
  }, [organizationId, teams, teamsLoading, accessToken]);

  const isOwner = Boolean(principal && !principal.startsWith('agent:') && principal === organization?.ownerPrincipalId);
  const editableTeams = teams.filter((team) => isOwner || Boolean(principal && !principal.startsWith('agent:') && ['admin', 'maintainer'].includes(teamRoles[team.id])));
  const canEditProduct = Boolean(product && editableTeams.some((team) => team.id === product.ownerTeamId));

  useEffect(() => {
    setOwnerTeam((current) => editableTeams.some((team) => team.id === current) ? current : (editableTeams[0]?.id || ''));
  }, [teams, principal, teamRoles, organization?.ownerPrincipalId]);

  useEffect(() => {
    setBindings([]); setBindingsError(''); setVerification('');
    if (!productId) { setBindingsLoading(false); return; }
    const controller = new AbortController();
    setBindingsLoading(true);
    request(`/products/${encodeURIComponent(productId)}/repositories`, accessToken, { signal: controller.signal })
      .then((/** @type {Binding[]} */ data) => setBindings(data))
      .catch((failure) => { if (!controller.signal.aborted) setBindingsError(failure.message === 'HTTP 403' ? 'Für diese Repositories fehlen die erforderlichen Rechte.' : 'Repositories konnten nicht geladen werden.'); })
      .finally(() => { if (!controller.signal.aborted) setBindingsLoading(false); });
    return () => controller.abort();
  }, [productId, accessToken]);

  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function createProduct(event) {
    event.preventDefault();
    if (!name.trim() || !editableTeams.some((team) => team.id === ownerTeam)) return;
    setBusy(true); setError('');
    try {
      /** @type {Product} */ const created = await request(`/organizations/${encodeURIComponent(organizationId)}/products`, accessToken, { method: 'POST', body: JSON.stringify({ name: name.trim(), ownerTeamId: ownerTeam }) });
      window.location.assign(productUrl(organizationId, created.id, 'repository'));
    } catch (failure) { setError(failure instanceof Error && failure.message === 'HTTP 403' ? 'Für diese Aktion fehlen die erforderlichen Rechte.' : 'Produkt konnte nicht erstellt werden.'); setBusy(false); }
  }

  /** @param {Binding} binding */
  async function verify(binding) {
    try {
      await request(`/products/${encodeURIComponent(productId)}/repositories/${encodeURIComponent(binding.id)}/github`, accessToken);
      setVerification(`${binding.repository}: GitHub-Zugriff bestätigt`);
    } catch { setVerification(`${binding.repository}: GitHub-Zugriff konnte nicht bestätigt werden. Das Repository bleibt gespeichert.`); }
  }

  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function connect(event) {
    event.preventDefault();
    if (!canEditProduct || !repository.trim() || bindingsLoading || bindingsError) return;
    setBusy(true); setError(''); setVerification('');
    try {
      /** @type {Binding} */ const binding = await request(`/products/${encodeURIComponent(productId)}/repositories`, accessToken, { method: 'POST', body: JSON.stringify({ provider: 'github', repository: repository.trim() }) });
      setBindings((current) => [...current, binding]); setRepository('');
      await verify(binding);
    } catch (failure) { setError(failure instanceof Error && failure.message === 'HTTP 403' ? 'Für diese Aktion fehlen die erforderlichen Rechte.' : 'Repository konnte nicht verbunden werden. Das Produkt bleibt gespeichert.'); }
    finally { setBusy(false); }
  }

  const visibleProducts = products.filter((item) => item.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()) && (!teamFilter || item.ownerTeamId === teamFilter));
  const listUrl = productUrl(organizationId);
  return <section className="products-screen" aria-labelledby="products-heading">
    {error && <p role="alert" className="alert">{error}</p>}
    {productError && <p role="alert" className="alert">{productError}</p>}
    {permissionsError && <p role="alert" className="alert">{permissionsError}</p>}
    {!ready ? !productError && <p role="status">Produkte werden geladen …</p> : view === 'list' ? <>
      <p className="eyebrow">PRODUKTE / INVENTAR</p><div className="page-heading"><div><h1 id="products-heading">Produkte</h1><p>Produkte, verantwortliche Teams und verbundene Quellen.</p></div>
        {!permissionsLoading && editableTeams.length > 0 && <a className="primary-link" href={productUrl(organizationId, '', 'create')}>+ Produkt registrieren</a>}</div>
      <div className="product-filters"><label>Team<select value={teamFilter} onChange={(event) => setTeamFilter(event.target.value)}><option value="">Alle Teams</option>{teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select></label><label>Produkte suchen<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} /></label></div>
      <div className="panel team-table-panel"><h2>Produktverzeichnis</h2>{products.length === 0 ? <p className="product-empty">Noch keine Produkte vorhanden.</p> : visibleProducts.length === 0 ? <p className="product-empty">Keine Produkte für diese Auswahl.</p> : <div className="team-table-scroll"><table className="team-table"><thead><tr><th>PRODUKT</th><th>VERANTWORTLICHES TEAM</th><th>QUELLEN</th></tr></thead><tbody>{visibleProducts.map((item) => <tr key={item.id}><td><a href={productUrl(organizationId, item.id)}>{item.name}</a></td><td>{teams.find((team) => team.id === item.ownerTeamId)?.name || item.ownerTeamId}</td><td><a href={productUrl(organizationId, item.id, 'repository')}>Quellen ansehen →</a></td></tr>)}</tbody></table></div>}</div>
      <div className="team-columns product-summary"><div className="panel"><h2>Discovery-Quellen</h2><dl className="team-role-list"><div><dt>Git-Repositories</dt><dd>Pro Produkt verbindbar</dd></div><div><dt>Cloud-Quellen</dt><dd>Nicht verfügbar</dd></div></dl></div><div className="panel"><h2>Inventar</h2><dl className="team-role-list"><div><dt>Sichtbare Produkte</dt><dd>{products.length}</dd></div><div><dt>Bewertungsabdeckung</dt><dd>Nicht verfügbar</dd></div></dl></div></div>
    </> : view === 'create' ? <>
      <p className="eyebrow">PRODUKTE / REGISTRIEREN</p><div className="page-heading"><div><h1 id="products-heading">Produkt registrieren</h1><p>Schritt 1 von 3 — Produkt benennen und einem Team zuordnen.</p></div></div>
      <ProductSteps active={1} /><div className="team-columns"><div className="panel"><h2>Produktidentität</h2>
        {permissionsLoading ? <p role="status">Berechtigungen werden geladen …</p> : editableTeams.length === 0 ? <p>Für die Produktanlage ist ein Team mit Bearbeitungsrecht erforderlich.</p> : <form onSubmit={createProduct}><label className="field">Produktname<input required maxLength={200} value={name} onChange={(event) => setName(event.target.value)} /></label><label className="field">Owner-Team<select value={ownerTeam} onChange={(event) => setOwnerTeam(event.target.value)} required><option value="" disabled>Team auswählen</option>{editableTeams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select></label><p>Produkttyp und Umgebung werden derzeit nicht gespeichert.</p><button type="submit" disabled={busy || !ownerTeam}>Produkt erstellen und weiter →</button></form>}</div>
        <div className="panel"><h2>Was geschieht als Nächstes?</h2><ol className="product-explainer"><li><strong>Git verbinden</strong><p>Ein Repository dem Produkt zuordnen und Zugriff prüfen.</p></li><li><strong>Discovery prüfen</strong><p>Verfügbare Informationen und Lücken werden gesondert dargestellt.</p></li><li><strong>Mit Packs bewerten</strong><p>Bewertungen verwenden die vorhandenen Packs.</p></li></ol></div></div><a className="team-back" href={listUrl}>← Zurück zu Produkten</a>
    </> : !product ? <><h1 id="products-heading">Produkt nicht verfügbar</h1><p>Das Produkt existiert nicht oder ist für dich nicht sichtbar.</p><a href={listUrl}>Zum Produktverzeichnis</a></> : view === 'detail' || view === 'discovery' ? <ProductDetail product={product} organizationId={organizationId} teamName={teams.find((team) => team.id === product.ownerTeamId)?.name || product.ownerTeamId} accessToken={accessToken} view={view} /> : <>
      <p className="eyebrow">PRODUKTE / QUELLEN VERBINDEN</p><div className="page-heading"><div><h1 id="products-heading">Produktquellen verbinden</h1><p>Schritt 2 von 3 — Git-Quellen für {product.name} verwalten.</p></div></div>
      <ProductSteps active={2} /><div className="team-columns"><div className="panel"><h2>Produktdetails</h2><p><strong>{product.name}</strong> · Team: {teams.find((team) => team.id === product.ownerTeamId)?.name || product.ownerTeamId}</p><h2>Git-Repositories</h2>
        {bindingsLoading ? <p role="status">Repositories werden geladen …</p> : bindingsError ? <p role="alert" className="alert">{bindingsError}</p> : bindings.length === 0 ? <p>Noch kein Repository verbunden.</p> : <ul className="product-bindings">{bindings.map((binding) => <li key={binding.id}><span className="break-value"><span>{binding.repository}</span> <small>({binding.provider})</small></span>{binding.provider.toLowerCase() === 'github' ? <button type="button" disabled={busy} onClick={() => { setBusy(true); void verify(binding).finally(() => setBusy(false)); }}>Zugriff prüfen</button> : <span>Prüfung nicht verfügbar</span>}</li>)}</ul>}
        {verification && <p role="status">{verification}</p>}
        {canEditProduct && <form onSubmit={connect}><label className="field">Git-Repository<input required maxLength={200} placeholder="owner/repository" value={repository} onChange={(event) => setRepository(event.target.value)} /></label><button type="submit" disabled={busy || bindingsLoading || Boolean(bindingsError)}>Repository verbinden</button></form>}
        {!permissionsLoading && !canEditProduct && <p>Du kannst dieses Produkt nur lesen.</p>}
        <h2 className="product-source-heading">Cloud-Quellen</h2><p>Nicht verfügbar.</p>
      </div><div className="panel"><h2>Zugriff und Quellen</h2><dl className="team-role-list"><div><dt>GitHub-Zugriff</dt><dd>Pro Repository prüfen</dd></div><div><dt>Cloud-Zuordnung</dt><dd>Nicht verfügbar</dd></div></dl><div className="team-info">Der Zugriff wird für das gespeicherte Repository geprüft. Ein Fehler entfernt weder Produkt noch Repository.</div></div></div>
      <div className="team-actions"><a className="team-back" href={listUrl}>← Zurück zu Produkten</a><a className="primary-link" href={productUrl(organizationId, product.id, 'discovery')}>Discovery ansehen →</a></div>
    </>}
  </section>;
}

/** @param {{active: number}} props */
function ProductSteps({ active }) {
  return <ol className="team-steps" aria-label="Schritte der Produktregistrierung">{['Produktidentität', 'Quellen verbinden', 'Discovery prüfen'].map((label, index) => <li key={label} aria-current={index + 1 === active ? 'step' : undefined}><span>{index + 1}</span>{label}</li>)}</ol>;
}
