import React, { useState } from 'react';

const uses = /** @type {Record<string, string>} */ ({
  internal: 'Interner Betrieb',
  saas: 'Serverseitiger SaaS-Betrieb',
  'customer-distribution': 'Auslieferung an Kunden',
});

/** @param {string} use */
export function licenseUseLabel(use) { return uses[use] || use; }

/** @typedef {{id: string, use: string, kind: string, reason: string, conditions: string, expiresAt?: string | null}} LicenseApproval */

/** @param {{productId: string, accessToken: string, approval: LicenseApproval, canManage: boolean}} props */
export function ApprovalDetails({ productId, accessToken, approval, canManage }) {
  const [proof, setProof] = useState('');
  const [revoked, setRevoked] = useState(false);
  const [error, setError] = useState('');
  const url = `/api/products/${encodeURIComponent(productId)}/license-approvals/${encodeURIComponent(approval.id)}`;
  const headers = accessToken ? { Authorization: 'Bearer ' + accessToken } : undefined;
  /** @param {boolean} revoke */
  async function openProof(revoke) {
    try {
      setError('');
      const response = await fetch(revoke ? url + '/revoke' : url, { method: revoke ? 'POST' : 'GET', headers });
      if (!response.ok) throw new Error('Freigabe konnte nicht geladen oder geändert werden.');
      const result = await response.json();
      if (!revoke) setProof(result.proofUrl);
      setRevoked(Boolean(revoke || result.revokedAt));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Freigabe ist nicht verfügbar.');
    }
  }
  return <div className="license-approval">
    <p><strong>{approval.kind === 'license-rights' ? 'Vertragliche Nutzungsrechte' : 'Nachgewiesene Lizenzauflagen'}</strong> · {licenseUseLabel(approval.use)}</p>
    <p>{approval.reason}</p>
    <p>Auflagen · {approval.conditions}</p>
    {approval.expiresAt && <p>Gültig bis {new Date(approval.expiresAt).toLocaleString('de-DE')}</p>}
    {canManage && <div className="assessment-links">
      {proof ? <a href={proof} target="_blank" rel="noreferrer">Geschützten Beleg öffnen</a> : <button type="button" onClick={() => void openProof(false)}>Nachweislink laden</button>}
      {revoked ? <p role="status">Freigabe widerrufen</p> : <button type="button" onClick={() => void openProof(true)}>Freigabe widerrufen</button>}
    </div>}
    {error && <p role="alert">{error}</p>}
  </div>;
}

/** @param {{productId: string, assessmentId: string, evaluationId: string, use: string, status: string, accessToken: string}} props */
export function ApprovalForm({ productId, assessmentId, evaluationId, use, status, accessToken }) {
  const [state, setState] = useState('ready');
  const [approval, setApproval] = useState(/** @type {LicenseApproval | null} */ (null));
  const [error, setError] = useState('');
  /** @param {React.FormEvent<HTMLFormElement>} event */
  async function submit(event) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    setState('sending'); setError('');
    try {
      const expiry = fields.get('expiry');
      const response = await fetch(`/api/products/${encodeURIComponent(productId)}/license-approvals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: 'Bearer ' + accessToken } : {}) },
        body: JSON.stringify({
          assessmentId, evaluationId, kind: fields.get('kind'), reason: fields.get('reason'),
          conditions: fields.get('conditions'), proofUrl: fields.get('proof'),
          expiresAt: expiry ? new Date(String(expiry)).toISOString() : null,
        }),
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(typeof result.detail === 'string' ? result.detail : 'Freigabe konnte nicht gespeichert werden.');
      }
      setApproval(await response.json());
      setState('saved');
    } catch (failure) {
      setState('ready');
      setError(failure instanceof Error ? failure.message : 'Freigabe konnte nicht gespeichert werden.');
    }
  }
  return <details className="license-approval">
    <summary>Nutzung freigeben</summary>
    {approval ? <>
      <p role="status">Freigabe gespeichert. Starte eine erneute Prüfung, um sie anzuwenden.</p>
      <ApprovalDetails approval={approval} productId={productId} accessToken={accessToken} canManage />
    </> : <form onSubmit={submit}>
      <p>Gilt für diese Paketversion und {licenseUseLabel(use).toLowerCase()}.</p>
      <label className="field">Grundlage<select name="kind">
        {status === 'FAIL' && <option value="conditions-met">Lizenzauflagen sind belegt</option>}
        <option value="license-rights">Ein Vertrag gewährt die Nutzungsrechte</option>
      </select></label>
      <label className="field">Begründung<input required name="reason" maxLength={1500} /></label>
      <label className="field">Erfüllte Auflagen oder Vertragsumfang<input required name="conditions" maxLength={1500} /></label>
      <label className="field">Geschützter HTTPS-Nachweislink<input required name="proof" type="url" placeholder="https://" maxLength={2048} /></label>
      <label className="field">Ablaufdatum und Uhrzeit<input name="expiry" type="datetime-local" /></label>
      <button type="submit" disabled={state === 'sending'}>Freigabe speichern</button>
    </form>}
    {error && <p role="alert">{error}</p>}
  </details>;
}
