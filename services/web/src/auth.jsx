import React, { useEffect, useState } from 'react';
import { UserManager, WebStorageStateStore } from 'oidc-client-ts';
import { TeamWorkspace } from './teams.jsx';
import { Documentation } from './docs.jsx';

/** @typedef {{enabled: boolean, issuer: string, clientId: string, audience: string}} AuthConfig */

/** @param {{apiStatus: string}} props */
export function AuthWorkspace({ apiStatus }) {
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
          let target = '/';
          try {
            current = await oidc.signinRedirectCallback();
            const state = current?.state;
            if (state && typeof state === 'object' && 'returnTo' in state && typeof state.returnTo === 'string') {
              const requested = state.returnTo;
              if (requested.startsWith('/') && !requested.startsWith('//')) {
                const url = new URL(requested, window.location.origin);
                if (url.origin === window.location.origin && /^(?:\/(?:settings|teams|products|packs|overview|agents|findings|pr-checks|evidence|providers|docs)?\/?|\/assessments\/[A-Za-z0-9_-]{1,100}\/?)$/.test(url.pathname)) {
                  target = `${url.pathname}${url.search}${url.hash}`;
                }
              }
            }
          }
          finally { window.history.replaceState(null, '', target); }
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

  if (!ready) return <main className="login-screen"><p>Authentifizierung wird vorbereitet …</p></main>;
  if (error) return <main className="login-screen"><p role="alert">{error}</p></main>;
  if (!configured) return <TeamWorkspace apiStatus={apiStatus} />;
  if (!user) return <main className="login-screen"><div className="login-card"><span className="brand-mark" aria-hidden="true">◇</span><h1>Specbound</h1>
    <p>Bitte anmelden, um fortzufahren.</p><button onClick={() => { void manager?.signinRedirect({ nonce: crypto.randomUUID(), state: { returnTo: `${window.location.pathname}${window.location.search}${window.location.hash}` } }).catch(() => setError('Anmeldung konnte nicht gestartet werden.')); }}>Anmelden</button>
    <a className="public-doc-link" href="/docs">Dokumentation öffnen</a>
    {window.location.pathname === '/docs' && <Documentation />}</div></main>;
  return <TeamWorkspace key={user.profile.sub} accessToken={user.access_token} apiStatus={apiStatus} authConfigured
    onSignOut={() => { void manager?.removeUser().then(() => setUser(null)).catch(() => setError('Lokale Abmeldung fehlgeschlagen.')); }} />;
}
