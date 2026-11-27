"""The product's own declaration for one scan: source paths and implemented controls.

Profiles and catalogs always come from the organization's registered resources.
Only what the product team declares about itself (which folders belong to the
product and how it implements selected controls) may be read from the pull
request commit, so a change can be checked in the pull request that makes it.
"""

import copy

from app.product_manifest import check_implemented_requirements


def _registered(context):
    product = context["product"]
    return {
        "source": "registered",
        "repository": product["source"]["repository"],
        "manifestPath": product["source"]["manifestPath"],
        "commit": product["source"]["commit"],
        "repositories": copy.deepcopy(product["resolved"]["repositories"]),
        "implementedRequirements": copy.deepcopy(
            product["resolved"].get("implementedRequirements", [])
        ),
    }


def freeze_declaration(context, *, repository=None, head=None, read_product=None):
    """Add the declaration that applies to this scan to a frozen governance context.

    A pull request in the repository that holds the product manifest uses the
    manifest at its head commit. An invalid manifest, or one that changes the
    product identity or profile, never grants anything: it keeps the registered
    source paths and declares no control implementations.
    """
    if not context or context.get("mode") != "profile":
        return context
    registered = _registered(context)
    declaration = registered
    if (
        repository is not None
        and head is not None
        and read_product is not None
        and registered["repository"].lower() == repository.lower()
    ):
        product, profile = context["product"], context["profile"]
        declaration = {
            **registered,
            "source": "pull-request",
            "commit": head,
            "implementedRequirements": [],
        }
        try:
            loaded = read_product(repository, head, registered["manifestPath"])
            if loaded["id"] != product["resourceId"]:
                raise ValueError("The pull request changes the product identity")
            if loaded["resolved"]["profile"] != {
                "id": profile["resourceId"],
                "version": profile["version"],
            }:
                raise ValueError(
                    "The pull request references a profile version that is not "
                    "the registered one"
                )
            check_implemented_requirements(
                loaded["resolved"], profile["resolved"]["selectedControlIds"]
            )
            declaration.update(
                repositories=copy.deepcopy(loaded["resolved"]["repositories"]),
                implementedRequirements=copy.deepcopy(
                    loaded["resolved"].get("implementedRequirements", [])
                ),
            )
        except Exception as exc:  # noqa: BLE001 - any failure grants nothing
            message = str(exc) if isinstance(exc, ValueError) else ""
            declaration["error"] = (
                message[:500] or "The product manifest could not be read"
            )
    return {**context, "productDeclaration": declaration}


def product_declaration(context):
    if not context or context.get("mode") != "profile":
        return None
    return context.get("productDeclaration") or _registered(context)


def product_paths(context, repository):
    """Folders of this repository that belong to the product; None means all."""
    declaration = product_declaration(context)
    if declaration is None or not isinstance(repository, str):
        return None
    for item in declaration["repositories"]:
        if item["repository"].lower() == repository.lower():
            return item.get("paths")
    return None


def scope_to_product(result, paths):
    """Keep lockfiles under the product's paths and disclose all others."""
    if not paths or not isinstance(result, dict):
        return result
    prefixes = tuple(path.rstrip("/") + "/" for path in paths)
    files = result.get("files")
    if not isinstance(files, list):
        return result
    inside = [
        path for path in files if isinstance(path, str) and path.startswith(prefixes)
    ]
    outside = sorted(path for path in files if path not in inside)
    return {
        **result,
        "files": inside,
        "outsideProductPaths": outside,
        "packages": [
            package
            for package in result.get("packages") or []
            if not isinstance(package, dict) or package.get("path") not in outside
        ],
    }


def library_use(context):
    """Declared control implementations and the basis shown in explanations."""
    declaration = product_declaration(context)
    if declaration is None:
        return None
    product, profile = context["product"], context["profile"]
    origin = (
        "Pull-Request-Commit" if declaration["source"] == "pull-request" else "Commit"
    )
    return {
        "implemented": frozenset(
            item["controlId"] for item in declaration["implementedRequirements"]
        ),
        "basis": (
            f"erklärt in Produkt {product['resourceId']}, {origin} "
            f"{declaration['commit'][:12]}; Profil {profile['resourceId']} "
            f"{profile['version']}"
        ),
    }
