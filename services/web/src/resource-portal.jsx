import React, { useEffect, useState } from 'react';
import { ProductWorkspace } from './products.jsx';
import { ResourceWorkspace } from './resources.jsx';
import { ProviderPacks } from './provider-packs.jsx';
import { ManifestProvenance } from './manifest-source.jsx';

const navigation = [['products', 'Produkte', '/products'], ['catalogs', 'Kataloge', '/catalogs'], ['profiles', 'Profile', '/profiles'], ['evidence-packs', 'Evidence Packs', '/evidence-packs']];

/** @typedef {{organizationId: string, defaultOwnerTeamId: string, organization: {id: string, name: string, ownerPrincipalId: string}}} Workspace */
/** @typedef {import('./products.jsx').Product} Product */

/** @param {{accessToken?: string, onSignOut?: () => void, apiStatus?: string}} props */
export function ResourcePortal({ accessToken = '', onSignOut, apiStatus = '' }) {
  const section = navigation.find((item) => item[2] === location.pathname.replace(/\/$/, ''))?.[0] || 'products';
  const params = new URLSearchParams(location.search);
  const productId = section === 'products' ? params.get('product') || '' : '';
  const [state, setState] = useState(/** @type {{token: string, workspace: Workspace | null, products: Product[], teams: {id: string, name: string}[], principal: string, resources: import('./resources.jsx').Resource[], error: string} | null} */ (null));
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const current = state?.token === accessToken ? state : null;
  const workspace = current?.workspace;
  const products = current?.products || [];
  const product = products.find((item) => item.id === productId);

  useEffect(() => {
    const controller = new AbortController();
    /** @type {RequestInit} */ const options = { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} };
    async function load() {
      try {
        const response = await fetch('/api/workspace', options);
        if (!response.ok) throw new Error(response.status === 403 ? 'Für den konfigurierten Arbeitsbereich fehlen die erforderlichen Rechte.' : response.status === 401 ? 'Anmeldung erforderlich.' : 'Der Arbeitsbereich ist nicht konfiguriert. Bitte die serverseitige Arbeitsbereichskonfiguration prüfen.');
        /** @type {Workspace} */ const context = await response.json();
        if (!context.organizationId || !context.defaultOwnerTeamId || context.organization?.id !== context.organizationId) throw new Error('Der Arbeitsbereich ist nicht eindeutig konfiguriert.');
        const root = `/api/organizations/${encodeURIComponent(context.organizationId)}`;
        const responses = await Promise.all([fetch(`${root}/products`, options), fetch(`${root}/resources`, options), fetch(`${root}/teams`, options), fetch('/api/auth/me', options)]);
        if (responses.some((item) => !item.ok)) throw new Error('Ressourcen des Arbeitsbereichs konnten nicht geladen werden.');
        const [items, resources, teams, principal] = await Promise.all(responses.map((item) => item.json()));
        if (!controller.signal.aborted) setState({ token: accessToken, workspace: context, products: items, resources, teams, principal: principal.id, error: '' });
      } catch (failure) {
        if (!controller.signal.aborted) setState({ token: accessToken, workspace: null, products: [], resources: [], teams: [], principal: '', error: failure instanceof Error ? failure.message : 'Arbeitsbereich nicht verfügbar.' });
      }
    }
    void load();
    return () => controller.abort();
  }, [accessToken]);

  /** @param {string} id */
  function selectProduct(id) {
    const view = params.get('view');
    const query = new URLSearchParams({ product: id, view: ['requirements', 'scans', 'scope'].includes(view || '') ? view || 'requirements' : 'requirements' });
    location.assign(`/products?${query}`);
  }

  /** @param {string} path */
  function workspaceHref(path) {
    return workspace ? `${path}?${new URLSearchParams({ organization: workspace.organizationId })}` : path;
  }

  return <div className="portal-layout resource-portal">
    <aside className="portal-sidebar"><a className="portal-brand" href="/products"><span className="brand-mark" aria-hidden="true">◇</span> Specbound</a>
      <nav className="portal-nav" aria-label="Hauptnavigation">{navigation.map(([id, label, href]) => <a className={`portal-nav-link ${section === id ? 'is-active' : ''}`} aria-current={section === id ? 'page' : undefined} key={id} href={href}>{label}</a>)}</nav>
      <div className="resource-support"><a href={workspaceHref('/docs')}>Dokumentation</a><details><summary>Weitere Funktionen</summary><a href={workspaceHref('/findings')}>Findings</a><a href={workspaceHref('/pr-checks')}>PR Checks</a><a href={workspaceHref('/legacy-products')}>Manuelle Produktverwaltung</a><a href={workspaceHref('/settings')}>Administration</a></details></div>
    </aside>
    <div className="portal-main"><header className="portal-top"><p className="portal-breadcrumb">Arbeitsbereich <strong>{workspace?.organization.name || 'Specbound'}</strong></p><span className="api-status" role="status">{apiStatus}</span>{onSignOut && <><span className="signed-in">Angemeldet.</span><button className="sign-out" onClick={onSignOut}>Lokal abmelden</button></>}</header>
      <main className="portal-content" id="main-content">
        {!current ? <p role="status">Arbeitsbereich wird geladen …</p> : current.error ? <section><h1>Arbeitsbereich nicht verfügbar</h1><p role="alert">{current.error}</p><a href="/docs#docs/getting-started">Einrichtung und Hilfe</a></section> : workspace && <>
          {productId && <div className="global-product-context"><label className="field">Produkt auswählen<select aria-label="Produkt auswählen" value={product?.id || ''} disabled={busy} onChange={(event) => selectProduct(event.target.value)}><option value="" disabled>Produkt auswählen</option>{products.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><a href="/products">Alle Produkte</a></div>}
          {section === 'products' ? productId || params.get('view') ? productId && !product ? <section><h1>Produkt nicht verfügbar</h1><p>Das Produkt existiert nicht oder ist für dich nicht sichtbar.</p><a href="/products">Alle Produkte</a></section> : <ProductWorkspace organizationId={workspace.organizationId} organization={workspace.organization} teams={current.teams} teamsLoading={false} accessToken={accessToken} onBusyChange={setBusy} portalMode /> : <section aria-labelledby="products-heading">
            <div className="page-heading"><div><h1 id="products-heading">Produkte</h1><p>Wähle das Produkt, dessen Anforderungen und Prüfungen du ansehen möchtest.</p></div>{current.principal === workspace.organization.ownerPrincipalId && <a className="primary-link" href="/products?view=manifest">Produkt aus Manifest registrieren</a>}</div>
            <label className="field">Produkte suchen<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
            <div className="resource-product-grid">{products.filter((item) => item.name.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map((item) => {
              const resource = current.resources.find((row) => row.id === item.resourceRevisionId);
              return <article className="panel" key={item.id}><h2><a href={`/products?${new URLSearchParams({ product: item.id, view: 'requirements' })}`}>{item.name}</a></h2><p>{item.configurationStatus === 'manifest_managed' ? 'Manifest verwaltet' : 'Ohne Profilzuordnung'}</p>{resource ? <><p>Profil: {resource.resolved.profile?.name} · {resource.resolved.profile?.version}</p><ManifestProvenance source={resource.source} defaultPath={resource.source.manifestPath} /></> : <p>Historisches Produkt ohne registrierte Manifestquelle.</p>}<a href={`/products?${new URLSearchParams({ product: item.id, view: 'scope' })}`}>Geltungsbereich ansehen</a></article>;
            })}</div>
            {!products.length ? <p>Noch keine Produkte vorhanden.</p> : !products.some((item) => item.name.toLocaleLowerCase().includes(search.toLocaleLowerCase())) && <p>Keine Produkte für diese Suche. <button onClick={() => setSearch('')}>Suche zurücksetzen</button></p>}
          </section> : section === 'evidence-packs' ? <ProviderPacks organizationId={workspace.organizationId} organization={workspace.organization} accessToken={accessToken} onBusyChange={setBusy} /> : <ResourceWorkspace organizationId={workspace.organizationId} organization={workspace.organization} resourceType={section === 'profiles' ? 'Profile' : 'Catalog'} accessToken={accessToken} onBusyChange={setBusy} />}
        </>}
      </main>
    </div>
  </div>;
}
