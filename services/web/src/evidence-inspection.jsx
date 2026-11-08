import React, { useEffect, useState } from 'react';
import { evidenceFreshness } from './evidence-freshness.js';

/** @typedef {{id: string, productId: string, subjectId: string, capability: string, environment: string, targetRevision: string, collectorRevision: string, collectorImage: string, provenance: {sourceRef?: string}, value: unknown, observedAt: string, expiresAt: string, ttlSeconds: number}} Evidence */
/** @typedef {{assessment: {id: string, organizationId: string, productId: string, gitSha: string, packSha: string}, evaluations: {id: string, status: string, reason: string, evidenceIds: string[], control: {id: string}}[], evidence: {id: string}[], findings: {id: string, evaluationId: string}[]}} Report */
/** @typedef {{report: Report, evaluation: Report['evaluations'][number]}} Context */

/** @param {{item: Evidence, organizationId: string, productName: string, accessToken: string, assessmentId: string, findingId: string, now: number}} props */
export function EvidenceInspection({ item, organizationId, productName, accessToken, assessmentId, findingId, now }) {
  const [context, setContext] = useState(/** @type {Context | null} */ (null));
  const [contextError, setContextError] = useState('');
  const [contextLoading, setContextLoading] = useState(Boolean(assessmentId && findingId));
  useEffect(() => {
    if (!assessmentId || !findingId) return;
    const controller = new AbortController();
    fetch(`/api/assessments/${encodeURIComponent(assessmentId)}`, { signal: controller.signal, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} })
      .then((response) => { if (!response.ok) throw new Error('Der Assessment-Kontext ist nicht verfügbar.'); return response.json(); })
      .then((/** @type {Report} */ report) => {
        const event = report.findings.find((finding) => finding.id === findingId);
        const evaluation = report.evaluations.find((entry) => entry.id === event?.evaluationId);
        if (report.assessment.organizationId !== organizationId || report.assessment.productId !== item.productId || !event || !evaluation || !evaluation.evidenceIds.includes(item.id) || !report.evidence.some((evidence) => evidence.id === item.id)) throw new Error('Diese Evidence ist dem angegebenen Finding nicht nachweisbar zugeordnet.');
        setContext({ report, evaluation });
      }).catch((failure) => { if (!controller.signal.aborted) setContextError(failure.message); })
      .finally(() => { if (!controller.signal.aborted) setContextLoading(false); });
    return () => controller.abort();
  }, [assessmentId, findingId, organizationId, item.id, item.productId, accessToken]);
  const back = `/evidence?${new URLSearchParams({ organization: organizationId })}`;
  const findingUrl = `/findings?${new URLSearchParams({ organization: organizationId, finding: findingId })}`;
  return <>
    <p className="eyebrow">EVIDENCE / INSPEKTION</p><div className="page-heading"><div><h1 id="evidence-heading">Evidence-Details</h1><p>Gespeicherte Observation mit Scope und Herkunft.</p></div>{context && <a className="primary-link" href={findingUrl}>Zum Finding →</a>}</div>
    <div className="team-metrics team-detail-metrics"><div className="panel"><span>Datensatz</span><strong>Gespeichert</strong></div><div className="panel"><span>Capability</span><strong>{item.capability}</strong></div><div className="panel"><span>Frische</span><strong>{evidenceFreshness(item, now)}</strong></div><div className="panel"><span>Vertrauen</span><strong>UNKNOWN</strong></div></div>
    <div className="team-columns"><div className="panel"><h2>Beobachtete Evidence</h2><dl className="team-role-list evidence-details"><div><dt>Evidence-ID</dt><dd>{item.id}</dd></div><div><dt>Produkt / Subject</dt><dd>{productName} / {item.subjectId}</dd></div><div><dt>Umgebung</dt><dd>{item.environment}</dd></div><div><dt>Quelle</dt><dd>{item.provenance?.sourceRef || 'UNKNOWN'}</dd></div><div><dt>Beobachtet</dt><dd>{item.observedAt}</dd></div><div><dt>Gültig bis</dt><dd>{item.expiresAt}</dd></div><div><dt>Produktrevision</dt><dd>{item.targetRevision}</dd></div><div><dt>Provider-/Packrevision</dt><dd>{item.collectorRevision}</dd></div><div><dt>Collector-Image</dt><dd>{item.collectorImage}</dd></div></dl><h2>Observation</h2><pre className="provider-code">{JSON.stringify(item.value, null, 2)}</pre></div>
      <div className="panel"><h2>Nachvollziehbarkeit</h2>{contextLoading ? <p role="status">Assessment-Kontext wird geladen …</p> : contextError ? <p role="alert" className="alert">{contextError}</p> : context ? <><dl className="team-role-list evidence-details"><div><dt>Control</dt><dd>{context.evaluation.control.id}</dd></div><div><dt>Capability</dt><dd>{item.capability}</dd></div><div><dt>Assessment-Ergebnis</dt><dd>{context.evaluation.status === 'NOT_APPLICABLE' ? 'N/A' : context.evaluation.status}</dd></div><div><dt>Produkt-Commit</dt><dd>{context.report.assessment.gitSha}</dd></div><div><dt>Governance-Packrevision</dt><dd>{context.report.assessment.packSha}</dd></div></dl><p>{context.evaluation.reason}</p><a href={`/assessments/${encodeURIComponent(context.report.assessment.id)}`}>Assessment-Bericht öffnen →</a></> : <p>Keine nachgewiesene Finding-Zuordnung übergeben.</p>}<div className="team-info">Frische bezieht sich auf jetzt; das gespeicherte Assessment ist historisch. Eine Provider-ID und ein Vertrauensstatus sind hier nicht gespeichert.</div></div></div>
    <a className="team-back" href={context ? findingUrl : back}>← {context ? 'Zum Finding' : 'Zum Evidence-Register'}</a>
  </>;
}
