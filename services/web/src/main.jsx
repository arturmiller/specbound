import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';

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
        if (error.name !== 'AbortError') setStatus('API nicht erreichbar');
      });
    return () => controller.abort();
  }, []);

  return (
    <main>
      <h1>Specbound</h1>
      <p>Lokale Entwicklungsumgebung</p>
      <p role="status">{status}</p>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
