"""Isolated OIDC provider for browser tests; not used by the application."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "http://127.0.0.1:18764"
WEB_ORIGIN = "http://127.0.0.1:18766"
CLIENT = "specbound-web"
AUDIENCE = "urn:specbound:api"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
CODES = {}
PUBLIC_JWK = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key()))
PUBLIC_JWK.update({"kid": "e2e-key", "use": "sig", "alg": "RS256"})


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _json(self, value, status=200):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", WEB_ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", WEB_ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        request = urlsplit(self.path)
        if request.path == "/.well-known/openid-configuration":
            return self._json(
                {
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/authorize",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/jwks",
                    "response_types_supported": ["code"],
                    "subject_types_supported": ["public"],
                    "id_token_signing_alg_values_supported": ["RS256"],
                    "token_endpoint_auth_methods_supported": ["none"],
                    "code_challenge_methods_supported": ["S256"],
                }
            )
        if request.path == "/jwks":
            return self._json({"keys": [PUBLIC_JWK]})
        if request.path == "/authorize":
            params = parse_qs(request.query)

            def get(name):
                return params.get(name, [""])[0]

            if (
                get("client_id") != CLIENT
                or get("redirect_uri") != f"{WEB_ORIGIN}/"
                or get("response_type") != "code"
                or get("code_challenge_method") != "S256"
                or not all(get(key) for key in ("code_challenge", "state", "nonce"))
                or get("resource") != AUDIENCE
                or "openid" not in get("scope").split()
            ):
                return self._json({"error": "invalid_request"}, 400)
            code = secrets.token_urlsafe(32)
            CODES[code] = {"challenge": get("code_challenge"), "nonce": get("nonce")}
            self.send_response(302)
            self.send_header(
                "Location",
                f"{WEB_ORIGIN}/?{urlencode({'code': code, 'state': get('state')})}",
            )
            self.end_headers()
            return
        self.send_error(404)

    def do_POST(self):
        if self.path != "/token":
            return self._json({"error": "not_found"}, 404)
        params = parse_qs(
            self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode()
        )

        def get(name):
            return params.get(name, [""])[0]

        saved = CODES.pop(get("code"), None)
        verifier = get("code_verifier")
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        if (
            not saved
            or not verifier
            or not hmac.compare_digest(saved["challenge"], challenge)
            or get("client_id") != CLIENT
            or get("redirect_uri") != f"{WEB_ORIGIN}/"
            or get("grant_type") != "authorization_code"
        ):
            return self._json({"error": "invalid_grant"}, 400)
        now = int(time.time())
        id_token = jwt.encode(
            {
                "iss": ISSUER,
                "sub": "alice",
                "aud": CLIENT,
                "iat": now,
                "exp": now + 300,
                "nonce": saved["nonce"],
            },
            KEY,
            algorithm="RS256",
            headers={"kid": "e2e-key"},
        )
        access_token = jwt.encode(
            {
                "iss": ISSUER,
                "sub": "alice",
                "aud": AUDIENCE,
                "client_id": CLIENT,
                "scope": "openid profile",
                "iat": now,
                "exp": now + 300,
                "jti": str(uuid4()),
            },
            KEY,
            algorithm="RS256",
            headers={"kid": "e2e-key", "typ": "at+jwt"},
        )
        return self._json(
            {
                "access_token": access_token,
                "id_token": id_token,
                "token_type": "Bearer",
                "expires_in": 300,
            }
        )


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 18764), Handler).serve_forever()
