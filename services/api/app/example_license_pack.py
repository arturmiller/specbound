"""Load the exact committed example license policy, never a floating file."""

import hashlib
from pathlib import Path

from app.git_source import GitSnapshot
from app.governance_pack import load_governance_pack

# The commit actually contains both files below. A changed pack requires a new
# commit and a corresponding explicit update to these pins.
POLICY_REVISION = "22c819b631d60fc0f561f376379e9de85edfe96c"
FILE_SHA256 = {
    "pack.yaml": "5e9b99158adb404f2c6d4f1f9acc16935db031ff7d5064376e7200a7f5244cae",
    "controls/PY-LIC-001.yaml": "9029e030f98a612f741e8c89b021ccefc1f7084136fb925cfec26efb18c01e4a",
}


def load_example_license_pack(directory=None):
    if directory is None:
        parents = Path(__file__).resolve().parents
        candidates = [parents[1] / "policies/python-license"]
        if len(parents) > 3:
            candidates.append(parents[3] / "policies/python-license")
        directory = next((path for path in candidates if path.is_dir()), candidates[0])
    directory = Path(directory)
    files = {}
    for name, expected in FILE_SHA256.items():
        content = (directory / name).read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(
                "Bundled governance policy differs from its pinned revision"
            )
        files[name] = content
    return load_governance_pack(GitSnapshot(POLICY_REVISION, files))
