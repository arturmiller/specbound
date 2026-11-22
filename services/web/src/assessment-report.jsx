import React, { useEffect, useState } from 'react';
import { AssessmentGovernance } from './assessment-governance.jsx';
import { ApprovalDetails, ApprovalForm, licenseUseLabel } from './license-approvals.jsx';
import { runDate } from './run-list.jsx';

/** @typedef {{id: string, evaluationId: string, outcome: string, state: string, reason: string}} Finding */
/** @typedef {{id: string, status: string, reason: string, licenseApprovalEligible?: boolean, evidenceIds: string[], control: {id: string}, subject: {id: string, labels?: {name?: string, version?: string, lockfile?: string}, provenance?: {sourceRef?: string}}, coverage: {status: string, revision: string | null, errors: {path: string, reason: string}[]} | null}} Evaluation */
/** @typedef {{id: string, capability: string, provenance?: {sourceRef?: string}, observedAt: string, expiresAt: string, value: unknown}} Evidence */
/** @typedef {{sourceScan?: import('./assessment-governance.jsx').SourceScan | null, pullRequestUrl?: string | null, licenseUse?: string | null, canApproveLicenses?: boolean, assessment: {governanceContext?: import('./assessment-governance.jsx').FrozenContext | null, controls?: import('./assessment-governance.jsx').ControlResult[] | null, id: string, organizationId: string, productId: string, context: string, createdAt?: string, gitSha: string, packSha: string, pullRequestNumber: number | null, environment: string, counts: {PASS: number, FAIL: number, UNKNOWN: number, NOT_APPLICABLE: number}}, evaluations: Evaluation[], evidence: Evidence[], findings: Finding[]}} Report */

const statusNames = /** @type {Record<string, string>} */ ({
  FAIL: 'Verstoß',
  UNKNOWN: 'Ungeklärt',
  PASS: 'Erfüllt',
  NOT_APPLICABLE: 'Nicht anwendbar',
});

/** @param {Evidence | undefined} evidence */
function licenseOf(evidence) {
  const value = evidence?.value;
  return value && typeof value === 'object' && 'licenseExpression' in value &&
    typeof value.licenseExpression === 'string' ? value.licenseExpression : '';
}
/** @param {Evidence | undefined} evidence */
function approvalOf(evidence) {
  const value = evidence?.value;
  return value && typeof value === 'object' && 'licenseApproval' in value
    ? /** @type {import('./license-approvals.jsx').LicenseApproval} */ (value.licenseApproval)
    : null;
}

/** @typedef {{artifactSha256: string, filename?: string, sourceUrl?: string, status?: string, licenseExpression?: string, reason?: string}} LicenseArtifact */

const licenseReasons = /** @type {Record<string, string>} */ ({
  'dynamic license declaration': 'Dynamische Lizenzangabe im Quellarchiv',
  'source metadata predates static license declarations': 'Metadaten des Quellarchivs belegen keine feste Lizenz für den Build',
  'artifact license metadata unavailable or invalid': 'Metadaten fehlen oder konnten nicht verifiziert werden',
  'locked artifact missing in index': 'Paketdatei fehlt im PyPI-Index',
  'source archive exceeds size limit': 'Quellarchiv überschreitet das Größenlimit',
  'ambiguous legacy license declaration': 'Mehrdeutige ältere Lizenzangabe',
  'ambiguous legacy license classifiers': 'Mehrdeutige Lizenzklassifikatoren',
  'no static license declaration': 'Keine eindeutige Lizenzangabe vorhanden',
  'artifact hashes missing': 'Artefakthashes im Lockfile fehlen',
  'unsupported package source': 'Paketquelle wird nicht unterstützt',
});

/** @param {{artifacts: LicenseArtifact[]}} props */
function LicenseArtifacts({ artifacts }) {
  const [open, setOpen] = useState(false);
  return <details className="assessment-disclosure" onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary>Lizenznachweise pro Paketdatei ({artifacts.length})</summary>
    {open && <ul>{artifacts.map((artifact) => {
      const label = artifact.filename || 'Paketdatei';
      const url = artifact.sourceUrl?.startsWith('https://files.pythonhosted.org/packages/') ? artifact.sourceUrl : '';
      return <li key={artifact.artifactSha256}>
        {url ? <a href={url}>{label}</a> : label}
        {' · '}{artifact.licenseExpression ? artifact.licenseExpression + ' belegt' : 'Ungeklärt'}
        {artifact.reason && ' · ' + (licenseReasons[artifact.reason] || artifact.reason)}
      </li>;
    })}</ul>}
  </details>;
}

/** @param {{evaluation: Evaluation, evidence: Evidence[], finding?: Finding, organizationId: string, sourceScan?: Report['sourceScan'], controlTitle?: string, productId: string, assessmentId: string, accessToken: string, licenseUse?: string | null, canApprove?: boolean}} props */
function EvaluationRow({ evaluation, evidence, finding, organizationId, sourceScan, controlTitle, productId, assessmentId, accessToken, licenseUse, canApprove }) {
  const { labels, provenance } = evaluation.subject;
  const name = labels?.name
    ? [labels.name, labels.version].filter(Boolean).join(' · ')
    : controlTitle || 'Kontrolle';
  const license = licenseOf(evidence[0]);
  const approval = approvalOf(evidence[0]);
  const licenseValue = /** @type {{artifacts?: LicenseArtifact[], licenseCoverage?: string, licenseReason?: string} | undefined} */ (evidence[0]?.value);
  const missingLicense = licenseValue?.licenseCoverage === 'incomplete';
  const licenseArtifacts = licenseValue?.licenseCoverage && Array.isArray(licenseValue.artifacts)
    ? licenseValue.artifacts : [];
  const lockfile = labels?.lockfile;
  const lockfileUrl = lockfile && sourceScan?.sourceRevision
    ? 'https://github.com/' + sourceScan.repository + '/blob/' + sourceScan.sourceRevision + '/' + lockfile.split('/').map(encodeURIComponent).join('/')
    : '';
  return <details className="assessment-item">
    <summary>
      <span><strong>{name}</strong>{lockfile && <small>{lockfile}</small>}</span>
      {license && <span className="assessment-license">{license}</span>}
      <span className={'assessment-status status-' + evaluation.status.toLowerCase()}>{approval ? 'Mit Freigabe' : statusNames[evaluation.status] || evaluation.status}</span>
    </summary>
    <div className="assessment-item-body">
      <p>{evaluation.reason}</p>
      {licenseValue?.licenseReason && <p>{licenseReasons[licenseValue.licenseReason] || licenseValue.licenseReason}</p>}
      {licenseArtifacts.length > 0 && <LicenseArtifacts artifacts={licenseArtifacts} />}
      {approval && <ApprovalDetails approval={approval} productId={productId} accessToken={accessToken} canManage={Boolean(canApprove)} />}
      {canApprove && licenseUse && evaluation.licenseApprovalEligible && <ApprovalForm productId={productId} assessmentId={assessmentId} evaluationId={evaluation.id} accessToken={accessToken} use={licenseUse} status={missingLicense ? 'UNKNOWN' : evaluation.status} />}
      <nav className="assessment-links" aria-label="Nachweise und Quelle">
        {finding && <a href={'/findings?' + new URLSearchParams({ organization: organizationId, finding: finding.id })}>Finding ansehen</a>}
        {lockfileUrl && <a href={lockfileUrl}>Lockfile öffnen</a>}
        {evidence.map((item, index) => <a key={item.id} href={'/evidence?' + new URLSearchParams({ organization: organizationId, evidence: item.id, view: 'detail' })}>{evidence.length > 1 ? 'Nachweis ' + (index + 1) + ' öffnen' : 'Nachweis öffnen'}</a>)}
      </nav>
      <details>
        <summary>Prüfregel und technische Herkunft</summary>
        {provenance?.sourceRef && <p>Quellverweis: {provenance.sourceRef}</p>}
        {evaluation.coverage && <p>Quellabdeckung: {evaluation.coverage.status}</p>}
        {evaluation.coverage?.errors.map((entry) => <p key={entry.path + entry.reason}>{entry.path} {entry.reason}</p>)}
        <pre>{JSON.stringify(evaluation.control, null, 2)}</pre>
      </details>
    </div>
  </details>;
}

/** @param {{id: string, accessToken?: string}} props */
export function AssessmentReport({ id, accessToken = '' }) {
  const [report, setReport] = useState(/** @type {Report | null} */ (null));
  const [error, setError] = useState('');
  const [showOpenItems, setShowOpenItems] = useState(false);
  const [showTechnical, setShowTechnical] = useState(false);
  const [recheckState, setRecheckState] = useState('');
  const [recheckError, setRecheckError] = useState('');
  async function recheck() {
    setRecheckState('sending');
    setRecheckError('');
    try {
      const response = await fetch(`/api/assessments/${encodeURIComponent(id)}/license-recheck`, {
        method: 'POST', headers: accessToken ? { Authorization: 'Bearer ' + accessToken } : undefined,
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.detail || 'Erneute Prüfung konnte nicht eingeplant werden.');
      }
      setRecheckState('queued');
    } catch (failure) {
      setRecheckState('');
      setRecheckError(failure instanceof Error ? failure.message : 'Erneute Prüfung konnte nicht eingeplant werden.');
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/assessments/' + encodeURIComponent(id), { signal: controller.signal, headers: accessToken ? { Authorization: 'Bearer ' + accessToken } : {} })
      .then((response) => {
        if (response.status === 403) throw new Error('Für dieses Assessment fehlen die erforderlichen Rechte.');
        if (response.status === 401) throw new Error('Für dieses Assessment ist eine Anmeldung erforderlich.');
        if (response.status === 404) throw new Error('Assessment nicht gefunden.');
        if (!response.ok) throw new Error('Assessment konnte nicht geladen werden.');
        return response.json();
      }).then(setReport).catch((failure) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [id, accessToken]);

  if (error) return <p role="alert" className="alert">{error}</p>;
  if (!report) return <p role="status">Assessment wird geladen …</p>;
  const { assessment, evaluations, evidence, findings, sourceScan, pullRequestUrl } = report;
  const { counts, controls, context, organizationId, productId, pullRequestNumber } = assessment;
  const isPR = context === 'pull_request';
  const incompleteControls = (controls || []).filter((control) => !['PASS', 'FAIL'].includes(control.status) && !control.evaluationIds.length);
  const violations = evaluations.filter((item) => item.status === 'FAIL');
  const unresolved = evaluations.filter((item) => item.status === 'UNKNOWN');
  const remaining = evaluations.filter((item) => !['FAIL', 'UNKNOWN'].includes(item.status));
  const noProfile = isPR && assessment.governanceContext?.mode === 'legacy-example';
  const incomplete = counts.UNKNOWN > 0 || !counts.PASS || incompleteControls.length > 0 ||
    Boolean(sourceScan && sourceScan.coverage !== 'covered') || noProfile ||
    Boolean(isPR && controls?.some((control) => control.status !== 'PASS'));
  const failed = counts.FAIL > 0 || controls?.some((control) => control.status === 'FAIL');
  const status = failed ? 'fail' : incomplete ? 'unknown' : 'pass';
  const title = failed ? 'Prüfung fehlgeschlagen' : incomplete ? 'Prüfung unvollständig' : 'Prüfung bestanden';
  const summary = [
    counts.FAIL ? counts.FAIL + (counts.FAIL === 1 ? ' Verstoß' : ' Verstöße') : '',
    counts.UNKNOWN ? counts.UNKNOWN + ' ungeklärt' : '',
    counts.PASS ? counts.PASS + ' erfüllt' : '',
    counts.NOT_APPLICABLE ? counts.NOT_APPLICABLE + ' nicht anwendbar' : '',
  ].filter(Boolean).join(' · ') || 'Für diesen Lauf liegen keine Einzelbewertungen vor.';
  const repositoryUrl = pullRequestUrl?.replace(/\/pull\/\d+$/, '') ||
    (sourceScan?.repository ? 'https://github.com/' + sourceScan.repository : '');
  const commitUrl = repositoryUrl && assessment.gitSha ? repositoryUrl + '/commit/' + assessment.gitSha : '';
  const productUrl = '/products?' + new URLSearchParams({ organization: organizationId, product: productId, view: 'scans' });
  const requirementsUrl = '/products?' + new URLSearchParams({ organization: organizationId, product: productId, view: 'requirements', assessment: id });
  const historyUrl = isPR ? '/pr-checks?' + new URLSearchParams({ organization: organizationId }) : productUrl;
  const evidenceById = new Map(evidence.map((item) => [item.id, item]));
  const approved = remaining.filter((item) => item.evidenceIds.some((key) => approvalOf(evidenceById.get(key))));
  const regular = remaining.filter((item) => !approved.includes(item));
  const findingByEvaluation = new Map(findings.map((item) => [item.evaluationId, item]));
  const controlTitles = new Map(controls?.map((item) => [item.controlId, item.title]));
  /** @param {Evaluation} item */
  const renderEvaluation = (item) => <EvaluationRow
    key={item.id} evaluation={item} organizationId={organizationId} sourceScan={sourceScan}
    productId={productId} assessmentId={id} accessToken={accessToken}
    licenseUse={report.licenseUse} canApprove={report.canApproveLicenses}
    finding={findingByEvaluation.get(item.id)} controlTitle={controlTitles.get(item.control.id)}
    evidence={item.evidenceIds.flatMap((value) => { const found = evidenceById.get(value); return found ? [found] : []; })}
  />;

  return <section className="assessment-report" aria-labelledby="assessment-heading">
    <p className="assessment-breadcrumb">
      <a href={historyUrl}>{isPR ? 'PR-Prüfungen' : 'Prüfungen'}</a>
      {pullRequestNumber != null && <> / {pullRequestUrl
        ? <a href={pullRequestUrl} aria-label={'Pull Request #' + pullRequestNumber + ' auf GitHub öffnen'}>PR #{pullRequestNumber}</a>
        : <span>PR #{pullRequestNumber}</span>}</>}
    </p>
    <header className={'assessment-outcome outcome-' + status}>
      <div className="assessment-outcome-result">
        <p className="assessment-stand">Ergebnis dieses Laufs{assessment.createdAt && ' · ' + runDate(assessment.createdAt)}</p>
        <h1 id="assessment-heading">{title}</h1>
        <p>{summary}</p>
        {report.licenseUse && <p className="assessment-stand">{licenseUseLabel(report.licenseUse)}</p>}
      </div>
      <div className="assessment-outcome-links">
        {commitUrl && <a href={commitUrl}>Commit {assessment.gitSha.slice(0, 8)}</a>}
        {repositoryUrl && <a href={repositoryUrl}>{sourceScan?.repository || new URL(repositoryUrl).pathname.slice(1)}</a>}
      </div>
    </header>
    {report.canApproveLicenses && isPR && pullRequestUrl && status !== 'pass' && <p>
      {recheckState === 'queued' ? <span role="status">Erneute Prüfung eingeplant. <a href={historyUrl}>PR-Prüfungen öffnen</a></span> : <button type="button" onClick={() => void recheck()} disabled={recheckState === 'sending'}>Diesen Commit erneut prüfen</button>}
      {recheckError && <span role="alert"> {recheckError}</span>}
    </p>}
    {sourceScan && sourceScan.coverage !== 'covered' && <p className="assessment-blocker">
      {sourceScan.reason === 'no supported lockfile' ? 'Dem geprüften Commit fehlt eine uv.lock.'
        : sourceScan.reason === 'timeout' ? 'Der Scan hat das Zeitlimit erreicht.' : 'Die Quellabdeckung ist unvollständig.'}
    </p>}
    {violations.length > 0 && <section className="panel" aria-labelledby="violations-heading">
      <h2 id="violations-heading">{sourceScan ? 'Abhängigkeiten mit Verstößen' : 'Fehlgeschlagene Kontrollen'}</h2>
      {violations.map(renderEvaluation)}
    </section>}
    {(unresolved.length > 0 || incompleteControls.length > 0) && <details className="panel assessment-disclosure"
      onToggle={(event) => setShowOpenItems(event.currentTarget.open)}>
      <summary>Ungeklärte Bewertungen ({unresolved.length + incompleteControls.length})</summary>
      {showOpenItems && <>
        {unresolved.map(renderEvaluation)}
        {incompleteControls.map((item) => <p key={item.controlId}>{item.title} · Keine Einzelbewertung verfügbar</p>)}
      </>}
    </details>}
    {approved.length > 0 && <details className="panel assessment-disclosure">
      <summary>Bewertungen mit Freigabe ({approved.length})</summary>
      {approved.map(renderEvaluation)}
    </details>}
    {noProfile && <p className="assessment-note">Dieser Lauf verwendet die Beispielrichtlinie. Ein Produktprofil ist erforderlich, damit der PR-Check bestehen kann.</p>}
    <details className="panel assessment-disclosure" onToggle={(event) => setShowTechnical(event.currentTarget.open)}>
      <summary>Technische Details</summary>
      {showTechnical && <>
        <div className="assessment-links">
          <a href={requirementsUrl}>Anforderungen für diesen Lauf öffnen</a>
          <a href={productUrl}>Produktprüfungen öffnen</a>
        </div>
        {!commitUrl && <p>Commit des Laufs: <code>{assessment.gitSha}</code></p>}
        <p>Umgebung: {assessment.environment}</p>
        <AssessmentGovernance context={assessment.governanceContext} controls={controls} sourceScan={sourceScan} />
        {regular.length > 0 && <details className="assessment-disclosure">
          <summary>Weitere Einzelbewertungen ({regular.length})</summary>
          {regular.map(renderEvaluation)}
        </details>}
      </>}
    </details>
  </section>;
}
