import React, { useEffect, useState } from 'react';
import { RunList, resultBadge } from './run-list.jsx';

/** @typedef {{id: string, productId: string, context: string, pullRequestNumber: number | null, createdAt: string, counts?: import('./run-list.jsx').EvaluationCounts}} Snapshot */
/** @typedef {{products: {id: string, name: string}[], assessments: Snapshot[]}} Overview */

/** @param {{organizationId: string, accessToken?: string}} props */
export function PullRequestAssessments({ organizationId, accessToken = '' }) {
  const [data, setData] = useState(/** @type {Overview | null} */ (null));
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/organizations/${encodeURIComponent(organizationId)}/overview`, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then((response) => { if (!response.ok) throw new Error(response.status === 403 ? 'Für diese Assessments fehlen die erforderlichen Rechte.' : 'Assessments konnten nicht geladen werden.'); return response.json(); })
      .then(setData).catch((failure) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [organizationId, accessToken]);
  const snapshots = data?.assessments.filter((item) => item.context === 'pull_request') || [];
  const productNames = new Map(data?.products.map((product) => [product.id, product.name]));
  const runs = snapshots.map((snapshot) => {
    const productName = productNames.get(snapshot.productId) || 'Produkt';
    return {
      id: snapshot.id,
      href: `/assessments/${encodeURIComponent(snapshot.id)}`,
      label: snapshot.pullRequestNumber == null ? productName : `${productName} · PR #${snapshot.pullRequestNumber}`,
      createdAt: snapshot.createdAt,
      ...resultBadge(snapshot.counts),
    };
  });
  return <section className="pr-screen" aria-labelledby="pr-heading">
    <div className="page-heading"><h1 id="pr-heading">PR-Prüfungen</h1></div>
    {error ? <p role="alert" className="alert">{error}</p> : !data ? <p role="status">Assessments werden geladen …</p> : runs.length === 0 ? <p>Keine sichtbaren PR-Assessments gespeichert.</p> : <RunList runs={runs} label="Gespeicherte PR-Prüfungen" />}
  </section>;
}
