import React from 'react';
import { ManifestProvenance } from './manifest-source.jsx';

/** @typedef {{mode: string, product?: import('./resources.jsx').Resource, profile?: import('./resources.jsx').Resource, catalog?: import('./resources.jsx').Resource, policy?: {revision: string}, producer?: {kind: string, version: string | null}}} FrozenContext */
/** @typedef {{controlId: string, title: string, status: string, executionStatus: string, reason: string, evaluationIds: string[], evidenceIds: string[]}} ControlResult */
/** @typedef {{id: string, repository: string, ref: string, sourceRevision: string | null, coverage: string, files: string[], unsupportedFiles: string[], reason?: string}} SourceScan */

/** @param {{sourceScan: SourceScan}} props */
export function ScanSource({ sourceScan }) {
  const { repository, ref, sourceRevision, files, unsupportedFiles } = sourceScan;
  const baseUrl = `https://github.com/${repository}`;
  const reason = sourceScan.reason === 'no supported lockfile'
    ? 'Dem geprüften Commit fehlt eine uv.lock. Die Lizenzen der Abhängigkeiten konnten nicht bewertet werden.'
    : sourceScan.reason;
  return <>
    <p>Quellabdeckung: {sourceScan.coverage || 'Nicht gespeichert'}</p>
    <p>{reason}</p>
    <p className="break-value">Prüfquelle: {sourceRevision ? <a href={`${baseUrl}/commit/${sourceRevision}`}>{repository} · {sourceRevision.slice(0, 12)}</a> : <>{repository} · Revision nicht beobachtet</>} · Ref: {ref}</p>
    {sourceRevision && files.length > 0 && <ul>{files.map((path) => <li key={path}><a href={`${baseUrl}/blob/${sourceRevision}/${path.split('/').map(encodeURIComponent).join('/')}`}>{path}</a></li>)}</ul>}
    {unsupportedFiles.length > 0 && <p className="break-value">Nicht unterstützte Dateien: {unsupportedFiles.join(', ')}</p>}
  </>;
}
/** @param {{context?: FrozenContext | null, controls?: ControlResult[] | null, sourceScan?: SourceScan | null}} props */
export function AssessmentGovernance({ context, controls, sourceScan }) {
  const labels = /** @type {Record<string, string>} */ ({ evaluated: 'Bewertet', unsupported: 'Nicht unterstützt', not_evaluated: 'Nicht bewertet' });
  const reasons = /** @type {Record<string, string>} */ ({ 'evaluation-limit': 'Bewertungsgrenze erreicht; dieses Control wurde in diesem Lauf nicht ausgeführt', 'method-not-configured': 'Keine Prüfmethode definiert', 'scanner-does-not-support-binding': 'Dieser Scanner liefert den benötigten Ziel- oder Nachweistyp nicht', 'no-evaluable-observations': 'Keine bewertbaren Beobachtungen vorhanden', 'individual-evaluations': 'Ergebnis aus gespeicherten Einzelbewertungen' });
  return <section className="panel" aria-label="Fixierter Geltungsbereich"><h2>Fixierter Geltungsbereich</h2>
    {!context ? <p>Für diesen historischen Stand wurde kein Produkt-/Profilabschluss gespeichert. Fehlende Angaben bleiben unbekannt.</p> : context.mode === 'profile' && context.product && context.profile ? <>
      <p>Produkt: {context.product.name} · {context.product.version}</p><p>Profil: <strong>{context.profile.name} · {context.profile.version}</strong></p>
      <ManifestProvenance source={context.product.source} defaultPath={context.product.source.manifestPath} />
      <ManifestProvenance source={context.profile.source} defaultPath={context.profile.source.manifestPath} />
      <p>Katalogdefinition: {context.catalog?.name} · {context.catalog?.version}</p>
      <ul>{context.profile.source.files.filter((file) => file.path !== context.profile?.source.manifestPath).map((file) => <li key={file.path}><a href={file.url}>{file.path}</a></li>)}</ul>
    </> : <p>Expliziter Legacy-Beispielstand · <a href={`https://github.com/arturmiller/specbound/commit/${context.policy?.revision}`}>Richtlinienrevision</a>. Eine Produktprofilzuordnung ist damit nicht belegt.</p>}
    {context?.producer && <p>Erzeuger: {context.producer.kind} · Version: {context.producer.version || 'nicht gespeichert / unbekannt'}</p>}
    {sourceScan && <ScanSource sourceScan={sourceScan} />}
    {controls && <><p>{controls.length} ausgewählte Controls. Die Anzahl der Einzelbewertungen kann davon abweichen.</p><div className="team-table-scroll"><table className="team-table"><thead><tr><th>CONTROL</th><th>PRÜFUNG</th><th>ERGEBNIS</th><th>GRUND</th></tr></thead><tbody>{controls.map((control) => <tr key={control.controlId}><td>{control.controlId}<small>{control.title}</small></td><td>{labels[control.executionStatus] || control.executionStatus}</td><td>{control.status}</td><td>{reasons[control.reason] || control.reason}<small>{control.evaluationIds.length} Einzelbewertungen · {control.evidenceIds.length} Nachweise</small></td></tr>)}</tbody></table></div></>}
  </section>;
}
