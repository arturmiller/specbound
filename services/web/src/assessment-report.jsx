import React, { useEffect, useState } from 'react';

/** @typedef {{id: string, outcome: string, state: string, reason: string}} Finding */
/** @typedef {{id: string, status: string, reason: string, evidenceIds: string[], control: {id: string}, subject: {id: string, provenance?: {sourceRef?: string}}}} Evaluation */
/** @typedef {{id: string, capability: string, provenance?: {sourceRef?: string}, observedAt: string, expiresAt: string, value: unknown}} Evidence */
/** @typedef {{assessment: {id: string, gitSha: string, packSha: string, pullRequestNumber: number | null, environment: string, counts: {PASS: number, FAIL: number, UNKNOWN: number, NOT_APPLICABLE: number}}, evaluations: Evaluation[], evidence: Evidence[], findings: Finding[]}} Report */

/** @param {{id: string, accessToken?: string}} props */
export function AssessmentReport({ id, accessToken = '' }) {
  const [report, setReport] = useState(/** @type {Report | null} */ (null));
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/assessments/${encodeURIComponent(id)}`, {
      signal: controller.signal,
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    }).then(async (response) => {
      if (response.status === 403) throw new Error('Für dieses Assessment fehlen die erforderlichen Rechte.');
      if (response.status === 401) throw new Error('Für dieses Assessment ist eine Anmeldung erforderlich.');
      if (!response.ok) throw new Error('Assessment konnte nicht geladen werden.');
      return response.json();
    }).then(setReport).catch((failure) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [id, accessToken]);

  if (error) return <p role="alert">{error}</p>;
  if (!report) return <p>Assessment wird geladen …</p>;
  const { assessment, evaluations, evidence, findings } = report;
  return <section className="workspace assessment-report" aria-labelledby="assessment-heading">
    <h2 id="assessment-heading">Assessment-Bericht</h2>
    <dl><dt>Assessment</dt><dd>{assessment.id}</dd><dt>Revision</dt><dd>{assessment.gitSha}</dd>
      <dt>Governance-Pack</dt><dd>{assessment.packSha}</dd><dt>Pull Request</dt><dd>{assessment.pullRequestNumber ?? '–'}</dd>
      <dt>Umgebung</dt><dd>{assessment.environment}</dd></dl>
    <p>Passed: {assessment.counts.PASS} | Failed: {assessment.counts.FAIL} | Unknown: {assessment.counts.UNKNOWN} | N/A: {assessment.counts.NOT_APPLICABLE}</p>
    <h3>Findings</h3>
    {findings.length === 0 ? <p>Für diesen Snapshot wurden keine Finding-Ereignisse gespeichert.</p> :
      <ul>{findings.map((item) => <li key={item.id}>{item.outcome}: {item.state} – {item.reason}</li>)}</ul>}
    <h3>Controls und Bewertungen</h3>
    {evaluations.map((item) => <article key={item.id} className="panel">
      <h4>{item.control.id}: {item.status}</h4><p>{item.reason}</p>
      <p>Subject: {item.subject.id}</p><p>Quellverweis: {item.subject.provenance?.sourceRef || 'Nicht verfügbar'}</p>
      <p>Evidence: {item.evidenceIds.length ? item.evidenceIds.join(', ') : 'Keine'}</p>
      <details><summary>Control</summary><pre>{JSON.stringify(item.control, null, 2)}</pre></details>
    </article>)}
    <h3>Evidence und Fakten</h3>
    {evidence.length === 0 ? <p>Keine Evidence für diesen Snapshot.</p> : evidence.map((item) => <article key={item.id} className="panel">
      <h4>{item.capability}</h4><p>Evidence: {item.id}</p><p>Quelle: {item.provenance?.sourceRef || 'Nicht verfügbar'}</p>
      <p>Beobachtet: {item.observedAt} · Gültig bis: {item.expiresAt}</p><pre>{JSON.stringify(item.value, null, 2)}</pre>
    </article>)}
  </section>;
}
