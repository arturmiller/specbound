import React from 'react';

export const navigation = [
  { id: 'overview', label: 'Übersicht', icon: '◫', href: '/overview' },
  { id: 'products', label: 'Produkte', icon: '▦', href: '/legacy-products' },
  { id: 'teams', label: 'Teams', icon: '♧', href: '/teams' },
  { id: 'agents', label: 'Agenten', icon: '✦', href: '/agents' },
  { id: 'packs', label: 'Packs', icon: '▧', href: '/packs' },
  { id: 'catalogs', label: 'Kataloge', icon: '▥', href: '/catalogs' },
  { id: 'profiles', label: 'Profile', icon: '▣', href: '/profiles' },
  { id: 'findings', label: 'Findings', icon: '⚑', href: '/findings' },
  { id: 'pr-checks', label: 'PR Checks', icon: '⑂', href: '/pr-checks' },
  { id: 'evidence', label: 'Evidence', icon: '◈', href: '/evidence' },
  { id: 'evidence-packs', label: 'Evidence Packs', icon: '◇', href: '/evidence-packs' },
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
  const administration = ['settings', 'teams', 'agents', 'products'].includes(section);
  const primarySection = ({ packs: 'catalogs', providers: 'evidence-packs' })[section];
  return <div className="portal-layout resource-portal">
    <PortalSidebar primarySection={primarySection} organizationId={organizationId} secondarySection={section} />
    <div className="portal-main">
      <header className="portal-top">
        <p className="portal-breadcrumb"><span aria-hidden="true">◈</span> {organization?.name || 'Organisation'} <span aria-hidden="true">/</span> <strong>{active?.label || (section === 'assessment' ? 'Assessment' : 'Seite')}</strong></p>
        <span className="api-status" role="status">{apiStatus}</span>
        {onSignOut && <><span className="signed-in">Angemeldet.</span><button className="sign-out" type="button" onClick={onSignOut}>Lokal abmelden</button></>}
      </header>
      <main className="portal-content" id="main-content">
        {administration && organizations.length > 0 && <label className="field">Organisation
          <select value={organizationId} disabled={organizationBusy} onChange={(event) => onOrganizationChange(event.target.value)}>
            {organizations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>}
        {children}
      </main>
    </div>
  </div>;
}

/** @param {{primarySection?: string, organizationId?: string, secondarySection?: string}} props */
export function PortalSidebar({ primarySection, organizationId = '', secondarySection }) {
  const primary = [
    ['products', 'Produkte', '/products'],
    ['catalogs', 'Kataloge', '/catalogs'],
    ['profiles', 'Profile', '/profiles'],
    ['evidence-packs', 'Evidence Packs', '/evidence-packs'],
  ];
  const secondary = [
    ['findings', 'Findings', '/findings'],
    ['pr-checks', 'PR Checks', '/pr-checks'],
    ['evidence', 'Nachweisverzeichnis', '/evidence'],
    ['settings', 'Administration', '/settings'],
  ];
  const inAdministration = ['settings', 'teams', 'agents', 'products'].includes(secondarySection || '');
  return <aside className="portal-sidebar">
    <a className="portal-brand" href="/products"><span className="brand-mark" aria-hidden="true">◇</span> Specbound</a>
    <nav className="portal-nav" aria-label="Hauptnavigation">
      {primary.map(([id, label, href]) => <a key={id} className={`portal-nav-link ${primarySection === id ? 'is-active' : ''}`}
        aria-current={primarySection === id ? 'page' : undefined} href={href}>{label}</a>)}
    </nav>
    <div className="resource-support">
      <a href={organizationHref('/docs', organizationId)} aria-current={secondarySection === 'docs' ? 'page' : undefined}>Dokumentation</a>
      <details open={Boolean(secondarySection && secondarySection !== 'docs')}><summary>Weitere Funktionen</summary>
        {secondary.map(([id, label, href]) => <a key={id} href={organizationHref(href, organizationId)}
          aria-current={secondarySection === id ? 'page' : undefined}>{label}</a>)}
        {inAdministration && <>
          <a href={organizationHref('/teams', organizationId)} aria-current={secondarySection === 'teams' ? 'page' : undefined}>Teams</a>
          <a href={organizationHref('/agents', organizationId)} aria-current={secondarySection === 'agents' ? 'page' : undefined}>Agenten</a>
          <a href={organizationHref('/legacy-products', organizationId)} aria-current={secondarySection === 'products' ? 'page' : undefined}>Manuelle Produktverwaltung</a>
        </>}
      </details>
    </div>
  </aside>;
}
