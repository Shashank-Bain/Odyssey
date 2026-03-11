"""add coe economics and governance

Revision ID: 2c7b6f3e9b11
Revises: fadd5f4fa081
Create Date: 2026-03-09 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2c7b6f3e9b11"
down_revision = "fadd5f4fa081"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "team" not in tables:
        op.create_table(
            "team",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
        with op.batch_alter_table("team", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_team_name"), ["name"], unique=True)
            batch_op.create_index(batch_op.f("ix_team_owner_user_id"), ["owner_user_id"], unique=False)

    if "team_membership" not in tables:
        op.create_table(
            "team_membership",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("team_member_id", sa.Integer(), nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
            sa.ForeignKeyConstraint(["team_member_id"], ["team_member.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("team_membership", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_team_membership_team_member_id"), ["team_member_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_team_membership_team_id"), ["team_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_team_membership_start_date"), ["start_date"], unique=False)
            batch_op.create_index(batch_op.f("ix_team_membership_end_date"), ["end_date"], unique=False)

    project_cols = {col["name"]: col for col in inspector.get_columns("project")}
    project_indexes = {idx["name"] for idx in inspector.get_indexes("project")}
    project_fks = {fk.get("name") for fk in inspector.get_foreign_keys("project")}
    if "team_id" not in project_cols or "ix_project_team_id" not in project_indexes or "fk_project_team_id_team" not in project_fks:
        with op.batch_alter_table("project", schema=None) as batch_op:
            if "team_id" not in project_cols:
                batch_op.add_column(sa.Column("team_id", sa.Integer(), nullable=True))
            if "ix_project_team_id" not in project_indexes:
                batch_op.create_index(batch_op.f("ix_project_team_id"), ["team_id"], unique=False)
            if "fk_project_team_id_team" not in project_fks:
                batch_op.create_foreign_key("fk_project_team_id_team", "team", ["team_id"], ["id"])

    if "project_day_billing" not in tables:
        op.create_table(
            "project_day_billing",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("work_date", sa.Date(), nullable=False),
            sa.Column("billable_fte", sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column("billing_manager_name", sa.String(length=120), nullable=True),
            sa.Column("billing_manager_user_id", sa.Integer(), nullable=True),
            sa.Column("override_daily_revenue", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["billing_manager_user_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "work_date", name="uq_project_day_billing"),
        )
        with op.batch_alter_table("project_day_billing", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_project_day_billing_project_id"), ["project_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_project_day_billing_work_date"), ["work_date"], unique=False)

    if "cost_rate" not in tables:
        op.create_table(
            "cost_rate",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("level_key", sa.String(length=80), nullable=False),
            sa.Column("cost_per_day", sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column("effective_start_date", sa.Date(), nullable=True),
            sa.Column("effective_end_date", sa.Date(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("level_key"),
        )
        with op.batch_alter_table("cost_rate", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_cost_rate_level_key"), ["level_key"], unique=True)

    if "client_billing_rate" not in tables:
        op.create_table(
            "client_billing_rate",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("region", sa.String(length=30), nullable=False),
            sa.Column("cadence", sa.String(length=20), nullable=False),
            sa.Column("fte_point", sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("region", "cadence", "fte_point", name="uq_client_billing_rate"),
        )
        with op.batch_alter_table("client_billing_rate", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_client_billing_rate_region"), ["region"], unique=False)
            batch_op.create_index(batch_op.f("ix_client_billing_rate_cadence"), ["cadence"], unique=False)

    if "non_client_billing_config" not in tables:
        op.create_table(
            "non_client_billing_config",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("base_daily_rate_for_4_5", sa.Numeric(precision=12, scale=2), nullable=False, server_default="1080"),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "non_client_billing_config" in tables:
        op.drop_table("non_client_billing_config")

    if "client_billing_rate" in tables:
        with op.batch_alter_table("client_billing_rate", schema=None) as batch_op:
            if "ix_client_billing_rate_region" in {idx["name"] for idx in inspector.get_indexes("client_billing_rate")}:
                batch_op.drop_index(batch_op.f("ix_client_billing_rate_region"))
            if "ix_client_billing_rate_cadence" in {idx["name"] for idx in inspector.get_indexes("client_billing_rate")}:
                batch_op.drop_index(batch_op.f("ix_client_billing_rate_cadence"))
        op.drop_table("client_billing_rate")

    if "cost_rate" in tables:
        with op.batch_alter_table("cost_rate", schema=None) as batch_op:
            if "ix_cost_rate_level_key" in {idx["name"] for idx in inspector.get_indexes("cost_rate")}:
                batch_op.drop_index(batch_op.f("ix_cost_rate_level_key"))
        op.drop_table("cost_rate")

    if "project_day_billing" in tables:
        with op.batch_alter_table("project_day_billing", schema=None) as batch_op:
            idxs = {idx["name"] for idx in inspector.get_indexes("project_day_billing")}
            if "ix_project_day_billing_project_id" in idxs:
                batch_op.drop_index(batch_op.f("ix_project_day_billing_project_id"))
            if "ix_project_day_billing_work_date" in idxs:
                batch_op.drop_index(batch_op.f("ix_project_day_billing_work_date"))
        op.drop_table("project_day_billing")

    project_cols = {col["name"]: col for col in inspector.get_columns("project")}
    project_indexes = {idx["name"] for idx in inspector.get_indexes("project")}
    project_fks = {fk.get("name") for fk in inspector.get_foreign_keys("project")}
    if "team_id" in project_cols or "ix_project_team_id" in project_indexes or "fk_project_team_id_team" in project_fks:
        with op.batch_alter_table("project", schema=None) as batch_op:
            if "fk_project_team_id_team" in project_fks:
                batch_op.drop_constraint("fk_project_team_id_team", type_="foreignkey")
            if "ix_project_team_id" in project_indexes:
                batch_op.drop_index(batch_op.f("ix_project_team_id"))
            if "team_id" in project_cols:
                batch_op.drop_column("team_id")

    if "team_membership" in tables:
        with op.batch_alter_table("team_membership", schema=None) as batch_op:
            idxs = {idx["name"] for idx in inspector.get_indexes("team_membership")}
            for idx_name in [
                "ix_team_membership_team_member_id",
                "ix_team_membership_team_id",
                "ix_team_membership_start_date",
                "ix_team_membership_end_date",
            ]:
                if idx_name in idxs:
                    batch_op.drop_index(idx_name)
        op.drop_table("team_membership")

    if "team" in tables:
        with op.batch_alter_table("team", schema=None) as batch_op:
            idxs = {idx["name"] for idx in inspector.get_indexes("team")}
            if "ix_team_name" in idxs:
                batch_op.drop_index(batch_op.f("ix_team_name"))
            if "ix_team_owner_user_id" in idxs:
                batch_op.drop_index(batch_op.f("ix_team_owner_user_id"))
        op.drop_table("team")
