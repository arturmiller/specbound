from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table

metadata = MetaData()
organizations = Table(
    "organizations",
    metadata,
    Column("id", String),
    Column("name", String),
    Column("owner_principal_id", String),
)
teams = Table(
    "teams",
    metadata,
    Column("id", String),
    Column("organization_id", String),
    Column("name", String),
)
members = Table(
    "team_members",
    metadata,
    Column("id", String),
    Column("team_id", String),
    Column("principal_id", String),
    Column("role", String),
)
principals = Table(
    "principals",
    metadata,
    Column("id", String),
    Column("kind", String),
    Column("issuer", String),
    Column("subject", String),
)
agents = Table(
    "agents",
    metadata,
    Column("principal_id", String),
    Column("organization_id", String),
    Column("name", String),
)
audit_events = Table(
    "audit_events",
    metadata,
    Column("id", String),
    Column("organization_id", String),
    Column("actor_id", String),
    Column("action", String),
    Column("target_id", String),
    Column("team_id", String),
    Column("details", JSON),
    Column("occurred_at", DateTime(timezone=True)),
)
products = Table(
    "products",
    metadata,
    Column("id", String),
    Column("owner_team_id", String),
    Column("name", String),
)
repo_bindings = Table(
    "repo_bindings",
    metadata,
    Column("id", String),
    Column("product_id", String),
    Column("provider", String),
    Column("repository", String),
)
scanner_coverage = Table(
    "scanner_coverage",
    metadata,
    Column("id", Integer),
    Column("binding_id", String),
    Column("scanner", String),
    Column("ref", String),
    Column("status", String),
    Column("source_revision", String),
    Column("observed_at", DateTime(timezone=True)),
    Column("files", JSON),
    Column("errors", JSON),
)
github_events = Table(
    "github_events",
    metadata,
    Column("delivery_id", String),
    Column("installation_id", String),
    Column("organization_id", String),
    Column("event_type", String),
    Column("payload", JSON),
    Column("received_at", DateTime(timezone=True)),
)
pack_revisions = Table(
    "pack_revisions", metadata,
    Column("id", String), Column("organization_id", String),
    Column("repository", String), Column("tag", String), Column("commit_sha", String),
)
pack_activations = Table(
    "pack_activations", metadata,
    Column("organization_id", String), Column("repository", String), Column("revision_id", String),
)
pack_catalog = Table(
    "pack_catalog", metadata,
    Column("revision_id", String), Column("kind", String), Column("manifest", JSON),
    Column("controls", JSON), Column("capabilities", JSON),
)
evidence_records = Table(
    "evidence_records", metadata,
    Column("id", String), Column("organization_id", String), Column("product_id", String),
    Column("subject_id", String), Column("capability", String), Column("environment", String),
    Column("target_revision", String), Column("collector_revision", String),
    Column("collector_image", String), Column("provenance", JSON), Column("value", JSON),
    Column("observed_at", DateTime(timezone=True)), Column("expires_at", DateTime(timezone=True)),
    Column("ttl_seconds", Integer),
)
rule_evaluations = Table(
    "rule_evaluations", metadata,
    Column("id", String), Column("organization_id", String), Column("product_id", String),
    Column("subject_id", String), Column("environment", String), Column("target_revision", String),
    Column("control_id", String), Column("governance_revision", String), Column("scan_id", Integer),
    Column("status", String), Column("reason", String), Column("evidence_ids", JSON),
    Column("control", JSON), Column("subject", JSON), Column("evaluated_at", DateTime(timezone=True)),
)
