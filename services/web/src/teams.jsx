import React, { useEffect, useState } from 'react';
import { PackWorkspace } from './packs.jsx';
import { ProductWorkspace } from './products.jsx';

/** @typedef {{id: string, name: string}} Organization */
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

/** @param {{accessToken?: string}} props */
export function TeamWorkspace({ accessToken = '' }) {
  const [organizations, setOrganizations] = useState(/** @type {Organization[]} */ ([]));
  const [teams, setTeams] = useState(/** @type {Team[]} */ ([]));
  const [members, setMembers] = useState(/** @type {Member[]} */ ([]));
  const [organizationId, setOrganizationId] = useState(() => new URLSearchParams(location.search).get('organization') || '');
  const [teamId, setTeamId] = useState(() => new URLSearchParams(location.search).get('team') || '');
  const [teamName, setTeamName] = useState('');
  const [principalId, setPrincipalId] = useState('');
  const [role, setRole] = useState('viewer');
  const [loading, setLoading] = useState(true);
  const [teamsLoading, setTeamsLoading] = useState(false);
  const [membersLoading, setMembersLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    request('/organizations', { signal: controller.signal }, accessToken)
      .then((/** @type {Organization[]} */ data) => {
        setOrganizations(data);
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

  return (
    <section className="workspace" aria-labelledby="teams-heading">
      <div className="workspace-heading">
        <div><p className="eyebrow">VERANTWORTUNG</p><h2 id="teams-heading">Teams</h2></div>
        <p>Teams und Mitgliedschaften einer Organisation verwalten.</p>
      </div>
      {error && <p role="alert" className="alert">{error}</p>}
      {loading && <p>Organisationen werden geladen …</p>}
      {!loading && organizations.length === 0 && !error && <p>Keine Organisationen verfügbar.</p>}
      {organizations.length > 0 && <>
        <label className="field">Organisation
          <select value={organizationId} disabled={busy} onChange={(event) => { setTeams([]); setMembers([]); setTeamId(''); setOrganizationId(event.target.value); setError(''); }}>
            {organizations.map((organization) => <option value={organization.id} key={organization.id}>{organization.name}</option>)}
          </select>
        </label>
        <div className="workspace-grid">
          <div className="panel">
            <h3>Teamliste</h3>
            {teamsLoading ? <p>Teams werden geladen …</p> : teams.length === 0 && <p>Noch keine Teams vorhanden.</p>}
            <ul className="team-list">{teams.map((team) => <li key={team.id}>
              <button type="button" className="team-choice" disabled={busy} aria-pressed={team.id === teamId} onClick={() => { setTeamId(team.id); setError(''); }}>{team.name}</button>
            </li>)}</ul>
            <form onSubmit={createTeam}>
              <label className="field">Teamname<input value={teamName} onChange={(event) => setTeamName(event.target.value)} required maxLength={200} /></label>
              <button type="submit" disabled={busy || teamsLoading}>Team erstellen</button>
            </form>
          </div>
          <div className="panel">
            <h3>Mitglieder</h3>
            {!teamId ? <p>Wähle ein Team aus.</p> : <>
              {membersLoading ? <p>Mitglieder werden geladen …</p> : members.length === 0 && <p>Noch keine Mitglieder vorhanden.</p>}
              <ul className="members">{members.map((member) => <li key={member.id}><span>{member.principalId}</span><span className="role">{member.role}</span></li>)}</ul>
              <form onSubmit={addMember}>
                <label className="field">Principal-ID<input value={principalId} onChange={(event) => setPrincipalId(event.target.value)} required maxLength={200} /></label>
                <label className="field">Rolle<select value={role} onChange={(event) => setRole(event.target.value)}>
                  <option value="viewer">Viewer</option><option value="maintainer">Maintainer</option><option value="admin">Admin</option>
                </select></label>
                <button type="submit" disabled={busy || membersLoading}>Mitglied hinzufügen</button>
              </form>
            </>}
          </div>
        </div>
      </>}
      {organizationId && <ProductWorkspace key={`products-${organizationId}`} organizationId={organizationId} teams={teams} accessToken={accessToken} />}
      {organizationId && <PackWorkspace key={`packs-${organizationId}`} organizationId={organizationId} accessToken={accessToken} />}
    </section>
  );
}
