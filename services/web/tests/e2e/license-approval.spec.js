import { expect, test } from '@playwright/test';

test('a license approval retains the finding context and keeps the proof behind an explicit request', async ({ page }) => {
  const proof = 'https://proof.example.test/protected/lgpl-review';
  const decision = {
    id: 'approval', use: 'customer-distribution', kind: 'conditions-met',
    reason: 'Bibliothek kann ausgetauscht werden.', conditions: 'Lizenzhinweise ausliefern.',
  };
  const report = (approved) => ({
    licenseUse: 'customer-distribution',
    canApproveLicenses: true, pullRequestUrl: 'https://github.com/example/product/pull/17',
    assessment: {
      id: approved ? 'approved' : 'blocked', organizationId: 'org', productId: 'product',
      context: 'pull_request', gitSha: 'a'.repeat(40), environment: 'customer-distribution',
      pullRequestNumber: 17, counts: { PASS: Number(approved), FAIL: Number(!approved), UNKNOWN: 0, NOT_APPLICABLE: 0 },
    },
    findings: [],
    evaluations: [{
      id: 'evaluation', status: approved ? 'PASS' : 'FAIL', evidenceIds: ['evidence'],
      licenseApprovalEligible: !approved, reason: approved ? 'Nutzung mit belegter Freigabe' : 'Lizenzauflagen sind zu prüfen',
      subject: { id: 'package', labels: { name: 'psycopg-binary', version: '3.3.3', lockfile: 'uv.lock' } },
      control: { id: 'PY-LIC-001' },
    }],
    evidence: [{
      id: 'evidence',
      value: { licenseExpression: 'LGPL-3.0-only', ...(approved ? { licenseApproval: decision } : {}) },
    }],
  });
  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/config')) return route.fulfill({ json: { enabled: false } });
    if (path.endsWith('/organizations')) return route.fulfill({ json: [{ id: 'org', name: 'Org' }] });
    if (path.endsWith('/assessments/blocked')) return route.fulfill({ json: report(false) });
    if (path.endsWith('/assessments/approved')) return route.fulfill({ json: report(true) });
    if (path.endsWith('/license-approvals')) {
      expect(route.request().postDataJSON()).toMatchObject({
        assessmentId: 'blocked', evaluationId: 'evaluation', kind: 'conditions-met', proofUrl: proof,
      });
      return route.fulfill({ status: 201, json: decision });
    }
    if (path.endsWith('/license-approvals/approval')) return route.fulfill({ json: { ...decision, proofUrl: proof } });
    if (path.endsWith('/license-recheck')) return route.fulfill({ status: 202, json: { queued: true } });
    return route.fulfill({ json: [] });
  });

  await page.goto('/assessments/blocked');
  await expect(page.getByText('Auslieferung an Kunden', { exact: true })).toBeVisible();
  await page.getByText('psycopg-binary · 3.3.3', { exact: true }).click();
  await page.getByText('Nutzung freigeben', { exact: true }).click();
  await page.getByLabel('Begründung').fill(decision.reason);
  await page.getByLabel('Erfüllte Auflagen oder Vertragsumfang').fill(decision.conditions);
  await page.getByLabel('Geschützter HTTPS-Nachweislink').fill(proof);
  await page.getByRole('button', { name: 'Freigabe speichern' }).click();
  await expect(page.getByText(/Freigabe gespeichert/)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Geschützten Beleg öffnen' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Nachweislink laden' }).click();
  await expect(page.getByRole('link', { name: 'Geschützten Beleg öffnen' })).toHaveAttribute('href', proof);
  await page.getByRole('button', { name: 'Diesen Commit erneut prüfen' }).click();
  await expect(page.getByText('Erneute Prüfung eingeplant.', { exact: false })).toBeVisible();
  await page.goto('/assessments/approved');
  await expect(page.getByRole('heading', { name: 'Prüfung bestanden' })).toBeVisible();
  await page.getByText('Bewertungen mit Freigabe (1)', { exact: true }).click();
  await expect(page.getByText('LGPL-3.0-only', { exact: true })).toBeVisible();
  await expect(page.getByText('Mit Freigabe', { exact: true })).toBeVisible();
});

test('an unresolved source archive blocks the package and keeps the wheel evidence visible', async ({ page }) => {
  const wheel = 'certifi-2026.11.20-py3-none-any.whl';
  const wheelUrl = 'https://files.pythonhosted.org/packages/example/' + wheel;
  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/config')) return route.fulfill({ json: { enabled: false } });
    if (path.endsWith('/organizations')) return route.fulfill({ json: [{ id: 'org', name: 'Org' }] });
    if (!path.endsWith('/assessments/certifi')) return route.fulfill({ json: [] });
    return route.fulfill({ json: {
      licenseUse: 'customer-distribution', canApproveLicenses: true,
      assessment: {
        id: 'certifi', organizationId: 'org', productId: 'product', context: 'pull_request',
        gitSha: 'a'.repeat(40), environment: 'customer-distribution', pullRequestNumber: 17,
        counts: { PASS: 0, FAIL: 1, UNKNOWN: 0, NOT_APPLICABLE: 0 },
      },
      findings: [],
      evaluations: [{
        id: 'evaluation', status: 'FAIL', licenseApprovalEligible: true, evidenceIds: ['evidence'],
        reason: 'Lizenznachweis für mindestens eine Paketdatei fehlt oder ist ungeklärt',
        subject: { id: 'package', labels: { name: 'certifi', version: '2026.11.20', lockfile: 'uv.lock' } },
        control: { id: 'PY-LIC-001' },
      }],
      evidence: [{
        id: 'evidence',
        value: { licenseCoverage: 'incomplete', artifacts: [
          { artifactSha256: 'a'.repeat(64), filename: wheel, sourceUrl: wheelUrl, status: 'OBSERVED', licenseExpression: 'MPL-2.0' },
          { artifactSha256: 'b'.repeat(64), filename: 'certifi-2026.11.20.tar.gz', status: 'UNKNOWN', reason: 'dynamic license declaration' },
        ] },
      }],
    } });
  });

  await page.goto('/assessments/certifi');
  await page.getByText('certifi · 2026.11.20', { exact: true }).click();
  await page.getByText('Lizenznachweise pro Paketdatei (2)').click();
  await expect(page.getByRole('link', { name: wheel })).toHaveAttribute('href', wheelUrl);
  await expect(page.getByText(/MPL-2.0 belegt/)).toBeVisible();
  await expect(page.getByText(/certifi-2026.11.20.tar.gz · Ungeklärt · Dynamische Lizenzangabe im Quellarchiv/)).toBeVisible();
  await page.getByText('Nutzung freigeben', { exact: true }).click();
  await expect(page.locator('option[value="conditions-met"]')).toHaveCount(0);
});
