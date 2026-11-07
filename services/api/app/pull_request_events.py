"""Validate PR heads and enqueue them for matching organization repositories."""

import re
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.engine import Connection

from app.tables import products, repo_bindings, teams


def parse_pr_event(payload):
    if payload.get("action") not in ("opened", "synchronize"):
        return None
    try:
        repository = payload["repository"]
        pull_request = payload["pull_request"]
        repo_id = repository["id"]
        name = repository["full_name"]
        pr_id = pull_request["id"]
        number = payload["number"]
        head = pull_request["head"]["sha"]
        if (
            type(repo_id) is not int
            or not 0 < repo_id < 2**63
            or type(pr_id) is not int
            or not 0 < pr_id < 2**63
            or type(number) is not int
            or not 0 < number < 2**31
            or type(pull_request["number"]) is not int
            or pull_request["number"] != number
            or type(pull_request["base"]["repo"]["id"]) is not int
            or pull_request["base"]["repo"]["id"] != repo_id
            or not isinstance(name, str)
            or len(name) > 200
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name)
            or not isinstance(head, str)
            or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", head)
        ):
            raise ValueError("Invalid pull request event")
        return {"repository": name, "pr_id": pr_id, "number": number, "head": head}
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid pull request event") from exc


def enqueue_pr_event(db: Connection, organization_id, delivery_id, event):
    bindings = db.execute(
        select(repo_bindings.c.id, repo_bindings.c.product_id)
        .select_from(
            repo_bindings.join(
                products, repo_bindings.c.product_id == products.c.id
            ).join(teams, products.c.owner_team_id == teams.c.id)
        )
        .where(
            teams.c.organization_id == organization_id,
            func.lower(repo_bindings.c.provider) == "github",
            func.lower(repo_bindings.c.repository) == event["repository"].lower(),
        )
    ).all()
    for binding_id, product_id in bindings:
        db.execute(
            text(
                "INSERT INTO assessment_jobs (id, organization_id, product_id, binding_id, delivery_id, pull_request_id, pull_request_number, head_sha) "
                "VALUES (:id, :org, :product, :binding, :delivery, :pr_id, :number, :head) "
                "ON CONFLICT (binding_id, pull_request_number, head_sha) DO NOTHING"
            ),
            {
                "id": str(uuid4()),
                "org": organization_id,
                "product": product_id,
                "binding": binding_id,
                "delivery": delivery_id,
                "pr_id": event["pr_id"],
                "number": event["number"],
                "head": event["head"],
            },
        )
