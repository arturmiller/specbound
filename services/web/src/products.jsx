import React, { useEffect, useState } from 'react';

/** @typedef {{id: string, name: string, ownerTeamId: string}} Product */
/** @typedef {{id: string, repository: string, provider: string}} Binding */
/** @typedef {{id: string, name: string}} Team */

/** @param {string} path @param {string} token @param {RequestInit} [options] */
async function request(path, token, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

/** @param {{organizationId: string, teams: Team[], accessToken?: string}} props */
export function ProductWorkspace({ organizationId, teams, accessToken = '' }) {
  const [products, setProducts] = useState(/** @type {Product[]} */ ([]));
  const [selectedId, setSelectedId] = useState(() => new URLSearchParams(location.search).get('product') || '');
  const [bindings, setBindings] = useState(/** @type {Binding[]} */ ([]));
  const [name, setName] = useState('');
  const [ownerTeam, setOwnerTeam] = useState('');
  const [repository, setRepository] = useState('');
  const [verification, setVerification] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [bindingsLoading, setBindingsLoading] = useState(false);
  const product = products.find((item) => item.id === selectedId);

  useEffect(() => {
    setOwnerTeam((current) => teams.some((team) => team.id === current) ? current : (teams[0]?.id || ''));
  }, [teams]);

  useEffect(() => {
    const controller = new AbortController();
    request(`/organizations/${encodeURIComponent(organizationId)}/products`, accessToken, { signal: controller.signal })
      .then((/** @type {Product[]} */ data) => {
        setProducts(data);
        setSelectedId((current) => data.some((item) => item.id === current) ? current : (data[0]?.id || ''));
        setReady(true);
      })
      .catch(() => { if (!controller.signal.aborted) setError('Produkte konnten nicht geladen werden.'); });
    return () => controller.abort();
  }, [organizationId, accessToken]);

  useEffect(() => {
    setBindings([]); setVerification('');
    if (!selectedId) { setBindingsLoading(false); return; }
    const controller = new AbortController();
    setBindingsLoading(true);
    request(`/products/${encodeURIComponent(selectedId)}/repositories`, accessToken, { signal: controller.signal })
      .then((/** @type {Binding[]} */ data) => setBindings(data))
      .catch(() => { if (!controller.signal.aborted) setError('Repositories konnten nicht geladen werden.'); })
      .finally(() => { if (!controller.signal.aborted) setBindingsLoading(false); });
    return () => controller.abort();
  }, [selectedId, accessToken]);

  useEffect(() => {
    if (!ready) return;
    const url = new URL(location.href);
    if (selectedId) url.searchParams.set('product', selectedId); else url.searchParams.delete('product');
    history.replaceState(null, '', url);
  }, [selectedId, ready]);

  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function createProduct(event) {
    event.preventDefault();
    if (!name.trim() || !ownerTeam) return;
    setBusy(true); setError('');
    try {
      /** @type {Product} */ const created = await request(`/organizations/${encodeURIComponent(organizationId)}/products`, accessToken, {
        method: 'POST', body: JSON.stringify({ name: name.trim(), ownerTeamId: ownerTeam }),
      });
      setProducts((current) => [...current, created]); setSelectedId(created.id); setName('');
    } catch { setError('Produkt konnte nicht erstellt werden.'); }
    finally { setBusy(false); }
  }

  /** @param {string} productId @param {string} bindingId @param {string} repositoryName */
  async function verify(productId, bindingId, repositoryName) {
    try {
      await request(`/products/${encodeURIComponent(productId)}/repositories/${encodeURIComponent(bindingId)}/github`, accessToken);
      setVerification(`${repositoryName}: GitHub-Zugriff bestätigt`);
    } catch { setVerification(`${repositoryName}: GitHub-Zugriff konnte nicht bestätigt werden. Das Repository bleibt gespeichert.`); }
  }

  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function connect(event) {
    event.preventDefault();
    if (!selectedId || !repository.trim()) return;
    setBusy(true); setError(''); setVerification('');
    try {
      /** @type {Binding} */ const binding = await request(`/products/${encodeURIComponent(selectedId)}/repositories`, accessToken, {
        method: 'POST', body: JSON.stringify({ provider: 'github', repository: repository.trim() }),
      });
      setBindings((current) => [...current, binding]); setRepository('');
      await verify(selectedId, binding.id, binding.repository);
    } catch { setError('Repository konnte nicht verbunden werden. Das Produkt bleibt gespeichert.'); }
    finally { setBusy(false); }
  }

  return <section aria-labelledby="products-heading" className="workspace">
    <div className="workspace-heading"><div><p className="eyebrow">INVENTAR</p><h2 id="products-heading">Produkte</h2></div>
      <p>Produkte ihren Teams und Git-Repositories zuordnen.</p></div>
    {error && <p role="alert" className="alert">{error}</p>}
    <div className="workspace-grid">
      <div className="panel"><h3>Produktliste</h3>
        {ready && products.length === 0 && <p>Noch keine Produkte vorhanden.</p>}
        <ul className="team-list">{products.map((item) => <li key={item.id}><button className="team-choice" type="button" disabled={busy} aria-pressed={selectedId === item.id} onClick={() => { setSelectedId(item.id); setError(''); }}>{item.name}</button></li>)}</ul>
        <form onSubmit={createProduct}>
          <label className="field">Produktname<input required maxLength={200} value={name} onChange={(event) => setName(event.target.value)} /></label>
          <label className="field">Owner-Team<select value={ownerTeam} onChange={(event) => setOwnerTeam(event.target.value)} required><option value="" disabled>Team auswählen</option>{teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select></label>
          <button type="submit" disabled={busy || !ownerTeam || !ready}>Produkt erstellen</button>
        </form>
      </div>
      <div className="panel"><h3>Produktdetails</h3>{product ? <>
        <p><strong>{product.name}</strong></p>
        <p>Owner-Team: {teams.find((team) => team.id === product.ownerTeamId)?.name || product.ownerTeamId}</p>
        <h4>Git-Repositories</h4>
        {bindingsLoading ? <p>Repositories werden geladen …</p> : bindings.length === 0 && <p>Noch kein Repository verbunden.</p>}
        <ul>{bindings.map((binding) => <li key={binding.id}><span>{binding.repository}</span>{binding.provider.toLowerCase() === 'github' && <button type="button" disabled={busy} onClick={() => { setBusy(true); void verify(product.id, binding.id, binding.repository).finally(() => setBusy(false)); }}>Zugriff prüfen</button>}</li>)}</ul>
        {verification && <p role="status">{verification}</p>}
        <form onSubmit={connect}><label className="field">Git-Repository<input required maxLength={200} placeholder="owner/repository" value={repository} onChange={(event) => setRepository(event.target.value)} /></label>
          <button type="submit" disabled={busy || bindingsLoading}>Repository verbinden</button></form>
      </> : <p>Wähle ein Produkt aus.</p>}</div>
    </div>
  </section>;
}
