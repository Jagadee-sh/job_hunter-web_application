"""Create initial JobHunter AI schema."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    jsonb = postgresql.JSONB()
    op.create_table("users", sa.Column("id", uuid, primary_key=True), sa.Column("email", sa.String(320), nullable=False, unique=True), sa.Column("full_name", sa.String(200), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("profiles", sa.Column("id", uuid, primary_key=True), sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True), sa.Column("target_roles", jsonb, nullable=False), sa.Column("locations", jsonb, nullable=False), sa.Column("skills", jsonb, nullable=False), sa.Column("preferred_companies", jsonb, nullable=False), sa.Column("years_experience", sa.Integer(), nullable=False))
    op.create_table("jobs", sa.Column("id", uuid, primary_key=True), sa.Column("external_id", sa.String(255), nullable=False), sa.Column("source", sa.String(80), nullable=False), sa.Column("title", sa.String(500), nullable=False), sa.Column("company", sa.String(255), nullable=False), sa.Column("location", sa.String(500), nullable=False), sa.Column("salary", sa.String(255)), sa.Column("description", sa.Text(), nullable=False), sa.Column("application_url", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("source", "external_id"))
    op.create_table("job_scores", sa.Column("id", uuid, primary_key=True), sa.Column("job_id", uuid, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("score", sa.Float(), nullable=False), sa.Column("rationale", sa.Text(), nullable=False), sa.Column("skill_gaps", jsonb, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    for table in ("applications", "application_answers", "generated_documents", "audit_logs", "agent_runs"):
        op.create_table(table, sa.Column("id", uuid, primary_key=True), sa.Column("payload", jsonb, nullable=False, server_default="{}"))


def downgrade() -> None:
    for table in ("agent_runs", "audit_logs", "generated_documents", "application_answers", "applications", "job_scores", "jobs", "profiles", "users"):
        op.drop_table(table)
