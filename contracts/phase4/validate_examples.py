"""Offline checks using the same contracts as the resource importer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/api"))
from app.resource_contracts import (  # noqa: E402
    HERE as HERE,
)
from app.resource_contracts import (
    ROOT as ROOT,
)
from app.resource_contracts import (
    compile_bindings as compile_example_bindings,
)
from app.resource_contracts import (
    identity as identity,
)
from app.resource_contracts import (
    imported_path as imported_path,
)
from app.resource_contracts import (
    read as read,
)
from app.resource_contracts import (
    resolve_profile as resolve_example_profile,
)
from app.resource_contracts import (
    validate as validate,
)
from app.resource_contracts import (
    verify_vendor as verify_vendor,
)


def check_examples():
    verify_vendor()
    examples = HERE / "examples"
    for name, path in [
        ("product", "products/audio-visualizer.json"),
        ("resource-source", "sources/profile.json"),
        ("workspace", "workspace.json"),
    ]:
        validate(read(examples / path), HERE / f"{name}.schema.json")
    profile = read(examples / "profiles/application-baseline.json")
    resolved = resolve_example_profile(
        profile,
        {"catalogs/application.json": read(examples / "catalogs/application.json")},
        profile_path="profiles/application-baseline.json",
    )
    if (
        read(examples / "products/audio-visualizer.json")["spec"]["profile"]
        != resolved["profile"]
    ):
        raise ValueError("Product references a different profile")
    source = read(examples / "sources/profile.json")["spec"]
    if (
        source["expected"] != resolved["profile"]
        or source["manifestPath"] != "profiles/application-baseline.json"
    ):
        raise ValueError("Registered source does not identify the profile")
    checks = compile_example_bindings(
        read(examples / resolved["bindingPath"]), resolved
    )
    for folder in ("example", "second"):
        validate(
            read(examples / f"evidence/{folder}/provider.json"),
            ROOT / "v1/evidence-provider-pack.schema.json",
        )
        validate(
            read(examples / f"sources/evidence-{folder}.json"),
            HERE / "resource-source.schema.json",
        )
    return checks


if __name__ == "__main__":
    result = check_examples()
    print(
        f"OSCAL 1.2.3 examples and local contracts valid; {len(result)} selected control bindings resolved."
    )
