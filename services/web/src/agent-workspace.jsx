import React, { useEffect, useState } from 'react';
import { AgentAccess } from './agent-access.jsx';

/** @typedef {{id: string, name: string, ownerPrincipalId?: string}} Organization */
/** @typedef {{id: string, name: string}} Team */
/** @typedef {{id: string, name: string, kind: string}} Agent */
/** @typedef {{id: string, principalId: string, role: string}} Member */
/** @typedef {(path: string, options?: RequestInit, accessToken?: string) => Promise<any>} Request */

/** @param {string} organizationId @param {string} [view] @param {string} [agentId] */
function agentUrl(organizationId, view = '', agentId = '') {
  const params = new URLSearchParams({ organization: organizationId });
  if (view) params.set('view', view);
  if (agentId) params.set('agent', agentId);
  return `/agents?${params}`;
}

/** @param {{organization?: Organization, teams: Team[], teamsLoading: boolean, teamsError: string, accessToken: string, request: Request, errorMessage: (error: unknown) => string, onBusyChange: (busy: boolean) => void}} props */
export function AgentWorkspace({ organization, teams, teamsLoading, teamsError, accessToken, request, errorMessage, onBusyChange }) {
  const organizationId = organization?.id || '';
  const params = new URLSearchParams(window.location.search);
  const view = params.get('view') || 'list';
  const agentId = params.get('agent') || '';
  const [agents, setAgents] = useState(/** @type {Agent[] | null} */ (null));
  const [principal, setPrincipal] = useState('');
  const [principalLoaded, setPrincipalLoaded] = useState(false);
  const [members, setMembers] = useState(/** @type {Record<string, Member[] | null>} */ ({}));
  const [membersLoading, setMembersLoading] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState('');
  useEffect(() => { onBusyChange(busy); return () => onBusyChange(false); }, [busy, onBusyChange]);
  useEffect(() => {
    const controller = new AbortController();
    request('/auth/me', { signal: controller.signal }, accessToken).then((data) => setPrincipal(data.id || '')).catch((failure) => { if (!controller.signal.aborted) setError(errorMessage(failure)); }).finally(() => { if (!controller.signal.aborted) setPrincipalLoaded(true); });
    request(`/organizations/${encodeURIComponent(organizationId)}/agents`, { signal: controller.signal }, accessToken).then(setAgents).catch((failure) => { if (!controller.signal.aborted) setError(errorMessage(failure)); });
    return () => controller.abort();
  }, [organizationId, accessToken, request, errorMessage]);
  useEffect(() => {
    if (teamsLoading || teamsError || !agents) return;
    const controller = new AbortController();
    setMembersLoading(true);
    Promise.all(teams.map(async (team) => {
      try { return [team.id, await request(`/teams/${encodeURIComponent(team.id)}/members`, { signal: controller.signal }, accessToken)]; }
      catch { return [team.id, null]; }
    })).then((entries) => { if (!controller.signal.aborted) setMembers(Object.fromEntries(entries)); }).finally(() => { if (!controller.signal.aborted) setMembersLoading(false); });
    return () => controller.abort();
  }, [teams, teamsLoading, teamsError, agents, request, accessToken]);
  const owner = Boolean(principal && !principal.startsWith('agent:') && principal === organization?.ownerPrincipalId);
  const selected = agents?.find((agent) => agent.id === agentId);
  const allTeamsKnown = !teamsLoading && !teamsError && !membersLoading && teams.every((team) => Array.isArray(members[team.id]));
  const teamsWithAgents = allTeamsKnown ? teams.filter((team) => members[team.id]?.some((member) => agents?.some((agent) => agent.id === member.principalId))).length : null;
  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function createAgent(event) {
    event.preventDefault();
    if (!owner || !name.trim()) return;
    setBusy(true); setError('');
    try {
      const created = await request(`/organizations/${encodeURIComponent(organizationId)}/agents`, { method: 'POST', body: JSON.stringify({ name: name.trim() }) }, accessToken);
      window.location.assign(agentUrl(organizationId, 'teams', created.id));
    } catch (failure) { setError(errorMessage(failure)); setBusy(false); }
  }
  /** @param {Team} team */
  async function addToTeam(team) {
    if (!owner || !selected || !Array.isArray(members[team.id])) return;
    setBusy(true); setError('');
    try {
      const created = await request(`/teams/${encodeURIComponent(team.id)}/members`, { method: 'POST', body: JSON.stringify({ principalId: selected.id, role: 'viewer' }) }, accessToken);
      setMembers((current) => ({ ...current, [team.id]: [...(current[team.id] || []), created] }));
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setBusy(false); }
  }
  const listUrl = agentUrl(organizationId);
  if (error && !agents) return <section><p role="alert" className="alert">{error}</p></section>;
  if (!agents || !principalLoaded) return <p role="status">Agenten werden geladen …</p>;
  if (!owner) return <section><p role="alert" className="alert">Agenten können nur von Organisationsinhabern verwaltet werden.</p></section>;
  if (view === 'scope' || view === 'history') {
    if (!selected) return <section><p role="alert">Agent nicht gefunden oder nicht sichtbar.</p><a href={listUrl}>Zur Agentenliste</a></section>;
    return <AgentAccess organizationId={organizationId} agent={selected} view={view} accessToken={accessToken} request={request} errorMessage={errorMessage} setBusy={setBusy} />;
  }
  return <section className="agent-screen" aria-labelledby="agent-heading">
    {error && <p role="alert" className="alert">{error}</p>}
    {view === 'create' ? <><p className="eyebrow">AGENTEN / IDENTITÄT</p><h1 id="agent-heading">Agentenidentität registrieren</h1><p>Eine lokale nichtmenschliche Identität; keine externe Git-Identität oder Ausführung wird eingerichtet.</p><div className="agent-steps"><strong>1 Identität</strong><span>2 Teammitgliedschaft</span><span>3 Berechtigungen</span></div><div className="team-columns"><div className="panel"><h2>Agentenidentität</h2><form onSubmit={createAgent}><label className="field">Anzeigename<input value={name} onChange={(event) => setName(event.target.value)} required maxLength={200} /></label><p>Die Agenten-ID wird beim Speichern erzeugt. Eine externe Integration ist nicht hinterlegt.</p><button type="submit" disabled={busy}>Agent anlegen und Teams zuordnen →</button></form></div><div className="panel"><h2>Eigene Identität</h2><dl className="team-role-list"><div><dt>Principal-Typ</dt><dd>Agent</dd></div><div><dt>Verwaltung</dt><dd>Organisationsinhaber</dd></div><div><dt>Teamrolle</dt><dd>Viewer</dd></div></dl><div className="team-info">Eine Mitgliedschaft startet keinen Agenten und gewährt keine Git-Rechte.</div></div></div><a className="team-back" href={listUrl}>← Zurück</a></> : view === 'teams' ? <><p className="eyebrow">AGENTEN / MITGLIEDSCHAFT</p><h1 id="agent-heading">Agent einem Team zuordnen</h1><p>Teammitgliedschaften gewähren ausschließlich lesenden Zugriff.</p><div className="agent-steps"><span>1 Identität</span><strong>2 Teammitgliedschaft</strong><span>3 Berechtigungen</span></div>{!selected ? <p role="alert">Agent nicht gefunden oder nicht sichtbar.</p> : <div className="team-columns"><div className="panel"><h2>Teammitgliedschaft · {selected.name}</h2><p className="break-value">{selected.id}</p>{teamsError ? <p role="alert">{teamsError}</p> : teamsLoading || membersLoading ? <p role="status">Teams werden geladen …</p> : teams.length === 0 ? <p>Keine Teams vorhanden.</p> : <ul className="agent-team-list">{teams.map((team) => { const list = members[team.id]; const member = list?.find((entry) => entry.principalId === selected.id); return <li key={team.id}><strong>{team.name}</strong>{!Array.isArray(list) ? <span>Mitgliedschaft nicht verfügbar</span> : member ? <span className="team-role">{member.role}</span> : <button type="button" disabled={busy} onClick={() => addToTeam(team)}>Als Viewer hinzufügen</button>}</li>; })}</ul>}<div className="team-info">Teammitgliedschaft allein erteilt keine Repository-Zugangsdaten.</div></div><div className="panel"><h2>Zusammenarbeit in Git</h2><p>Menschen und Agenten arbeiten außerhalb von Specbound. Die Plattform verteilt keine Aufgaben.</p><p>Git-Rechte und externe Identitäten werden gesondert verwaltet.</p><a className="primary-link" href={agentUrl(organizationId, 'scope', selected.id)}>Rechte und Zugang ansehen →</a></div></div>}<a className="team-back" href={listUrl}>← Zur Agentenliste</a></> : <><p className="eyebrow">ORGANISATION / IDENTITÄTEN</p><div className="page-heading"><div><h1 id="agent-heading">Agentenidentitäten</h1><p>Eigenständige nichtmenschliche Principals und ihre Teammitgliedschaften.</p></div><a className="primary-link" href={agentUrl(organizationId, 'create')}>+ Agent registrieren</a></div><div className="team-metrics team-detail-metrics"><div className="panel"><span>Registrierte Agenten</span><strong>{agents.length}</strong></div><div className="panel"><span>Teams mit Agenten</span><strong>{teamsWithAgents ?? 'UNKNOWN'}</strong></div><div className="panel"><span>Git-Identität</span><strong>Nicht hinterlegt</strong></div><div className="panel"><span>Ausführung</span><strong>Nicht verwaltet</strong></div></div><div className="panel team-table-panel"><h2>Agenten</h2>{agents.length === 0 ? <p>Keine Agenten registriert.</p> : <><p className="pack-scroll-hint">Tabelle horizontal scrollen, um alle Spalten zu sehen.</p><div className="team-table-scroll" tabIndex={0} aria-label="Agenten, horizontal scrollbar"><table className="team-table"><thead><tr><th>IDENTITÄT</th><th>TEAMS</th><th>ROLLE</th><th>INTEGRATION</th></tr></thead><tbody>{agents.map((agent) => <tr key={agent.id}><td><a href={agentUrl(organizationId, 'teams', agent.id)}>{agent.name}</a><small>{agent.id}</small></td><td>{!allTeamsKnown ? 'Nicht vollständig verfügbar' : teams.filter((team) => members[team.id]?.some((member) => member.principalId === agent.id)).map((team) => team.name).join(', ') || 'Keine'}</td><td>Viewer in zugeordneten Teams</td><td>Nicht hinterlegt</td></tr>)}</tbody></table></div></>}</div><div className="team-info">Agenten sind einzelne Teammitglieder. Teamrollen und Git-Berechtigungen sind getrennt; Specbound startet keine Agentenausführung.</div></>}
  </section>;
}
