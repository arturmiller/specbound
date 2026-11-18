"""Explicit revision adoption, rollback fences and unchanged historical results."""

import copy
import json
import unittest

from app.database import get_engine
from app.identity import get_current_principal
from app.main import app
from app.tables import resource_documents
from sqlalchemy import func, select

from tests import test_public_license_scans as scan_tests


class ResourceUpdatesTest(unittest.TestCase):
    setUp = scan_tests.PublicLicenseScansTest.setUp
    tearDown = scan_tests.PublicLicenseScansTest.tearDown
    configure_native_product = (
        scan_tests.PublicLicenseScansTest.configure_native_product
    )
    finish_profile_scan = scan_tests.PublicLicenseScansTest.finish_profile_scan
    observed_result = staticmethod(scan_tests.PublicLicenseScansTest.observed_result)

    def prepare(self):
        self.configure_native_product()
        governance = self.client.get(f"/products/{self.product}/governance").json()
        self.original_product = governance["product"]
        self.original_profile = governance["profile"]
        self.resources = f"/organizations/{self.org}/resources"
        self.product_url = self.resources + "/" + self.original_product["id"]

    def change(self, path, edit):
        document = json.loads(self.source.files[path])
        edit(document)
        self.source.files[path] = json.dumps(document).encode()

    def stage_profile(self):
        self.source.commit = "c" * 40

        def edit(document):
            document["profile"]["metadata"]["version"] = "2.0.0"
            document["profile"]["modify"]["set-parameters"][0]["values"] = [
                "GPL-3.0-only"
            ]

        self.change("profiles/application-baseline.json", edit)
        url = self.resources + "/" + self.original_profile["id"]
        checked = self.client.post(url + "/check", json={})
        self.assertEqual(checked.status_code, 200, checked.text)
        self.assertTrue(checked.json()["references"]["currentProducts"])
        saved = self.client.post(url + "/adopt", json=self.adoption(checked.json()))
        self.assertEqual(saved.status_code, 201, saved.text)
        # Adopting a Profile does not repoint existing products.
        self.assertEqual(
            self.client.get(f"/products/{self.product}/governance").json()["profile"][
                "id"
            ],
            self.original_profile["id"],
        )

    @staticmethod
    def adoption(check):
        return {
            "commit": check["candidate"]["source"]["commit"],
            "reviewDigest": check["reviewDigest"],
            "ref": check["candidate"]["source"]["ref"],
            "refType": check["candidate"]["source"]["refType"],
        }

    def new_product(self):
        def edit(document):
            document["metadata"]["version"] = "2.0.0"
            document["metadata"]["name"] = "Updated Audio Visualizer"
            document["spec"]["profile"]["version"] = "2.0.0"
            document["spec"]["repositories"] = [
                {"provider": "github", "repository": "example/new-source"}
            ]

        self.change("products/audio-visualizer.json", edit)

    def count_resources(self):
        with get_engine().connect() as db:
            return db.execute(
                select(func.count())
                .select_from(resource_documents)
                .where(resource_documents.c.organization_id == self.org)
            ).scalar_one()

    def test_product_adoption_preserves_assessment_and_queued_configuration(self):
        self.prepare()
        historical = self.finish_profile_scan(self.observed_result("GPL-3.0-only"))
        queued = self.client.post(self.url, json={"ref": "main"}).json()
        self.stage_profile()
        self.new_product()
        before = self.count_resources()
        checked = self.client.post(self.product_url + "/check", json={})
        self.assertEqual(checked.status_code, 200, checked.text)
        check = checked.json()
        self.assertEqual(check["assessmentImpact"], "not_computed")
        self.assertEqual(check["candidate"]["version"], "2.0.0")
        self.assertTrue(
            any("repositories" in item["path"] for item in check["changes"])
        )
        self.assertEqual(self.count_resources(), before)
        self.assertEqual(
            self.client.get(f"/products/{self.product}/governance").json()["product"][
                "id"
            ],
            self.original_product["id"],
        )
        saved = self.client.post(self.product_url + "/adopt", json=self.adoption(check))
        self.assertEqual(saved.status_code, 201, saved.text)
        adopted = saved.json()
        self.assertNotEqual(adopted["id"], self.original_product["id"])
        self.assertEqual(
            self.client.get(f"/products/{self.product}").json()["name"],
            "Updated Audio Visualizer",
        )
        bindings = self.client.get(f"/products/{self.product}/repositories").json()
        self.assertEqual(
            [row["repository"] for row in bindings], ["example/new-source"]
        )
        self.assertNotEqual(bindings[0]["id"], self.binding)
        self.assertEqual(
            self.client.post(self.url, json={"ref": "main"}).status_code, 409
        )
        self.assertEqual(self.client.get(self.product_url).status_code, 200)
        self.assertIn(
            self.original_product["id"],
            [row["id"] for row in self.client.get(self.resources).json()],
        )
        self.assertEqual(
            self.client.get("/assessments/" + historical["assessment"]["id"]).json(),
            historical,
        )
        from public_license_worker import poll_once

        self.assertTrue(
            poll_once(
                get_engine(),
                execute=lambda *_: {
                    "status": "ok",
                    "result": self.observed_result("GPL-3.0-only"),
                },
                job_id=queued["id"],
            )
        )
        old_scan = next(
            row for row in self.client.get(self.url).json() if row["id"] == queued["id"]
        )
        self.assertEqual(old_scan["status"], "completed")
        self.assertEqual(old_scan["governanceContext"]["profile"]["version"], "1.0.0")
        new_url = f"/products/{self.product}/repositories/{bindings[0]['id']}/public-license-scans"
        new_job = self.client.post(new_url, json={"ref": "main"})
        self.assertEqual(new_job.status_code, 201, new_job.text)
        self.assertEqual(
            new_job.json()["governanceContext"]["profile"]["version"], "2.0.0"
        )
        self.assertTrue(
            poll_once(
                get_engine(),
                execute=lambda *_: {
                    "status": "ok",
                    "result": self.observed_result("GPL-3.0-only"),
                },
                job_id=new_job.json()["id"],
            )
        )
        history = self.client.get(self.product_url + "/adoptions").json()
        self.assertEqual(history[-1]["actorId"], self.owner)
        self.assertEqual(history[-1]["details"]["revisionId"], adopted["id"])
        self.assertEqual(
            self.client.post(self.product_url + "/check", json={}).status_code, 409
        )

    def test_invalid_or_changed_candidate_never_changes_current_state(self):
        self.prepare()
        self.stage_profile()
        self.new_product()
        checked = self.client.post(self.product_url + "/check", json={}).json()
        count = self.count_resources()
        valid_files = copy.deepcopy(self.source.files)
        self.source.commit = "d" * 40
        self.assertEqual(
            self.client.post(
                self.product_url + "/adopt", json=self.adoption(checked)
            ).status_code,
            409,
        )
        self.source.commit = "c" * 40
        self.change(
            "products/audio-visualizer.json",
            lambda doc: doc["spec"]["profile"].update(version="99.0.0"),
        )
        self.assertEqual(
            self.client.post(self.product_url + "/check", json={}).status_code, 422
        )
        self.assertEqual(
            self.client.post(
                self.product_url + "/adopt", json=self.adoption(checked)
            ).status_code,
            422,
        )
        self.source.files = valid_files
        bad_digest = self.adoption(checked) | {"reviewDigest": "0" * 64}
        self.assertEqual(
            self.client.post(self.product_url + "/adopt", json=bad_digest).status_code,
            409,
        )
        self.assertEqual(self.count_resources(), count)
        self.assertEqual(
            self.client.get(f"/products/{self.product}/governance").json()["product"][
                "id"
            ],
            self.original_product["id"],
        )
        self.assertEqual(self.client.get(self.product_url + "/adoptions").json(), [])

    def test_viewer_and_agent_cannot_check_or_adopt_revisions(self):
        self.prepare()
        team = self.client.get(f"/products/{self.product}").json()["ownerTeamId"]
        agent = self.client.post(
            f"/organizations/{self.org}/agents", json={"name": "Reader"}
        ).json()["id"]
        for principal in ("user:viewer", agent):
            self.client.post(
                f"/teams/{team}/members",
                json={"principalId": principal, "role": "viewer"},
            )
            app.dependency_overrides[get_current_principal] = lambda: principal
            self.assertEqual(
                self.client.post(self.product_url + "/check", json={}).status_code, 403
            )
            self.assertEqual(
                self.client.post(
                    self.product_url + "/adopt",
                    json={"commit": "a" * 40, "reviewDigest": "b" * 64},
                ).status_code,
                403,
            )
            self.assertEqual(
                self.client.get(self.product_url + "/adoptions").status_code, 200
            )
            app.dependency_overrides[get_current_principal] = lambda: self.owner

    def test_pack_contract_changes_are_reviewed_without_execution_approval(self):
        self.prepare()
        config = {
            "apiVersion": "specbound.example/v1alpha1",
            "kind": "ResourceSource",
            "metadata": {"id": "pack-source", "version": "1.0.0", "name": "Pack"},
            "spec": {
                "resourceType": "EvidenceProviderPack",
                "provider": "github",
                "repository": self.source.repository,
                "ref": "main",
                "manifestPath": "evidence/second/provider.json",
                "expected": {"id": "org.specbound.example-license", "version": "1.0.0"},
            },
        }
        first = self.client.post(self.resources, json=config)
        self.assertEqual(first.status_code, 201, first.text)
        url = self.resources + "/" + first.json()["id"]
        self.source.commit = "c" * 40

        def edit(document):
            document["metadata"]["version"] = "2.0.0"
            document["capabilities"][0]["version"] = "v2"
            document["permissions"] = {"network": ["pypi.org"]}

        self.change("evidence/second/provider.json", edit)
        checked = self.client.post(url + "/check", json={})
        self.assertEqual(checked.status_code, 200, checked.text)
        self.assertTrue(
            any("capabilities" in item["path"] for item in checked.json()["changes"])
        )
        valid = copy.deepcopy(self.source.files)
        self.source.files["evidence/second/contracts/request.json"] = b'{"type":42}'
        count = self.count_resources()
        self.assertEqual(
            self.client.post(
                url + "/adopt", json=self.adoption(checked.json())
            ).status_code,
            422,
        )
        self.assertEqual(self.count_resources(), count)
        self.source.files = valid
        adopted = self.client.post(url + "/adopt", json=self.adoption(checked.json()))
        self.assertEqual(adopted.status_code, 201, adopted.text)
        self.assertEqual(
            adopted.json()["resolved"]["executionApproval"], "not_available"
        )
        self.assertEqual(self.client.get(url).json()["version"], "1.0.0")

    def test_catalog_identity_conflict_and_moved_tag_are_rejected_during_check(self):
        self.prepare()
        catalog_id = self.original_profile["resolved"]["catalog"]["revisionId"]
        url = self.resources + "/" + catalog_id
        old_files = copy.deepcopy(self.source.files)
        self.source.commit = "c" * 40
        self.change(
            "catalogs/application.json",
            lambda doc: doc["catalog"]["metadata"].update(
                title="Changed without version"
            ),
        )
        self.assertEqual(self.client.post(url + "/check", json={}).status_code, 409)
        self.source.files = old_files
        checked = self.client.post(
            url + "/check", json={"refType": "tag", "ref": "v1.0.0"}
        )
        self.assertEqual(checked.status_code, 200, checked.text)
        adopted = self.client.post(url + "/adopt", json=self.adoption(checked.json()))
        self.assertEqual(adopted.status_code, 201, adopted.text)
        self.source.commit = "d" * 40
        response = self.client.post(
            self.resources + "/" + adopted.json()["id"] + "/check", json={}
        )
        self.assertEqual(response.status_code, 409, response.text)
