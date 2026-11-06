import React, { useEffect, useState } from 'react';
import { UserManager, WebStorageStateStore } from 'oidc-client-ts';
import { TeamWorkspace } from './teams.jsx';

/** @typedef {{enabled: boolean, issuer: string, clientId: string, audience: string}} AuthConfig */

export function AuthWorkspace() {
  const [ready, setReady] = useState(false);
  const [configured, setConfigured] = useState(false);
  const [error, setError] = useState('');
  const [manager, setManager] = useState(/** @type {UserManager | null} */ (null));
  const [user, setUser] = useState(/** @type {import('oidc-client-ts').User | null} */ (null));

  useEffect(() => {
    let active = true;
    let cleanup = () => {};
    async function initialize() {
      try {
        const response = await fetch('/api/auth/config');
        if (!response.ok) throw new Error('Authentication configuration unavailable');
        /** @type {AuthConfig} */
        const config = await response.json();
        if (!active) return;
        if (!config.enabled) { if (active) setReady(true); return; }
        if (!window.isSecureContext) throw new Error('Secure browser context required');
        const oidc = new UserManager({
          authority: config.issuer,
          client_id: config.clientId,
          redirect_uri: `${window.location.origin}/`,
          response_type: 'code',
          scope: 'openid profile',
          resource: config.audience,
          automaticSilentRenew: false,
          loadUserInfo: false,
          userStore: new WebStorageStateStore({ store: window.sessionStorage }),
          stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
        });
        const onExpired = () => { if (active) setUser(null); void oidc.removeUser(); };
        oidc.events.addAccessTokenExpired(onExpired);
        cleanup = () => oidc.events.removeAccessTokenExpired(onExpired);
        let current;
        const params = new URLSearchParams(window.location.search);
        if (params.has('code') || (params.has('error') && params.has('state'))) {
          try { current = await oidc.signinRedirectCallback(); }
          finally { window.history.replaceState(null, '', window.location.pathname); }
        } else {
          current = await oidc.getUser();
        }
        if (current?.expired) { await oidc.removeUser(); current = null; }
        if (active) { setManager(oidc); setUser(current); setConfigured(true); setReady(true); }
      } catch {
        if (active) { setError('Anmeldung konnte nicht initialisiert werden.'); setReady(true); }
      }
    }
    void initialize();
    return () => { active = false; cleanup(); };
  }, []);

  if (!ready) return <p>Authentifizierung wird vorbereitet …</p>;
  if (error) return <p role="alert">{error}</p>;
  if (!configured) return <TeamWorkspace />;
  if (!user) return <section><p>Bitte anmelden, um Teams zu verwalten.</p><button onClick={() => { void manager?.signinRedirect({ nonce: crypto.randomUUID() }).catch(() => setError('Anmeldung konnte nicht gestartet werden.')); }}>Anmelden</button></section>;
  return <>
    <p>Angemeldet. <button onClick={() => { void manager?.removeUser().then(() => setUser(null)).catch(() => setError('Lokale Abmeldung fehlgeschlagen.')); }}>Lokal abmelden</button></p>
    <TeamWorkspace key={user.profile.sub} accessToken={user.access_token} />
  </>;
}
