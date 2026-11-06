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
