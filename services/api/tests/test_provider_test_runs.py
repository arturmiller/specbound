"""Synthetic run requests remain owner-scoped and separate from evidence."""

import unittest
from uuid import uuid4

from app.database import get_engine
from app.identity import get_current_principal
from app.main import app
from app.tables import (
    assessment_snapshots,
    evidence_records,
    findings,
    pack_catalog,
    pack_revisions,
    principals,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select


class ProviderTestRunsTest(unittest.TestCase):
    def setUp(self):
        self.owner = f"user:{uuid4()}"
        self.other = f"user:{uuid4()}"
        with get_engine().begin() as db:
            for principal in (self.owner, self.other):
                db.execute(insert(principals).values(id=principal, kind="user", issuer="test", subject=principal))
        app.dependency_overrides[get_current_principal] = lambda: self.owner
        self.client = TestClient(app)
        self.org = self.client.post('/organizations', json={'name': 'Run organization'}).json()['id']
        self.pack = str(uuid4())
        with get_engine().begin() as db:
            db.execute(insert(pack_revisions).values(id=self.pack, organization_id=self.org, repository='arturmiller/specbound-example-provider', tag='v1.1.0', commit_sha='a' * 40))
            db.execute(insert(pack_catalog).values(revision_id=self.pack, kind='provider', manifest={}, controls=[], capabilities=[{'id': 'demo.fixture', 'version': 'v1'}]))
        self.url = f'/organizations/{self.org}/packs/{self.pack}/test-runs'

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_owner_can_request_and_reload_without_creating_evidence(self):
        self.assertEqual(self.client.get(self.url).json(), [])
        response = self.client.post(self.url, json={})
        self.assertEqual(response.status_code, 201, response.text)
        run = response.json()
        self.assertEqual((run['status'], run['synthetic'], run['packCommit']), ('pending', True, 'a' * 40))
        self.assertEqual(self.client.get(self.url).json(), [run])
        with get_engine().connect() as db:
            for table in (evidence_records, findings, assessment_snapshots):
                self.assertEqual(db.execute(select(func.count()).select_from(table).where(table.c.organization_id == self.org)).scalar_one(), 0)

    def test_rejects_extra_inputs_and_other_principals(self):
        for payload in ({'command': ['sh']}, {'credentialsRef': 'credential:x'}, {'image': 'example'}):
            self.assertEqual(self.client.post(self.url, json=payload).status_code, 422)
        team = self.client.post(f'/organizations/{self.org}/teams', json={'name': 'Viewers'}).json()['id']
        membership = self.client.post(f'/teams/{team}/members', json={'principalId': self.other, 'role': 'viewer'})
        self.assertEqual(membership.status_code, 201, membership.text)
        app.dependency_overrides[get_current_principal] = lambda: self.other
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, json={}).status_code, 403)
        other_org = self.client.post('/organizations', json={'name': 'Another organization'}).json()['id']
        other_url = f'/organizations/{other_org}/packs/{self.pack}/test-runs'
        self.assertEqual(self.client.get(other_url).status_code, 404)
        self.assertEqual(self.client.post(other_url, json={}).status_code, 404)

    def test_other_pack_is_not_a_test_provider(self):
        with get_engine().begin() as db:
            db.execute(pack_revisions.update().where(pack_revisions.c.id == self.pack).values(repository='other/repository'))
        self.assertEqual(self.client.post(self.url, json={}).status_code, 422)
        self.assertEqual(self.client.get(self.url).status_code, 422)
