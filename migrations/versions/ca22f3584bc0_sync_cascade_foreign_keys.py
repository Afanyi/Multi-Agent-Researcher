"""Sync cascade foreign keys for existing databases."""

from alembic import op


revision = "ca22f3584bc0"
down_revision = "20260407_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("evidence_chunks_source_id_fkey"), "evidence_chunks", type_="foreignkey")
    op.create_foreign_key(
        None,
        "evidence_chunks",
        "sources",
        ["source_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(op.f("reports_run_id_fkey"), "reports", type_="foreignkey")
    op.create_foreign_key(None, "reports", "research_runs", ["run_id"], ["id"], ondelete="CASCADE")
    op.drop_constraint(op.f("sources_run_id_fkey"), "sources", type_="foreignkey")
    op.create_foreign_key(None, "sources", "research_runs", ["run_id"], ["id"], ondelete="CASCADE")
    op.drop_constraint(op.f("traces_run_id_fkey"), "traces", type_="foreignkey")
    op.create_foreign_key(None, "traces", "research_runs", ["run_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint(None, "traces", type_="foreignkey")
    op.create_foreign_key(op.f("traces_run_id_fkey"), "traces", "research_runs", ["run_id"], ["id"])
    op.drop_constraint(None, "sources", type_="foreignkey")
    op.create_foreign_key(op.f("sources_run_id_fkey"), "sources", "research_runs", ["run_id"], ["id"])
    op.drop_constraint(None, "reports", type_="foreignkey")
    op.create_foreign_key(op.f("reports_run_id_fkey"), "reports", "research_runs", ["run_id"], ["id"])
    op.drop_constraint(None, "evidence_chunks", type_="foreignkey")
    op.create_foreign_key(op.f("evidence_chunks_source_id_fkey"), "evidence_chunks", "sources", ["source_id"], ["id"])
