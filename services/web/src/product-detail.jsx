import React, { useEffect, useState } from 'react';

/** @typedef {{id: string, name: string, ownerTeamId: string}} Product */
/** @typedef {{id: number, bindingId: string, repository: string, provider: string, scanner: string, ref: string, status: string, sourceRevision: string | null, observedAt: string, files: string[], errors: {path: string, reason: string}[]}} Scan */
/** @typedef {{id: string, productId: string}} AssessmentRef */
/** @typedef {{id: string, status: string, reason: string, control: {id: string}, subject: {id: string, type: string, labels?: {name?: string}, provenance?: {sourceRef?: string, sourceRevision?: string}}, coverage: {status: string, revision: string | null} | null}} Evaluation */
/** @typedef {{assessment: {id: string, environment: string, context: string, gitSha: string, packSha: string, createdAt: string, counts: Record<string, number>}, evaluations: Evaluation[], evidence: unknown[]}} Report */

/** @param {string} path @param {string} token @param {AbortSignal} signal */
async function read(path, token, signal) {
  const response = await fetch(`/api${path}`, { signal, headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (response.status === 403) throw new Error('Für diese Daten fehlen die erforderlichen Rechte.');
  if (response.status === 401) throw new Error('Für diese Daten ist eine Anmeldung erforderlich.');
  if (!response.ok) throw new Error('Die Daten konnten nicht geladen werden.');
  return response.json();
}

/** @param {string} org @param {string} product @param {string} [view] */
function url(org, product, view = '') {
  const params = new URLSearchParams({ organization: org, product });
  if (view) params.set('view', view);
  return `/products?${params}`;
}

/** @param {{product: Product, organizationId: string, teamName: string, accessToken: string, view: string}} props */
export function ProductDetail({ product, organizationId, teamName, accessToken, view }) {
  const [scans, setScans] = useState(/** @type {Scan[] | null} */ (null));
  const [scanError, setScanError] = useState('');
  const [assessments, setAssessments] = useState(/** @type {AssessmentRef[] | null} */ (null));
  const [assessmentError, setAssessmentError] = useState('');
  const [report, setReport] = useState(/** @type {Report | null} */ (null));
  const [reportError, setReportError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    read(`/products/${encodeURIComponent(product.id)}/discovery`, accessToken, controller.signal)
      .then(setScans).catch((failure) => { if (!controller.signal.aborted) setScanError(failure.message); });
    read(`/organizations/${encodeURIComponent(organizationId)}/overview`, accessToken, controller.signal)
      .then((data) => {
        /** @type {AssessmentRef[]} */ const matches = data.assessments.filter((/** @type {AssessmentRef} */ item) => item.productId === product.id);
        setAssessments(matches);
        if (matches.length) read(`/assessments/${encodeURIComponent(matches[0].id)}`, accessToken, controller.signal)
          .then(setReport).catch((failure) => { if (!controller.signal.aborted) setReportError(failure.message); });
      }).catch((failure) => { if (!controller.signal.aborted) setAssessmentError(failure.message); });
    return () => controller.abort();
  }, [product.id, organizationId, accessToken]);

  const detailUrl = url(organizationId, product.id);
  const discoveryUrl = url(organizationId, product.id, 'discovery');
  const sourcesUrl = url(organizationId, product.id, 'repository');
  const listUrl = `/products?${new URLSearchParams({ organization: organizationId })}`;
  const subjects = report ? Array.from(new Map(report.evaluations.map((evaluation) => [evaluation.subject.id, evaluation.subject])).values()) : [];
  return view === 'discovery' ? <>
    <p className="eyebrow">PRODUKTE / DISCOVERY</p><div className="page-heading"><div><h1 id="products-heading">Discovery prüfen</h1><p>Gespeicherte Scanabdeckung und Datenlücken für {product.name}.</p></div></div>
    <ol className="team-steps" aria-label="Schritte der Produktregistrierung"><li><span>1</span>Produktidentität</li><li><span>2</span>Quellen verbinden</li><li aria-current="step"><span>3</span>Discovery prüfen</li></ol>
    <div className="discovery-columns"><div className="panel"><h2>Beobachtete Scanabdeckung</h2><p>Historische Beobachtungen; eine Datei ist nicht automatisch eine erkannte Komponente.</p>
      {scanError ? <p role="alert" className="alert">{scanError}</p> : scans === null ? <p role="status">Scans werden geladen …</p> : scans.length === 0 ? <p>Keine Scanbeobachtungen vorhanden. Discovery-Zustand: UNKNOWN.</p> : <div className="discovery-scans">{scans.map((scan) => <article key={scan.id} className="discovery-scan"><div className="discovery-scan-heading"><strong className="break-value">{scan.repository}</strong><span className="team-role">{scan.status}</span></div><p>{scan.scanner} · Ref: {scan.ref} · Beobachtet: {scan.observedAt}</p><p className="break-value">Revision: {scan.sourceRevision || 'UNKNOWN'}</p><p>Dateien: {scan.files.length ? scan.files.join(', ') : 'Keine beobachtet'}</p>{scan.errors.map((item, index) => <p key={index}>Scanfehler: {item.path || 'Quelle'} — {item.reason}</p>)}</article>)}</div>}
      <p>Erkannte Subjects werden nur gezeigt, wenn sie in einer gespeicherten Bewertung mit Herkunft vorliegen.</p>
    </div><div className="discovery-side"><div className="panel"><h2>Fehlender Produktkontext</h2><dl className="team-role-list"><div><dt>Produkttyp</dt><dd>UNKNOWN</dd></div><div><dt>Umgebung des Produkts</dt><dd>UNKNOWN</dd></div><div><dt>Cloud-Zuordnung</dt><dd>UNKNOWN</dd></div></dl><div className="team-info">UNKNOWN ist weder PASS noch automatisch nicht anwendbar.</div></div>
      <div className="panel"><h2>Gespeicherte Bewertungen</h2><AssessmentSummary assessments={assessments} assessmentError={assessmentError} report={report} reportError={reportError} /></div></div></div>
    <div className="team-actions"><a className="team-back" href={sourcesUrl}>← Quellen</a><a className="primary-link" href={detailUrl}>Produkt ansehen →</a></div>
  </> : <>
    <p className="eyebrow">PRODUKTE / PRODUKTDETAILS</p><div className="page-heading"><div><h1 id="products-heading">◇ {product.name}</h1><p>Verantwortung, Beobachtungen und gespeicherte Bewertungen.</p></div><a className="primary-link" href={sourcesUrl}>Quellen verwalten →</a></div>
    <div className="team-metrics team-detail-metrics"><div className="panel"><span>Produkttyp</span><strong>UNKNOWN</strong></div><div className="panel"><span>Umgebung des Produkts</span><strong>UNKNOWN</strong></div><div className="panel"><span>Verantwortliches Team</span><strong>{teamName}</strong></div><div className="panel"><span>Scanbeobachtungen</span><strong>{scanError ? 'Nicht verfügbar' : scans === null ? '…' : scans.length}</strong></div></div>
    <nav className="product-detail-nav" aria-label="Produktansichten"><a aria-current="page" href={detailUrl}>Produktdetails</a><a href={discoveryUrl}>Discovery</a><a href={sourcesUrl}>Git-Quellen</a></nav>
    <div className="discovery-columns"><div className="panel"><h2>Produktdetails</h2><h3>Belegte Subjects und Herkunft</h3>
      {assessmentError || reportError ? <p role="alert" className="alert">{assessmentError || reportError}</p> : assessments === null || (assessments.length > 0 && !report) ? <p role="status">Bewertungen werden geladen …</p> : subjects.length === 0 ? <div className="unknown-architecture"><strong>◇ {product.name}</strong><p>Keine bewerteten Subjects verfügbar. Komponenten und Beziehungen: UNKNOWN.</p></div> : <div className="discovery-scans">{subjects.map((subject) => <article key={subject.id} className="discovery-scan"><strong>{subject.labels?.name || subject.id}</strong><p>{subject.type}</p><p className="break-value">Quelle: {subject.provenance?.sourceRef || 'UNKNOWN'}</p><p className="break-value">Revision: {subject.provenance?.sourceRevision || 'UNKNOWN'}</p></article>)}</div>}
      <p>Subjects stammen aus dem zuletzt gespeicherten Assessment. Weitere Komponenten und Beziehungen werden nicht angenommen.</p><a href={discoveryUrl}>Scanabdeckung ansehen →</a>
    </div><div className="discovery-side"><div className="panel"><h2>Kontrollen im letzten Assessment</h2><AssessmentSummary assessments={assessments} assessmentError={assessmentError} report={report} reportError={reportError} /></div>
      <div className="panel"><h2>Evidence im letzten Assessment</h2>{report ? <p>{report.evidence.length} gespeicherte Evidence-Einträge für diesen Snapshot.</p> : <p>{assessmentError || reportError ? 'Nicht verfügbar.' : assessments === null || assessments.length ? 'Wird geladen …' : 'Kein Assessment vorhanden.'}</p>}</div></div></div>
    <a className="team-back" href={listUrl}>← Zurück zu Produkten</a>
  </>;
}

/** @param {{assessments: AssessmentRef[] | null, assessmentError: string, report: Report | null, reportError: string}} props */
function AssessmentSummary({ assessments, assessmentError, report, reportError }) {
  if (assessmentError || reportError) return <p role="alert" className="alert">{assessmentError || reportError}</p>;
  if (assessments === null || (assessments.length > 0 && !report)) return <p role="status">Bewertungen werden geladen …</p>;
  if (!report) return <p>Kein Assessment vorhanden. Bewertung: UNKNOWN.</p>;
  return <><p>Zuletzt gespeichert: {report.assessment.createdAt} · {report.assessment.environment} · {report.assessment.context}</p>
    <p className="break-value">Git: {report.assessment.gitSha} · Pack: {report.assessment.packSha}</p>
    {report.evaluations.length ? <ul className="product-evaluations">{report.evaluations.map((item) => <li key={item.id}><div><strong>{item.control.id}</strong><small>{item.reason} · Quellabdeckung: {item.coverage?.status || 'UNKNOWN'}</small></div><span className={`assessment-status status-${item.status.toLowerCase()}`}>{item.status}</span></li>)}</ul> : <p>Keine Bewertungen in diesem Snapshot.</p>}
    <p>PASS {report.assessment.counts.PASS ?? 'UNKNOWN'} · FAIL {report.assessment.counts.FAIL ?? 'UNKNOWN'} · UNKNOWN {report.assessment.counts.UNKNOWN ?? 'UNKNOWN'} · N/A {report.assessment.counts.NOT_APPLICABLE ?? 'UNKNOWN'}</p>
    <a href={`/assessments/${encodeURIComponent(report.assessment.id)}`}>Assessment mit Provenienz öffnen →</a></>;
}
