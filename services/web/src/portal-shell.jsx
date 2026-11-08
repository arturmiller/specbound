import React from 'react';

export const navigation = [
  { id: 'overview', label: 'Übersicht', icon: '◫', href: '/overview' },
  { id: 'products', label: 'Produkte', icon: '▦', href: '/products' },
  { id: 'teams', label: 'Teams', icon: '♧', href: '/teams' },
  { id: 'agents', label: 'Agenten', icon: '✦', href: '/agents' },
  { id: 'packs', label: 'Packs', icon: '▧', href: '/packs' },
  { id: 'findings', label: 'Findings', icon: '⚑', href: '/findings', pending: true },
  { id: 'pr-checks', label: 'PR Checks', icon: '⑂', href: '/pr-checks' },
  { id: 'evidence', label: 'Evidence', icon: '◈', href: '/evidence' },
  { id: 'providers', label: 'Provider', icon: '⌁', href: '/providers' },
  { id: 'docs', label: 'Dokumentation', icon: '▤', href: '/docs' },
  { id: 'settings', label: 'Einstellungen', icon: '⚙', href: '/settings' },
];

export function currentSection() {
  const { pathname, search, hash } = window.location;
  if (/^\/assessments\/[A-Za-z0-9_-]{1,100}\/?$/.test(pathname)) return 'assessment';
  if (pathname === '/') {
    const params = new URLSearchParams(search);
    if (hash.startsWith('#docs/')) return 'docs';
    if (params.has('product') || hash === '#products-heading') return 'products';
    if (params.has('pack') || hash === '#packs-heading') return 'packs';
    if (params.has('team') || hash === '#teams-heading') return 'teams';
    return 'settings';
  }
  return navigation.find((item) => item.href === pathname.replace(/\/$/, ''))?.id || 'not-found';
}

/** @param {string} href @param {string} organizationId */
export function organizationHref(href, organizationId) {
  if (!organizationId) return href;
  const url = new URL(href, window.location.origin);
  url.searchParams.set('organization', organizationId);
  return `${url.pathname}${url.search}${url.hash}`;
}

/** @param {{section: string, organizationId: string, organizations: {id: string, name: string}[], onOrganizationChange: (id: string) => void, organizationBusy?: boolean, onSignOut?: () => void, apiStatus: string, children: React.ReactNode}} props */
export function PortalShell({ section, organizationId, organizations, onOrganizationChange, organizationBusy = false, onSignOut, apiStatus, children }) {
  const active = navigation.find((item) => item.id === section);
  const organization = organizations.find((item) => item.id === organizationId);
  const initials = organization?.name.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0].toLocaleUpperCase()).join('') || 'S';
  return <div className="portal-layout">
    <aside className="portal-sidebar">
      <a className="portal-brand" href={organizationHref('/settings', organizationId)}><span className="brand-mark" aria-hidden="true">◇</span> Specbound</a>
      <nav aria-label="Hauptnavigation" className="portal-nav">
        {navigation.map((item) => <a key={item.id} className={`portal-nav-link ${section === item.id ? 'is-active' : ''}`}
          aria-current={section === item.id ? 'page' : undefined} href={organizationHref(item.href, organizationId)}>
          <span className="nav-icon" aria-hidden="true">{item.icon}</span><span>{item.label}</span>
        </a>)}
      </nav>
      <div className="sidebar-organization">
        <span className="organization-avatar" aria-hidden="true">{initials}</span>
        <div className="organization-picker">
          {organizations.length ? <label>Organisation<select aria-label="Organisation" value={organizationId} disabled={organizationBusy} onChange={(event) => onOrganizationChange(event.target.value)}>
            {organizations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label> : <span>Keine Organisation</span>}
          <small>Organisation und Zugriff</small>
        </div>
      </div>
    </aside>
    <div className="portal-main">
      <header className="portal-top">
        <p className="portal-breadcrumb"><span aria-hidden="true">◈</span> {organization?.name || 'Organisation'} <span aria-hidden="true">/</span> <strong>{active?.label || (section === 'assessment' ? 'Assessment' : 'Seite')}</strong></p>
        <a className="portal-search" href={organizationHref('/overview', organizationId)}><span aria-hidden="true">⌕</span> Suche öffnen</a>
        <span className="api-status" role="status">{apiStatus}</span>
        {onSignOut && <><span className="signed-in">Angemeldet.</span><button className="sign-out" type="button" onClick={onSignOut}>Lokal abmelden</button></>}
      </header>
      <main className="portal-content" id="main-content">{children}</main>
    </div>
  </div>;
}
