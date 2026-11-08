import React, { useEffect, useState } from 'react';

/** @typedef {{id: string, name: string, ownerPrincipalId?: string}} Organization */
/** @typedef {{id: string, name: string}} Team */
/** @typedef {{id: string, principalId: string, role: string}} Member */
/** @typedef {{id: string, name: string, ownerTeamId: string}} Product */
/** @typedef {(path: string, options?: RequestInit, accessToken?: string) => Promise<any>} Request */

/** @param {string} organizationId @param {string} [teamId] @param {string} [view] */
function teamUrl(organizationId, teamId = '', view = '') {
  const params = new URLSearchParams({ organization: organizationId });
  if (teamId) params.set('team', teamId);
  if (view) params.set('view', view);
  return `/teams?${params}`;
}

/** @param {{organization?: Organization, teams: Team[], teamsLoading: boolean, teamsError: string, accessToken: string, request: Request, errorMessage: (error: unknown) => string, onBusyChange: (busy: boolean) => void}} props */
export function TeamsScreen({ organization, teams, teamsLoading, teamsError, accessToken, request, errorMessage, onBusyChange }) {
  const organizationId = organization?.id || '';
  const params = new URLSearchParams(window.location.search);
  const selectedId = params.get('team') || '';
  const view = params.get('view') || (selectedId ? 'detail' : 'list');
  const selected = teams.find((team) => team.id === selectedId);
  const [principal, setPrincipal] = useState('');
  const [principalError, setPrincipalError] = useState('');
  const [memberMap, setMemberMap] = useState(/** @type {Record<string, Member[] | null>} */ ({}));
  const [memberLoading, setMemberLoading] = useState(false);
  const [products, setProducts] = useState(/** @type {Product[] | null} */ (null));
  const [productsLoading, setProductsLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState('');
  const [newPrincipal, setNewPrincipal] = useState('');
  const [role, setRole] = useState('viewer');

  useEffect(() => {
    onBusyChange(busy);
    return () => onBusyChange(false);
  }, [busy, onBusyChange]);

  useEffect(() => {
    const controller = new AbortController();
    request('/auth/me', { signal: controller.signal }, accessToken)
      .then((data) => setPrincipal(data.id))
      .catch((failure) => { if (!controller.signal.aborted) setPrincipalError(errorMessage(failure)); });
    return () => controller.abort();
  }, [accessToken, request, errorMessage]);

  useEffect(() => {
    const controller = new AbortController();
    setProductsLoading(true);
    request(`/organizations/${encodeURIComponent(organizationId)}/products`, { signal: controller.signal }, accessToken)
      .then((data) => setProducts(data))
      .catch(() => { if (!controller.signal.aborted) setProducts(null); })
      .finally(() => { if (!controller.signal.aborted) setProductsLoading(false); });
    return () => controller.abort();
  }, [organizationId, accessToken, request]);

  useEffect(() => {
    if (teamsLoading || teamsError) return;
    const controller = new AbortController();
    setMemberLoading(true);
    Promise.all(teams.map(async (team) => {
      try { return [team.id, await request(`/teams/${encodeURIComponent(team.id)}/members`, { signal: controller.signal }, accessToken)]; }
      catch { return [team.id, null]; }
    })).then((entries) => { if (!controller.signal.aborted) setMemberMap(Object.fromEntries(entries)); })
      .finally(() => { if (!controller.signal.aborted) setMemberLoading(false); });
    return () => controller.abort();
  }, [teams, teamsLoading, teamsError, accessToken, request]);

  const isOwner = Boolean(principal && !principal.startsWith('agent:') && principal === organization?.ownerPrincipalId);
  const selectedMembers = selectedId ? memberMap[selectedId] : null;
  const canManage = isOwner || Boolean(principal && !principal.startsWith('agent:') && selectedMembers?.some((member) => member.principalId === principal && member.role === 'admin'));
  const allMembersKnown = !memberLoading && teams.every((team) => Array.isArray(memberMap[team.id]));
  const membersTotal = allMembersKnown ? teams.reduce((sum, team) => sum + (memberMap[team.id]?.length || 0), 0) : null;

  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function createTeam(event) {
    event.preventDefault();
    if (!name.trim() || !isOwner) return;
    setBusy(true); setError('');
    try {
      const team = await request(`/organizations/${encodeURIComponent(organizationId)}/teams`, { method: 'POST', body: JSON.stringify({ name: name.trim() }) }, accessToken);
      window.location.assign(teamUrl(organizationId, team.id, 'members'));
    } catch (failure) { setError(errorMessage(failure)); setBusy(false); }
  }

  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function addMember(event) {
    event.preventDefault();
    if (!newPrincipal.trim() || !canManage) return;
    setBusy(true); setError('');
    try {
      const member = await request(`/teams/${encodeURIComponent(selectedId)}/members`, { method: 'POST', body: JSON.stringify({ principalId: newPrincipal.trim(), role }) }, accessToken);
      setMemberMap((current) => ({ ...current, [selectedId]: [...(current[selectedId] || []), member] }));
      setNewPrincipal('');
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setBusy(false); }
  }

  /** @param {Member} member @param {string} nextRole */
  async function changeRole(member, nextRole) {
    if (!canManage) return;
    setBusy(true); setError('');
    try {
      const changed = await request(`/teams/${encodeURIComponent(selectedId)}/members/${encodeURIComponent(member.id)}`, { method: 'PATCH', body: JSON.stringify({ role: nextRole }) }, accessToken);
      setMemberMap((current) => ({ ...current, [selectedId]: (current[selectedId] || []).map((item) => item.id === member.id ? changed : item) }));
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setBusy(false); }
  }

  /** @param {Member} member */
  async function removeMember(member) {
    if (!canManage || !window.confirm(`${member.principalId} aus dem Team entfernen?`)) return;
    setBusy(true); setError('');
    try {
      await request(`/teams/${encodeURIComponent(selectedId)}/members/${encodeURIComponent(member.id)}`, { method: 'DELETE' }, accessToken);
      setMemberMap((current) => ({ ...current, [selectedId]: (current[selectedId] || []).filter((item) => item.id !== member.id) }));
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setBusy(false); }
  }

  const listUrl = teamUrl(organizationId);
  const detailUrl = teamUrl(organizationId, selectedId);
  const membersUrl = teamUrl(organizationId, selectedId, 'members');
  return <section className="teams-screen" aria-labelledby="teams-title">
    {error && <p className="alert" role="alert">{error}</p>}
    {principalError && <p className="alert" role="alert">Die eigenen Berechtigungen konnten nicht geladen werden. {principalError}</p>}
    {teamsError && <p className="alert" role="alert">Teams konnten nicht geladen werden. {teamsError}</p>}
    {teamsLoading ? <p role="status">Teams werden geladen …</p> : teamsError ? null : view === 'list' ? <>
      <p className="eyebrow">ORGANISATION / VERANTWORTUNG</p>
      <div className="page-heading"><div><h1 id="teams-title">Teams</h1><p>Verantwortung für Produkte, Findings und Evidence zuordnen.</p></div>
        {isOwner && <a className="primary-link" href={teamUrl(organizationId, '', 'create')}>+ Team erstellen</a>}</div>
      <div className="team-metrics"><div className="panel"><span>Registrierte Teams</span><strong>{teams.length}</strong></div>
        <div className="panel"><span>Teammitgliedschaften</span><strong>{memberLoading ? '…' : membersTotal ?? 'Nicht verfügbar'}</strong></div>
        <div className="panel"><span>Sichtbare Produkte</span><strong>{productsLoading ? '…' : products?.length ?? 'Nicht verfügbar'}</strong></div></div>
      <div className="panel team-table-panel"><h2>Teamliste</h2>{teams.length === 0 ? <p>Noch keine Teams vorhanden.</p> : <div className="team-table-scroll"><table className="team-table"><thead><tr><th>TEAM</th><th>TEAM-ADMINS</th><th>MITGLIEDER</th><th>PRODUKTE</th></tr></thead><tbody>
        {teams.map((team) => <tr key={team.id}><td><a href={teamUrl(organizationId, team.id)}>{team.name}</a><small>{team.id}</small></td><td>{memberLoading ? 'Wird geladen …' : memberMap[team.id] ? memberMap[team.id]?.filter((member) => member.role === 'admin').map((member) => member.principalId).join(', ') || 'Keine' : 'Nicht verfügbar'}</td><td>{memberLoading ? '…' : memberMap[team.id]?.length ?? 'Nicht verfügbar'}</td><td>{productsLoading ? '…' : products?.filter((product) => product.ownerTeamId === team.id).length ?? 'Nicht verfügbar'}</td></tr>)}
      </tbody></table></div>}</div>
      <div className="team-info">Teams können Menschen und Agenten enthalten. Agenten haben ausschließlich lesenden Teamzugriff.</div>
    </> : view === 'create' ? <>
      <p className="eyebrow">TEAMS / NEUES TEAM</p><div className="page-heading"><div><h1 id="teams-title">Team erstellen</h1><p>Schritt 1 von 3 — Verantwortungsbereich benennen.</p></div></div>
      <Steps active={1} /><div className="team-columns"><div className="panel"><h2>Teamdetails</h2>
        {isOwner ? <form onSubmit={createTeam}><label className="field">Teamname<input value={name} onChange={(event) => setName(event.target.value)} required maxLength={200} /></label><button type="submit" disabled={busy}>Team erstellen und weiter →</button></form> : <p>Nur Organisationseigentümer können Teams erstellen.</p>}</div>
        <div className="panel"><h2>Verantwortung des Teams</h2><p>Produkte werden einem Team zugeordnet. Mitglieder und ihre Rollen lassen sich nach der Erstellung verwalten.</p><p>Beschreibung und Teamkennung werden derzeit nicht unterstützt.</p></div></div>
      <a className="team-back" href={listUrl}>← Zurück zu Teams</a>
    </> : !selected ? <><h1 id="teams-title">Team nicht verfügbar</h1><p>Das Team existiert nicht oder ist für dich nicht sichtbar.</p><a href={listUrl}>Zur Teamliste</a></> : <>
      <p className="eyebrow">TEAMS / {view === 'members' ? 'MITGLIEDER & ROLLEN' : 'TEAMDETAILS'}</p>
      <div className="page-heading"><div><h1 id="teams-title">{view === 'members' ? 'Mitglieder & Rollen' : selected.name}</h1><p>{view === 'members' ? 'Teamzugriff über einzelne Mitgliedschaften verwalten.' : 'Verantwortung und Mitgliedschaften des Teams.'}</p></div>
        {view !== 'members' && <a className="primary-link" href={membersUrl}>Mitglieder ansehen →</a>}</div>
      {view === 'members' && <Steps active={2} />}
      {view !== 'members' && <div className="team-metrics team-detail-metrics"><div className="panel"><span>Team-ID</span><strong>{selected.id}</strong></div><div className="panel"><span>Team-Admins</span><strong>{memberLoading ? '…' : selectedMembers ? selectedMembers.filter((member) => member.role === 'admin').length : 'Nicht verfügbar'}</strong></div><div className="panel"><span>Mitglieder</span><strong>{memberLoading ? '…' : selectedMembers?.length ?? 'Nicht verfügbar'}</strong></div><div className="panel"><span>Sichtbare Produkte</span><strong>{productsLoading ? '…' : products?.filter((product) => product.ownerTeamId === selected.id).length ?? 'Nicht verfügbar'}</strong></div></div>}
      <div className={`team-columns ${view !== 'members' ? 'team-detail-columns' : ''}`}><div className="panel"><h2>Teammitgliedschaften</h2>
        {memberLoading ? <p role="status">Mitglieder werden geladen …</p> : selectedMembers === null || selectedMembers === undefined ? <p role="alert">Mitglieder konnten nicht geladen werden. Prüfe deine Berechtigung.</p> : <>
          {selectedMembers.length === 0 ? <p>Noch keine Mitglieder vorhanden.</p> : <ul className="team-member-list">{selectedMembers.map((member) => <li key={member.id}><div><strong className="break-value">{member.principalId}</strong><small>{member.principalId.startsWith('agent:') ? 'Agent: Lesen; keine Pack-Freigabe' : 'Teammitglied'}</small></div>
            {canManage && view === 'members' && !member.principalId.startsWith('agent:') ? <label className="member-role"><span className="sr-only">Rolle von {member.principalId}</span><select value={member.role} disabled={busy} onChange={(event) => changeRole(member, event.target.value)}><option value="viewer">Viewer</option><option value="maintainer">Maintainer</option><option value="admin">Admin</option></select></label> : <span className="team-role">{member.role}</span>}
            {canManage && view === 'members' && <button type="button" className="member-remove" aria-label={`Entfernen: ${member.principalId}`} disabled={busy} onClick={() => removeMember(member)}>Entfernen</button>}</li>)}</ul>}
          {canManage && view === 'members' && <form onSubmit={addMember} className="member-form"><label className="field">Principal-ID<input value={newPrincipal} onChange={(event) => setNewPrincipal(event.target.value)} required maxLength={200} /></label><label className="field">Rolle<select aria-label="Rolle" value={role} onChange={(event) => setRole(event.target.value)}><option value="viewer">Viewer</option><option value="maintainer">Maintainer</option><option value="admin">Admin</option></select></label><button type="submit" disabled={busy}>Mitglied hinzufügen</button></form>}
        </>}
      </div>{view === 'members' ? <div className="panel"><h2>Rollendefinitionen</h2>
        <dl className="team-role-list"><div><dt>Admin</dt><dd>Mitglieder und Team verwalten</dd></div><div><dt>Maintainer</dt><dd>Teamressourcen bearbeiten</dd></div><div><dt>Viewer</dt><dd>Teamressourcen lesen</dd></div></dl>
        <div className="team-info">Teamrollen gewähren keine organisationsweiten Administrationsrechte. Agenten bleiben lesend.</div>
      </div> : <><div className="panel"><h2>Verantwortete Produkte</h2>
        {productsLoading ? <p>Produkte werden geladen …</p> : products === null ? <p>Produkte konnten nicht geladen werden.</p> : products.filter((product) => product.ownerTeamId === selected.id).length === 0 ? <p>Keine sichtbaren Produkte zugeordnet.</p> : <ul>{products.filter((product) => product.ownerTeamId === selected.id).map((product) => <li key={product.id}><a href={`/products?${new URLSearchParams({ organization: organizationId, product: product.id })}`}>{product.name}</a></li>)}</ul>}
        <a href={`/products?${new URLSearchParams({ organization: organizationId })}`}>Produktübersicht →</a>
      </div><div className="panel"><h2>Aufgaben & Benachrichtigungen</h2><p>Benachrichtigungen und Eskalationskontakte sind derzeit nicht verfügbar.</p><div className="team-info">Teamrollen gewähren keine organisationsweiten Administrationsrechte. Agenten bleiben lesend.</div></div></>}</div>
      <div className="team-actions"><a className="team-back" href={view === 'members' ? detailUrl : listUrl}>← {view === 'members' ? 'Teamdetails' : 'Alle Teams'}</a>{view === 'members' && <a className="primary-link" href={detailUrl}>Team ansehen →</a>}</div>
    </>}
  </section>;
}

/** @param {{active: number}} props */
function Steps({ active }) {
  return <ol className="team-steps" aria-label="Schritte der Teameinrichtung">{['Teamdetails', 'Mitglieder & Rollen', 'Team ansehen'].map((label, index) => <li key={label} aria-current={index + 1 === active ? 'step' : undefined}><span>{index + 1}</span>{label}</li>)}</ol>;
}
