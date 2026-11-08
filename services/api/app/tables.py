from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
)

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
agent_credentials = Table(
    "agent_credentials", metadata,
    Column("id", String), Column("agent_id", String), Column("token_hash", String),
    Column("expires_at", DateTime(timezone=True)), Column("revoked_at", DateTime(timezone=True)),
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
pack_approvals = Table(
    "pack_approvals", metadata,
    Column("revision_id", String), Column("organization_id", String), Column("repository", String),
    Column("approved_by", String), Column("approved_at", DateTime(timezone=True)),
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
assessment_snapshots = Table(
    "assessment_snapshots", metadata,
    Column("id", String), Column("organization_id", String), Column("product_id", String),
    Column("binding_id", String), Column("context", String), Column("pull_request_number", Integer),
    Column("environment", String), Column("git_sha", String), Column("pack_sha", String),
    Column("evaluation_ids", JSON), Column("evidence_ids", JSON), Column("counts", JSON),
    Column("evaluations", JSON), Column("created_at", DateTime(timezone=True)),
)
findings = Table(
    "findings", metadata,
    Column("id", String), Column("fingerprint", String), Column("organization_id", String),
    Column("product_id", String), Column("binding_id", String), Column("context", String),
    Column("pull_request_number", Integer), Column("environment", String), Column("subject_id", String),
    Column("control_id", String), Column("status", String), Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)), Column("last_snapshot_id", String),
)
finding_history = Table(
    "finding_history", metadata,
    Column("id", String), Column("finding_id", String), Column("snapshot_id", String),
    Column("evaluation_id", String), Column("outcome", String), Column("state_after", String),
    Column("reason", String), Column("observed_at", DateTime(timezone=True)),
)
assessment_jobs = Table(
    "assessment_jobs", metadata,
    Column("id", String), Column("organization_id", String), Column("product_id", String),
    Column("binding_id", String), Column("delivery_id", String), Column("pull_request_id", BigInteger),
    Column("pull_request_number", Integer), Column("head_sha", String), Column("status", String),
    Column("created_at", DateTime(timezone=True)), Column("attempts", Integer),
    Column("lease_token", String), Column("lease_until", DateTime(timezone=True)),
    Column("last_error", String), Column("result_snapshot_id", String),
    Column("comment_processed_at", DateTime(timezone=True)), Column("comment_retry_at", DateTime(timezone=True)),
    Column("check_processed_at", DateTime(timezone=True)), Column("check_retry_at", DateTime(timezone=True)),
    Column("check_valid_until", DateTime(timezone=True)),
)
