import React, { useEffect, useState } from 'react';
import { CatalogControls } from './resources.jsx';
import { ManifestProvenance } from './manifest-source.jsx';

/** @param {{productId: string, organizationId: string, accessToken: string}} props */
export function ProductGovernance({ productId, organizationId, accessToken }) {
  const scope = `${productId}:${accessToken}`;
  const [state, setState] = useState(/** @type {{scope: string, value: {state: string, product: import('./resources.jsx').Resource | null, profile: import('./resources.jsx').Resource | null} | null, error: string}} */ ({ scope: '', value: null, error: '' }));
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/products/${encodeURIComponent(productId)}/governance`, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then(async (response) => { if (!response.ok) throw new Error('Der Geltungsbereich konnte nicht geladen werden.'); return response.json(); })
      .then((value) => { if (!controller.signal.aborted) setState({ scope, value, error: '' }); })
      .catch((failure) => { if (!controller.signal.aborted) setState({ scope, value: null, error: failure.message }); });
    return () => controller.abort();
  }, [productId, accessToken, scope]);
  if (state.scope !== scope) return <p role="status">Geltungsbereich wird geladen …</p>;
  if (state.error) return <p role="alert">{state.error}</p>;
  const product = state.value?.product;
  const profile = state.value?.profile;
  return <section aria-label="Geltungsbereich" className="panel">
    <h2>Geltungsbereich</h2>
    {!product || !profile ? <><p>Ohne Profilzuordnung. Dieses bestehende Produkt hat noch kein Produktmanifest.</p><p>Frühere Prüfungen behalten ihren damaligen Stand. Eine Zuordnung wird nicht aus Repositorynamen oder Subject-Typen abgeleitet.</p></> : <>
      <p>Produkt: {product.resourceId} · {product.version}</p>
      <p>Geltendes Profil: <a href={`/profiles?${new URLSearchParams({ organization: organizationId, resource: profile.id || '' })}`}>{profile.name} · {profile.version}</a></p>
      <p>Katalog: <a href={`/catalogs?${new URLSearchParams({ organization: organizationId, resource: profile.resolved.catalog?.revisionId || '' })}`}>{profile.resolved.catalog?.name} · {profile.resolved.catalog?.version}</a></p>
      <ManifestProvenance source={product.source} defaultPath={product.source.manifestPath} />
      <p>Produktquellen:</p><ul>{product.resolved.repositories?.map((repository) => <li key={repository.repository}><a href={`https://github.com/${repository.repository}`}>{repository.repository}</a></li>)}</ul>
      <p>Die Profilwahl wird im Produktmanifest geändert. Gemeinsame Anforderungen und Parameter werden in einer neuen Profilversion geändert und anschließend ausdrücklich übernommen.</p>
      <p>{profile.resolved.controls.length} ausdrücklich zugeordnete Controls:</p>
      <CatalogControls resource={profile} />
    </>}
  </section>;
}
