import React, { useEffect, useState } from 'react';

/** @typedef {{id: string, name: string}} Agent */
/** @typedef {{id: string, expiresAt: string, revokedAt: string | null}} Credential */
/** @typedef {{id: string, actorId: string, action: string, targetId: string, teamId: string | null, occurredAt: string}} AuditEvent */
/** @typedef {(path: string, options?: RequestInit, accessToken?: string) => Promise<any>} Request */

/** @param {{organizationId: string, agent: Agent, view: string, accessToken: string, request: Request, errorMessage: (error: unknown) => string, setBusy: (busy: boolean) => void}} props */
export function AgentAccess({ organizationId, agent, view, accessToken, request, errorMessage, setBusy }) {
  const [credentials, setCredentials] = useState(/** @type {Credential[] | null} */ (null));
  const [events, setEvents] = useState(/** @type {AuditEvent[] | null} */ (null));
  const [secret, setSecret] = useState('');
  const [error, setError] = useState('');
  const [credentialsError, setCredentialsError] = useState('');
  const [eventsError, setEventsError] = useState('');
  const [waiting, setWaiting] = useState(false);
  const [now, setNow] = useState(Date.now());
  const root = `/organizations/${encodeURIComponent(organizationId)}/agents/${encodeURIComponent(agent.id)}/credentials`;
  /** @param {string} target */
  const link = (target) => `/agents?${new URLSearchParams({ organization: organizationId, agent: agent.id, view: target })}`;
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 10000); return () => window.clearInterval(timer); }, []);
  useEffect(() => {
    const controller = new AbortController();
    request(root, { signal: controller.signal, cache: 'no-store' }, accessToken).then(setCredentials).catch((failure) => { if (!controller.signal.aborted) setCredentialsError(errorMessage(failure)); });
    request(`/organizations/${encodeURIComponent(organizationId)}/audit-events`, { signal: controller.signal, cache: 'no-store' }, accessToken).then((/** @type {AuditEvent[]} */ rows) => setEvents(rows.filter((event) => event.targetId === agent.id).reverse())).catch((failure) => { if (!controller.signal.aborted) setEventsError(errorMessage(failure)); });
    return () => controller.abort();
  }, [root, organizationId, agent.id, accessToken, request, errorMessage]);
  async function issue() {
    setWaiting(true); setBusy(true); setError(''); setSecret('');
    try {
      const issued = await request(root, { method: 'POST', cache: 'no-store' }, accessToken);
      setCredentials((current) => [{ id: issued.id, expiresAt: issued.expiresAt, revokedAt: null }, ...(current || [])]);
      setSecret(issued.token);
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setWaiting(false); setBusy(false); }
  }
  /** @param {Credential} credential */
  async function revoke(credential) {
    setWaiting(true); setBusy(true); setError('');
    try {
      await request(`${root}/${encodeURIComponent(credential.id)}`, { method: 'DELETE', cache: 'no-store' }, accessToken);
      setCredentials((current) => current?.map((entry) => entry.id === credential.id ? { ...entry, revokedAt: new Date().toISOString() } : entry) || []);
      setSecret('');
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setWaiting(false); setBusy(false); }
  }
  /** @param {Credential} entry */
  function status(entry) {
    if (entry.revokedAt) return 'Widerrufen';
    const expires = Date.parse(entry.expiresAt);
    if (!Number.isFinite(expires)) return 'UNKNOWN';
    return expires <= now ? 'Abgelaufen' : 'Gültig';
  }
  return <section className="agent-screen" aria-labelledby="agent-access-heading">
    <p className="eyebrow">AGENTEN / {view === 'history' ? 'AUDIT' : 'BERECHTIGUNGEN'}</p><h1 id="agent-access-heading">{view === 'history' ? 'Agentenaktivität und Audit' : 'Agentenrechte und Zugang'}</h1><p>{agent.name} · <span className="break-value">{agent.id}</span></p>
    <nav className="pr-tabs" aria-label="Agentenansichten"><a href={link('teams')}>Teams</a><a href={link('scope')} aria-current={view === 'scope' ? 'page' : undefined}>Rechte und Zugang</a><a href={link('history')} aria-current={view === 'history' ? 'page' : undefined}>Audit</a></nav>
    {error && <p role="alert" className="alert">{error}</p>}
    {view === 'scope' ? <><div className="agent-steps"><span>1 Identität</span><span>2 Teammitgliedschaft</span><strong>3 Berechtigungen</strong></div><div className="team-columns"><div className="panel"><h2>Rechte und Grenzen</h2><dl className="team-role-list"><div><dt>Teamdaten und Assessments</dt><dd>Lesen in zugewiesenen Teams</dd></div><div><dt>Organisations- und Teamverwaltung</dt><dd>Nicht erlaubt</dd></div><div><dt>Governance-Packfreigabe</dt><dd>Nicht erlaubt</dd></div><div><dt>Git-Rechte</dt><dd>Separat in Git verwaltet</dd></div></dl><div className="team-info">Eine Registrierung startet keinen Agenten und vergibt keine Git-Rechte.</div></div><div className="panel"><h2>Lokaler Zugang</h2><p>Ein menschlicher Organisationsinhaber kann einen lokalen Zugang für eine Stunde ausstellen und widerrufen.</p><button type="button" disabled={waiting || !credentials} onClick={issue}>Zugang ausstellen</button>{secret && <div className="team-info" role="status"><strong>Token einmalig sichtbar</strong><p>Jetzt sicher übernehmen. Beim Verlassen oder Neuladen dieser Seite wird es nicht erneut angezeigt.</p><code className="agent-secret">{secret}</code><p><button type="button" onClick={() => setSecret('')}>Token ausblenden</button></p></div>}<h3>Ausgestellte Zugänge</h3>{credentialsError ? <p role="alert">{credentialsError}</p> : !credentials ? <p role="status">Zugänge werden geladen …</p> : credentials.length === 0 ? <p>Keine Zugänge ausgestellt.</p> : <ul className="agent-credentials">{credentials.map((entry) => <li key={entry.id}><div><strong className="break-value">{entry.id}</strong><small>Gültig bis: {entry.expiresAt} · {status(entry)}</small></div>{!entry.revokedAt && <button type="button" disabled={waiting} onClick={() => revoke(entry)}>Widerrufen</button>}</li>)}</ul>}</div></div></> : <><div className="team-metrics team-detail-metrics"><div className="panel"><span>Identität</span><strong>{agent.name}</strong></div><div className="panel"><span>Zugang</span><strong>Lokal · zeitlich begrenzt</strong></div><div className="panel"><span>Git-Aktivität</span><strong>Nicht verfügbar</strong></div><div className="panel"><span>Auditquelle</span><strong>Specbound</strong></div></div><div className="panel team-table-panel"><h2>Audit-Ereignisse</h2>{eventsError ? <p role="alert">{eventsError}</p> : !events ? <p role="status">Audit wird geladen …</p> : events.length === 0 ? <p>Keine Audit-Ereignisse für diesen Agenten.</p> : <><p className="pack-scroll-hint">Tabelle horizontal scrollen, um alle Spalten zu sehen.</p><div className="team-table-scroll" tabIndex={0} aria-label="Audit-Ereignisse, horizontal scrollbar"><table className="team-table agent-audit-table"><thead><tr><th>ZEIT</th><th>EREIGNIS</th><th>AKTEUR</th><th>TEAM</th></tr></thead><tbody>{events.map((event) => <tr key={event.id}><td>{event.occurredAt}</td><td>{event.action}</td><td className="break-value">{event.actorId}</td><td>{event.teamId || '–'}</td></tr>)}</tbody></table></div></>}</div><div className="team-columns"><div className="panel"><h2>Verantwortung</h2><p>Die aufgeführten Ereignisse stammen aus dem Specbound-Audit.</p></div><div className="panel"><h2>Externe Aktivität</h2><p>Git-Commits, PR-Aktivität und externe Ausführungen sind nicht verfügbar und werden hier nicht angenommen.</p></div></div></>}
    <a className="team-back" href={`/agents?${new URLSearchParams({ organization: organizationId })}`}>← Zur Agentenliste</a>
  </section>;
}
