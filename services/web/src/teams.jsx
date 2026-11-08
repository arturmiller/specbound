import React, { useEffect, useState } from 'react';
import { PackWorkspace } from './packs.jsx';
import { ProductWorkspace } from './products.jsx';
import { Overview } from './overview.jsx';
import { Documentation } from './docs.jsx';
import { AssessmentReport } from './assessment-report.jsx';
import { currentSection, navigation, organizationHref, PortalShell } from './portal-shell.jsx';
import { TeamsScreen } from './teams-screen.jsx';
import { ProviderPacks } from './provider-packs.jsx';
import { EvidenceRegistry } from './evidence-registry.jsx';
import { FindingDetail } from './finding-detail.jsx';

/** @typedef {{id: string, name: string, ownerPrincipalId?: string}} Organization */
/** @typedef {{id: string, name: string}} Team */

class ApiError extends Error {
  /** @param {number} status */
  constructor(status) {
    super(`API error ${status}`);
    this.status = status;
  }
}

/** @param {string} path @param {RequestInit} [options] @param {string} [accessToken] */
async function request(path, options = {}, accessToken = '') {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}), ...options.headers },
  });
  if (!response.ok) throw new ApiError(response.status);
  return response.status === 204 ? null : response.json();
}

/** @param {unknown} error */
function errorMessage(error) {
  if (error instanceof ApiError && error.status === 401) return 'Anmeldung erforderlich. Die Anmeldung wird noch eingerichtet.';
  if (error instanceof ApiError && error.status === 403) return 'Für diese Aktion fehlen die erforderlichen Rechte.';
  if (error instanceof ApiError && error.status === 409) return 'Dieses Mitglied ist bereits im Team.';
  return 'Die Anfrage konnte nicht abgeschlossen werden. Bitte erneut versuchen.';
}

/** @param {{accessToken?: string, onSignOut?: () => void, authConfigured?: boolean, apiStatus?: string}} props */
export function TeamWorkspace({ accessToken = '', onSignOut, authConfigured = false, apiStatus = 'API wird geprüft …' }) {
  const [organizations, setOrganizations] = useState(/** @type {Organization[]} */ ([]));
  const [teams, setTeams] = useState(/** @type {Team[]} */ ([]));
  const [organizationId, setOrganizationId] = useState(() => new URLSearchParams(location.search).get('organization') || '');
  const [organizationName, setOrganizationName] = useState('');
  const [loading, setLoading] = useState(true);
  const [organizationsReady, setOrganizationsReady] = useState(false);
  const [teamsLoading, setTeamsLoading] = useState(false);
  const [teamsError, setTeamsError] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setOrganizationsReady(false);
    request('/organizations', { signal: controller.signal }, accessToken)
      .then((/** @type {Organization[]} */ data) => {
        setOrganizations(data);
        setOrganizationsReady(true);
        setOrganizationId((current) => data.some((org) => org.id === current) ? current : (data[0]?.id || ''));
      })
      .catch((failure) => { if (!controller.signal.aborted) setError(errorMessage(failure)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [accessToken]);

  useEffect(() => {
    if (!organizationId) { setTeams([]); setTeamsLoading(false); return; }
    const controller = new AbortController();
    setTeamsLoading(true);
    setTeamsError('');
    request(`/organizations/${encodeURIComponent(organizationId)}/teams`, { signal: controller.signal }, accessToken)
      .then((/** @type {Team[]} */ data) => {
        setTeams(data);
      })
      .catch((failure) => { if (!controller.signal.aborted) { setTeams([]); setTeamsError(errorMessage(failure)); } })
      .finally(() => { if (!controller.signal.aborted) setTeamsLoading(false); });
    return () => controller.abort();
  }, [organizationId, accessToken]);

  useEffect(() => {
    const url = new URL(location.href);
    if (organizationId) url.searchParams.set('organization', organizationId); else url.searchParams.delete('organization');
    history.replaceState(null, '', url);
  }, [organizationId]);

  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function createOrganization(event) {
    event.preventDefault();
    if (!organizationName.trim()) return;
    setBusy(true); setError('');
    try {
      /** @type {Organization} */
      const organization = await request('/organizations', {
        method: 'POST', body: JSON.stringify({ name: organizationName.trim() }),
      }, accessToken);
      setOrganizations([organization]); setOrganizationId(organization.id); setOrganizationName('');
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setBusy(false); }
  }

  const section = currentSection();
  const currentOrganization = organizations.find((item) => item.id === organizationId);
  const needsOrganization = !['settings', 'docs', 'assessment', 'not-found'].includes(section);
  const findingId = new URLSearchParams(window.location.search).get('finding') || '';
  const pending = navigation.find((item) => item.id === section && item.pending && !(section === 'findings' && findingId));
  const reportId = /^\/assessments\/([A-Za-z0-9_-]{1,100})\/?$/.exec(window.location.pathname)?.[1];

  /** @param {string} id */
  function changeOrganization(id) {
    const url = new URL(window.location.href);
    for (const key of ['team', 'product', 'pack', 'view', 'capability', 'evidence', 'offset', 'finding', 'assessment']) url.searchParams.delete(key);
    url.searchParams.set('organization', id);
    history.replaceState(null, '', url);
    setTeams([]); setOrganizationId(id); setError('');
  }

  return <PortalShell section={section} organizationId={organizationId} organizations={organizations}
    onOrganizationChange={changeOrganization} organizationBusy={busy} onSignOut={onSignOut} apiStatus={apiStatus}>
    {error && <p role="alert" className="alert">{error}</p>}
    {loading && <p role="status">Organisationen werden geladen …</p>}
    {section === 'settings' && <section aria-labelledby="settings-heading">
      <p className="eyebrow">ORGANISATION / EINSTELLUNGEN</p>
      <div className="page-heading"><div><h1 id="settings-heading">Workspace-Einstellungen</h1>
        <p>Organisationsidentität, Teamverantwortung und Systemverbindungen verwalten.</p></div>
        {currentOrganization && <a className="primary-link" href={organizationHref('/teams', organizationId)}>Teams verwalten <span aria-hidden="true">→</span></a>}
      </div>
      <div className="settings-grid">
        <div className="panel settings-card"><h2>{currentOrganization?.name || 'Organisation'}</h2>
          {currentOrganization ? <><div className="workspace-avatar" aria-hidden="true">{currentOrganization.name.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0].toLocaleUpperCase()).join('')}</div>
            <dl className="settings-list"><div><dt>Workspace-ID</dt><dd>{currentOrganization.id}</dd></div>
              <div><dt>Teams</dt><dd>{teamsLoading ? 'Wird geladen …' : teamsError ? 'Nicht verfügbar' : teams.length}</dd></div>
              <div><dt>Eigentümer</dt><dd className="break-value">{currentOrganization.ownerPrincipalId || 'Nicht verfügbar'}</dd></div></dl>
            <a className="small-link" href={organizationHref('/teams', organizationId)}>Teams ansehen →</a></>
            : !loading && organizationsReady ? <><p>Keine Organisationen verfügbar.</p>
              <form onSubmit={createOrganization}>
                <label className="field">Organisationsname<input required maxLength={200} value={organizationName} onChange={(event) => setOrganizationName(event.target.value)} /></label>
                <button type="submit" disabled={busy}>Organisation erstellen</button>
              </form></> : <p>Organisationsdaten werden geladen …</p>}
        </div>
        <div className="panel settings-card"><h2>Identität und Zugriff</h2><dl className="settings-list">
          <div><dt>Anmeldung</dt><dd>{authConfigured ? 'OIDC konfiguriert' : 'Nicht konfiguriert'}</dd></div>
          <div><dt>Teamrollen</dt><dd>Admin · Maintainer · Viewer</dd></div>
          <div><dt>Produktverantwortung</dt><dd>Team erforderlich</dd></div></dl>
          <p className="info-note">Teams bilden Verantwortungsbereiche. Git-Rechte werden separat verwaltet.</p>
        </div>
        <div className="panel settings-card"><h2>Plattformverbindungen</h2><dl className="settings-list">
          <div><dt>GitHub</dt><dd>Nicht geprüft</dd></div>
          <div><dt>Weitere Verbindungen</dt><dd>Derzeit nicht verfügbar</dd></div></dl>
          <p>Verbindungen und ihre Rechte werden gesondert eingerichtet.</p>
        </div>
      </div>
      {currentOrganization && <div className="next-step"><div><strong>Ein verantwortliches Team einrichten</strong>
        <p>Produkte werden einem Team zugeordnet; Teammitgliedschaften und Organisationszugriff sind getrennt.</p></div>
        <a className="primary-link" href={organizationHref('/teams', organizationId)}>Teams öffnen →</a></div>}
    </section>}
    {needsOrganization && !loading && organizationsReady && !organizationId && <div className="panel"><h1>Organisation erforderlich</h1>
      <p>Lege zuerst eine Organisation an oder wähle eine zugängliche Organisation aus.</p><a href="/settings">Zu den Einstellungen</a></div>}
    {section === 'teams' && organizationsReady && organizationId && <TeamsScreen key={organizationId} organization={currentOrganization} teams={teams} teamsLoading={teamsLoading} teamsError={teamsError} accessToken={accessToken} request={request} errorMessage={errorMessage} onBusyChange={setBusy} />}
    {section === 'products' && organizationsReady && organizationId && <ProductWorkspace key={`products-${organizationId}`} organizationId={organizationId} organization={currentOrganization} teams={teams} teamsLoading={teamsLoading} accessToken={accessToken} onBusyChange={setBusy} />}
    {section === 'packs' && organizationsReady && organizationId && <PackWorkspace key={`packs-${organizationId}`} organizationId={organizationId} organization={currentOrganization} accessToken={accessToken} onBusyChange={setBusy} />}
    {section === 'providers' && organizationsReady && organizationId && <ProviderPacks key={`providers-${organizationId}`} organizationId={organizationId} organization={currentOrganization} accessToken={accessToken} onBusyChange={setBusy} />}
    {section === 'evidence' && organizationsReady && organizationId && <EvidenceRegistry key={`evidence-${organizationId}`} organizationId={organizationId} accessToken={accessToken} />}
    {section === 'findings' && findingId && organizationsReady && organizationId && <FindingDetail key={`${organizationId}-${findingId}`} organizationId={organizationId} findingId={findingId} accessToken={accessToken} />}
    {section === 'overview' && organizationsReady && organizationId && <Overview key={`overview-${organizationId}`} organizationId={organizationId} teams={teams} teamsLoading={teamsLoading} teamsError={teamsError} accessToken={accessToken} />}
    {pending && organizationsReady && organizationId && <section className="unavailable"><p className="eyebrow">IN VORBEREITUNG</p><h1>{pending.label}</h1>
      <div className="panel"><h2>Dieser Bereich ist noch nicht verfügbar</h2><p>Die Oberfläche für diesen Bereich wird in Phase 1 ergänzt.</p></div></section>}
    {section === 'docs' && <Documentation />}
    {section === 'assessment' && reportId && <AssessmentReport id={reportId} accessToken={accessToken} />}
    {section === 'not-found' && <section><h1>Seite nicht gefunden</h1><a href={organizationHref('/settings', organizationId)}>Zu den Einstellungen</a></section>}
  </PortalShell>;
}
