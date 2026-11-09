import React, { useEffect, useState } from 'react';
import { evidenceFreshness } from './evidence-freshness.js';
import { FindingJourney } from './finding-journey.jsx';

/** @typedef {{id: string, productId: string, subjectId: string, controlId: string, environment: string, status: string, snapshotId: string}} Finding */
/** @typedef {{id: string, name: string, teamId?: string}} Product */
/** @typedef {{id: string, observedAt: string, expiresAt: string, capability: string, provenance?: {sourceRef?: string}}} Evidence */
/** @typedef {{id: string, status: string, reason: string, evidenceIds: string[], control: {id: string, requiredEvidence?: {capability?: string}}, subject: {id: string, labels?: {name?: string}, provenance?: {sourceRef?: string, sourceRevision?: string}}, coverage: {status: string, revision: string | null} | null}} Evaluation */
/** @typedef {{assessment: {id: string, organizationId: string, productId: string, context: string, environment: string, gitSha: string, packSha: string, pullRequestNumber: number | null}, evaluations: Evaluation[], evidence: Evidence[], findings: {id: string, evaluationId: string, outcome: string, state: string, reason: string}[]}} Report */
/** @typedef {{finding: Finding, productName: string, teamId: string, report: Report, evaluation: Evaluation}} Trace */

/** @param {{organizationId: string, findingId: string, teams: {id: string, name: string}[], accessToken?: string}} props */
export function FindingDetail({ organizationId, findingId, teams, accessToken = '' }) {
  const [trace, setTrace] = useState(/** @type {Trace | null} */ (null));
  const [error, setError] = useState('');
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  useEffect(() => {
    const controller = new AbortController();
    /** @type {Record<string, string>} */ const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
    async function load() {
      const response = await fetch(`/api/organizations/${encodeURIComponent(organizationId)}/overview`, { signal: controller.signal, headers });
      if (!response.ok) throw new Error(response.status === 403 ? 'Für dieses Finding fehlen die erforderlichen Rechte.' : 'Finding konnte nicht geladen werden.');
      const overview = await response.json();
      /** @type {Finding | undefined} */ const finding = overview.findings.find((/** @type {Finding} */ item) => item.id === findingId);
      if (!finding) throw new Error('Finding nicht gefunden oder nicht sichtbar.');
      const assessmentResponse = await fetch(`/api/assessments/${encodeURIComponent(finding.snapshotId)}`, { signal: controller.signal, headers });
      if (!assessmentResponse.ok) throw new Error(assessmentResponse.status === 403 ? 'Für dieses Assessment fehlen die erforderlichen Rechte.' : 'Das verknüpfte Assessment konnte nicht geladen werden.');
      /** @type {Report} */ const report = await assessmentResponse.json();
      const event = report.findings.find((item) => item.id === finding.id);
      const evaluation = report.evaluations.find((item) => item.id === event?.evaluationId);
      if (report.assessment.organizationId !== organizationId || report.assessment.productId !== finding.productId || !event || !evaluation || evaluation.control.id !== finding.controlId || evaluation.subject.id !== finding.subjectId) throw new Error('Die gespeicherte Finding-Zuordnung ist unvollständig.');
      /** @type {Product | undefined} */ const product = overview.products.find((/** @type {Product} */ item) => item.id === finding.productId);
      setTrace({ finding, productName: product?.name || finding.productId, teamId: product?.teamId || '', report, evaluation });
    }
    load().catch((failure) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [organizationId, findingId, accessToken]);

  if (error) return <section><p role="alert" className="alert">{error}</p><a href={`/overview?${new URLSearchParams({ organization: organizationId })}`}>Zur Übersicht</a></section>;
  if (!trace) return <p role="status">Finding und Assessment werden geladen …</p>;
  const view = new URLSearchParams(window.location.search).get('view');
  if (view === 'remediation' || view === 'resolution') return <FindingJourney organizationId={organizationId} trace={trace} teams={teams} view={view} accessToken={accessToken} />;
  const { finding, productName, report, evaluation } = trace;
  const { assessment } = report;
  const evidence = report.evidence.filter((item) => evaluation.evidenceIds.includes(item.id));
  const outcome = evaluation.status === 'NOT_APPLICABLE' ? 'N/A' : evaluation.status;
  const missingEvidence = evidence.length !== evaluation.evidenceIds.length;
  /** @param {string} id */
  const evidenceUrl = (id) => `/evidence?${new URLSearchParams({ organization: organizationId, evidence: id, view: 'detail', assessment: assessment.id, finding: finding.id })}`;
  return <section className="finding-screen" aria-labelledby="finding-heading">
    <p className="eyebrow">FINDINGS / ASSESSMENT</p><div className="page-heading"><div><h1 id="finding-heading">⚑ {finding.controlId}</h1><p>Finding {finding.id} · Status {finding.status} · {finding.environment}</p></div><span className={`assessment-status status-${evaluation.status.toLowerCase()}`}>{outcome}</span></div>
    <div className="finding-metrics"><div className="panel"><span>Schweregrad</span><strong>UNKNOWN</strong></div><div className="panel"><span>Produkt</span><strong>{productName}</strong></div><div className="panel"><span>Subject</span><strong>{evaluation.subject.labels?.name || finding.subjectId}</strong></div><div className="panel"><span>Control</span><strong>{finding.controlId}</strong></div><div className="panel"><span>Packrevision</span><strong>{assessment.packSha}</strong></div></div>
    <div className="finding-columns"><div className="finding-main"><div className="panel"><h2>Nachvollziehbarkeit und Assessment</h2><div className="finding-trace"><div><small>Control</small><strong>{evaluation.control.id}</strong></div><div><small>Capability</small><strong>{evaluation.control.requiredEvidence?.capability || 'UNKNOWN'}</strong></div><div><small>Evidence</small><strong>{evaluation.evidenceIds.length}</strong></div><div><small>Ergebnis im Snapshot</small><strong>{outcome}</strong></div></div><h3>Ergebnisgrund</h3><p>{evaluation.reason}</p><p>Finding-Status und historisches Bewertungsergebnis sind getrennt. UNKNOWN oder N/A schließt ein offenes Finding nicht automatisch.</p><p className="break-value">Subject-Quelle: {evaluation.subject.provenance?.sourceRef || 'UNKNOWN'}</p><p className="break-value">Subject-Revision: {evaluation.subject.provenance?.sourceRevision || 'UNKNOWN'}</p></div>
      <div className="panel"><h2>Verknüpfte Evidence</h2>{missingEvidence && <p role="alert" className="alert">Eine verknüpfte Evidence ist im Snapshot nicht lesbar.</p>}{evidence.length ? <ul className="finding-evidence">{evidence.map((item) => <li key={item.id}><a href={evidenceUrl(item.id)}>{item.id}</a><span>{item.capability} · {evidenceFreshness(item, now)}</span></li>)}</ul> : <p>Keine Evidence mit dieser Bewertung verknüpft.</p>}<p>Die angezeigte Frische bezieht sich auf jetzt; das Assessment bleibt ein historischer Snapshot.</p></div></div>
      <div className="panel finding-side"><h2>Assessment-Herkunft</h2><dl className="team-role-list evidence-details"><div><dt>Assessment</dt><dd>{assessment.id}</dd></div><div><dt>Produkt-Commit</dt><dd>{assessment.gitSha}</dd></div><div><dt>Packrevision</dt><dd>{assessment.packSha}</dd></div><div><dt>Kontext</dt><dd>{assessment.context}</dd></div><div><dt>Umgebung</dt><dd>{assessment.environment}</dd></div>{assessment.pullRequestNumber !== null && <div><dt>Pull Request</dt><dd>#{assessment.pullRequestNumber}</dd></div>}</dl><a href={`/assessments/${encodeURIComponent(assessment.id)}`}>Assessment-Bericht öffnen →</a></div></div>
    <a className="primary-link" href={`/findings?${new URLSearchParams({ organization: organizationId, finding: finding.id, view: 'remediation' })}`}>Lösungsweg ansehen →</a>{' '}
    <a className="team-back" href={`/findings?${new URLSearchParams({ organization: organizationId })}`}>← Zur Finding-Inbox</a>{' '}
    <a className="team-back" href={`/overview?${new URLSearchParams({ organization: organizationId })}`}>← Zur Übersicht</a>
  </section>;
}
