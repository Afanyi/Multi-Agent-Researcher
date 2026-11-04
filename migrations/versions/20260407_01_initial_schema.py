"""Initial schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260407_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("research_runs"):
        op.create_table(
            "research_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("keywords", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("depth", sa.Integer(), nullable=False, server_default="6"),
            sa.Column("domain_allowlist", postgresql.ARRAY(sa.Text()), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        )

    if not inspector.has_table("sources"):
        op.create_table(
            "sources",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("title", sa.Text(), nullable=True),
            sa.Column("domain", sa.String(length=255), nullable=True),
            sa.Column("rank_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="fetched"),
            sa.Column("content_text", sa.Text(), nullable=True),
            sa.Column("content_hash", sa.String(length=64), nullable=True),
            sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"], ondelete="CASCADE"),
        )

    if not inspector.has_table("evidence_chunks"):
        op.create_table(
            "evidence_chunks",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("heading", sa.Text(), nullable=True),
            sa.Column("snippet", sa.Text(), nullable=False),
            sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        )

    if not inspector.has_table("reports"):
        op.create_table(
            "reports",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("report_md", sa.Text(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("coverage", sa.Float(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("run_id"),
        )

    if not inspector.has_table("traces"):
        op.create_table(
            "traces",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("agent", sa.String(length=32), nullable=False),
            sa.Column("event_type", sa.String(length=16), nullable=False),
            sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"], ondelete="CASCADE"),
        )


def downgrade() -> None:
    op.drop_table("traces")
    op.drop_table("reports")
    op.drop_table("evidence_chunks")
    op.drop_table("sources")
    op.drop_table("research_runs")
