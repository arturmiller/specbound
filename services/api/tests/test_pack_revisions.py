"""Pin and activate revisions through the pack revision boundary."""

import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from app.database import get_engine
from app.identity import get_current_principal
from app.main import app
from app.pack_revisions import (
    TagMoved,
    activate_release,
    get_active_release,
    pin_release,
    verify_release,
)
from fastapi.testclient import TestClient


class FakeSource:
    def __init__(self):
        self.commit = "a" * 40

    def resolve_tag(self, tag):
        if tag not in ("v1", "v2"):
            raise ValueError("unknown tag")
        return self.commit


class PackRevisionTest(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DATABASE_URL"):
            self.fail("DATABASE_URL must point to a disposable migrated database")
        app.dependency_overrides[get_current_principal] = lambda: "user:owner"
        self.client = TestClient(app)
        self.org = self.client.post("/organizations", json={"name": "Packs"}).json()[
            "id"
        ]
        self.other = self.client.post("/organizations", json={"name": "Other"}).json()[
            "id"
        ]
        self.source = FakeSource()

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_moved_tag_does_not_change_activated_revision(self):
        with get_engine().begin() as db:
            release = pin_release(db, self.org, "example/packs", "v1", self.source)
            activate_release(db, self.org, release["id"], self.source)
        self.source.commit = "b" * 40
        with get_engine().begin() as db:
            with self.assertRaises(TagMoved) as conflict:
                verify_release(db, self.org, release["id"], self.source)
            self.assertEqual(conflict.exception.pinned, "a" * 40)
            self.assertEqual(conflict.exception.observed, "b" * 40)
            active = get_active_release(db, self.org, "example/packs")
            self.assertEqual(active["commit"], "a" * 40)
            self.assertEqual(active["tag"], "v1")
            self.assertEqual(active["repository"], "example/packs")
            with self.assertRaises(TagMoved):
                pin_release(db, self.org, "example/packs", "v1", self.source)
        with get_engine().begin() as db:
            self.assertEqual(
                get_active_release(db, self.org, "example/packs")["commit"], "a" * 40
            )
            self.assertIsNone(get_active_release(db, self.other, "example/packs"))

    def test_pinning_is_idempotent_and_activation_is_scoped(self):
        with get_engine().begin() as db:
            first = pin_release(db, self.org, "example/packs", "v1", self.source)
            second = pin_release(db, self.org, "example/packs", "v1", self.source)
            self.assertEqual(first, second)
            with self.assertRaises(LookupError):
                activate_release(db, self.other, first["id"], self.source)
            self.assertIsNone(get_active_release(db, self.org, "example/packs"))

    def test_moved_tag_cannot_be_activated_and_new_tag_can_replace_pointer(self):
        with get_engine().begin() as db:
            first = pin_release(db, self.org, "example/packs", "v1", self.source)
            self.source.commit = "b" * 40
            with self.assertRaises(TagMoved):
                activate_release(db, self.org, first["id"], self.source)
            self.assertIsNone(get_active_release(db, self.org, "example/packs"))
            second = pin_release(db, self.org, "example/packs", "v2", self.source)
            activate_release(db, self.org, second["id"], self.source)
            self.assertEqual(
                get_active_release(db, self.org, "example/packs")["id"], second["id"]
            )

    def test_concurrent_pins_are_idempotent(self):
        if get_engine().dialect.name != "postgresql":
            self.skipTest("PostgreSQL transaction and locking behavior")
        barrier = threading.Barrier(4)

        def pin(_):
            barrier.wait(timeout=15)
            with get_engine().begin() as db:
                return pin_release(db, self.org, "example/packs", "v1", self.source)[
                    "id"
                ]

        with ThreadPoolExecutor(max_workers=4) as executor:
            ids = list(executor.map(pin, range(4)))
        self.assertEqual(len(set(ids)), 1)


if __name__ == "__main__":
    unittest.main()
