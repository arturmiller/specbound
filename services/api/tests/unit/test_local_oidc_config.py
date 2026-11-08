"""The local provider exception must never broaden normal OIDC trust."""

import os
import unittest
from unittest.mock import patch

from app.identity import oidc_config


class LocalOidcConfigTest(unittest.TestCase):
    def test_dev_exception_is_explicit_and_fixed_to_the_local_provider(self):
        base = {
            "OIDC_ISSUER": "http://127.0.0.1:15556",
            "OIDC_JWKS_URL": "http://local-oidc:5556/jwks",
            "OIDC_CLIENT_ID": "specbound-web",
            "OIDC_AUDIENCE": "urn:specbound:api",
        }
        with patch.dict(os.environ, base, clear=True):
            self.assertIsNone(oidc_config())
        with patch.dict(os.environ, {**base, "SPECBOUND_LOCAL_DEV_OIDC": "1"}, clear=True):
            self.assertIsNotNone(oidc_config())
        for changed in (
            {"SPECBOUND_LOCAL_DEV_OIDC": "true"},
            {"OIDC_ISSUER": "http://127.0.0.1:15557"},
            {"OIDC_JWKS_URL": "http://other-host:5556/jwks"},
            {"OIDC_JWKS_URL": "http://local-oidc:5556/other"},
            {"OIDC_CLIENT_ID": "urn:specbound:api"},
        ):
            with self.subTest(changed=changed):
                with patch.dict(
                    os.environ,
                    {**base, "SPECBOUND_LOCAL_DEV_OIDC": "1", **changed},
                    clear=True,
                ):
                    self.assertIsNone(oidc_config())
