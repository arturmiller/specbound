import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { AuthWorkspace } from './auth.jsx';
import { Documentation } from './docs.jsx';
import './styles.css';

function App() {
  const [status, setStatus] = useState('Verbindung wird geprüft …');

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/healthz', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('API unavailable');
        return response.json();
      })
      .then((data) => setStatus(data.status === 'ok' ? 'API erreichbar' : 'API nicht bereit'))
      .catch((error) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setStatus('API nicht erreichbar');
        }
      });
    return () => controller.abort();
  }, []);

  return (
    <main>
      <h1>Specbound</h1>
      <p>Lokale Entwicklungsumgebung</p>
      <p role="status">{status}</p>
      <AuthWorkspace />
      <Documentation />
    </main>
  );
}

const root = document.getElementById('root');
if (!root) throw new Error('Missing root element');
createRoot(root).render(<App />);
