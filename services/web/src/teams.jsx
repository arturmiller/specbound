import React, { useEffect, useState } from 'react';
import { PackWorkspace } from './packs.jsx';
import { ProductWorkspace } from './products.jsx';
import { Overview } from './overview.jsx';
import { Documentation } from './docs.jsx';
import { AssessmentReport } from './assessment-report.jsx';
import { currentSection, navigation, organizationHref, PortalShell } from './portal-shell.jsx';

/** @typedef {{id: string, name: string, ownerPrincipalId?: string}} Organization */
/** @typedef {{id: string, name: string}} Team */
/** @typedef {{id: string, principalId: string, role: string}} Member */

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
  return response.json();
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
  const [members, setMembers] = useState(/** @type {Member[]} */ ([]));
  const [organizationId, setOrganizationId] = useState(() => new URLSearchParams(location.search).get('organization') || '');
  const [teamId, setTeamId] = useState(() => new URLSearchParams(location.search).get('team') || '');
  const [organizationName, setOrganizationName] = useState('');
  const [teamName, setTeamName] = useState('');
  const [principalId, setPrincipalId] = useState('');
  const [role, setRole] = useState('viewer');
  const [loading, setLoading] = useState(true);
  const [organizationsReady, setOrganizationsReady] = useState(false);
  const [teamsLoading, setTeamsLoading] = useState(false);
  const [membersLoading, setMembersLoading] = useState(false);
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
    if (!organizationId) { setTeams([]); setTeamId(''); setTeamsLoading(false); return; }
    const controller = new AbortController();
    setTeamsLoading(true);
    request(`/organizations/${encodeURIComponent(organizationId)}/teams`, { signal: controller.signal }, accessToken)
      .then((/** @type {Team[]} */ data) => {
        setTeams(data);
        setTeamId((current) => data.some((team) => team.id === current) ? current : (data[0]?.id || ''));
      })
      .catch((failure) => { if (!controller.signal.aborted) setError(errorMessage(failure)); })
      .finally(() => { if (!controller.signal.aborted) setTeamsLoading(false); });
    return () => controller.abort();
  }, [organizationId, accessToken]);

  useEffect(() => {
    if (!teamId) { setMembers([]); setMembersLoading(false); return; }
    const controller = new AbortController();
    setMembers([]);
    setMembersLoading(true);
    request(`/teams/${encodeURIComponent(teamId)}/members`, { signal: controller.signal }, accessToken)
      .then((/** @type {Member[]} */ data) => setMembers(data))
      .catch((failure) => { if (!controller.signal.aborted) setError(errorMessage(failure)); })
      .finally(() => { if (!controller.signal.aborted) setMembersLoading(false); });
    return () => controller.abort();
  }, [teamId, accessToken]);

  useEffect(() => {
    const url = new URL(location.href);
    if (organizationId) url.searchParams.set('organization', organizationId); else url.searchParams.delete('organization');
    if (teamId) url.searchParams.set('team', teamId); else url.searchParams.delete('team');
    history.replaceState(null, '', url);
  }, [organizationId, teamId]);

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

  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function createTeam(event) {
    event.preventDefault();
    if (!teamName.trim() || !organizationId) return;
    setBusy(true); setError('');
    try {
      const team = await request(`/organizations/${encodeURIComponent(organizationId)}/teams`, {
        method: 'POST', body: JSON.stringify({ name: teamName.trim() }),
      }, accessToken);
      setTeams((current) => [...current, team]);
      setTeamId(team.id);
      setTeamName('');
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setBusy(false); }
  }

  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function addMember(event) {
    event.preventDefault();
    if (!principalId.trim() || !teamId) return;
    setBusy(true); setError('');
    try {
      const member = await request(`/teams/${encodeURIComponent(teamId)}/members`, {
        method: 'POST', body: JSON.stringify({ principalId: principalId.trim(), role }),
      }, accessToken);
      setMembers((current) => [...current, member]);
      setPrincipalId('');
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setBusy(false); }
  }

  const section = currentSection();
  const currentOrganization = organizations.find((item) => item.id === organizationId);
  const needsOrganization = !['settings', 'docs', 'assessment', 'not-found'].includes(section);
  const pending = navigation.find((item) => item.id === section && item.pending);
  const reportId = /^\/assessments\/([A-Za-z0-9_-]{1,100})\/?$/.exec(window.location.pathname)?.[1];

  /** @param {string} id */
  function changeOrganization(id) {
    const url = new URL(window.location.href);
    for (const key of ['team', 'product', 'pack']) url.searchParams.delete(key);
    url.searchParams.set('organization', id);
    history.replaceState(null, '', url);
    setTeams([]); setMembers([]); setTeamId(''); setOrganizationId(id); setError('');
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
              <div><dt>Teams</dt><dd>{teamsLoading ? 'Wird geladen …' : teams.length}</dd></div>
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
    {section === 'teams' && organizationsReady && organizationId && <section className="workspace" aria-labelledby="teams-heading">
      <div className="workspace-heading"><div><p className="eyebrow">VERANTWORTUNG</p><h1 id="teams-heading">Teams</h1></div>
        <p>Teams und Mitgliedschaften einer Organisation verwalten.</p></div>
      <div className="workspace-grid"><div className="panel"><h2>Teamliste</h2>
        {teamsLoading ? <p>Teams werden geladen …</p> : teams.length === 0 && <p>Noch keine Teams vorhanden.</p>}
        <ul className="team-list">{teams.map((team) => <li key={team.id}>
          <button type="button" className="team-choice" disabled={busy} aria-pressed={team.id === teamId} onClick={() => { setTeamId(team.id); setError(''); }}>{team.name}</button>
        </li>)}</ul><form onSubmit={createTeam}>
          <label className="field">Teamname<input value={teamName} onChange={(event) => setTeamName(event.target.value)} required maxLength={200} /></label>
          <button type="submit" disabled={busy || teamsLoading}>Team erstellen</button></form></div>
        <div className="panel"><h2>Mitglieder</h2>{!teamId ? <p>Wähle ein Team aus.</p> : <>
          {membersLoading ? <p>Mitglieder werden geladen …</p> : members.length === 0 && <p>Noch keine Mitglieder vorhanden.</p>}
          <ul className="members">{members.map((member) => <li key={member.id}><span>{member.principalId}</span><span className="role">{member.principalId.startsWith('agent:') ? 'Agent: Lesen; keine Pack-Freigabe' : member.role}</span></li>)}</ul>
          <form onSubmit={addMember}><label className="field">Principal-ID<input value={principalId} onChange={(event) => setPrincipalId(event.target.value)} required maxLength={200} /></label>
            <label className="field">Rolle<select value={role} onChange={(event) => setRole(event.target.value)}><option value="viewer">Viewer</option><option value="maintainer">Maintainer</option><option value="admin">Admin</option></select></label>
            <button type="submit" disabled={busy || membersLoading}>Mitglied hinzufügen</button></form></>}
        </div></div>
    </section>}
    {section === 'products' && organizationsReady && organizationId && <ProductWorkspace key={`products-${organizationId}`} organizationId={organizationId} teams={teams} accessToken={accessToken} />}
    {section === 'packs' && organizationsReady && organizationId && <PackWorkspace key={`packs-${organizationId}`} organizationId={organizationId} accessToken={accessToken} />}
    {section === 'overview' && organizationsReady && organizationId && <Overview key={`overview-${organizationId}`} organizationId={organizationId} teams={teams} accessToken={accessToken} />}
    {pending && organizationsReady && organizationId && <section className="unavailable"><p className="eyebrow">IN VORBEREITUNG</p><h1>{pending.label}</h1>
      <div className="panel"><h2>Dieser Bereich ist noch nicht verfügbar</h2><p>Die Oberfläche für diesen Bereich wird in Phase 1 ergänzt.</p></div></section>}
    {section === 'docs' && <Documentation />}
    {section === 'assessment' && reportId && <AssessmentReport id={reportId} accessToken={accessToken} />}
    {section === 'not-found' && <section><h1>Seite nicht gefunden</h1><a href={organizationHref('/settings', organizationId)}>Zu den Einstellungen</a></section>}
  </PortalShell>;
}
