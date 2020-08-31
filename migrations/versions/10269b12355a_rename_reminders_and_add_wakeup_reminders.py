"""rename_reminders_and_add_wakeup_reminders

Revision ID: 10269b12355a
Revises: cb71584de89d
Create Date: 2020-08-29 15:40:59.127242

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "10269b12355a"
down_revision = "cb71584de89d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bedtime_reminders",
        sa.Column("job_id", sa.VARCHAR(length=191), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["apscheduler_jobs.id"], onupdate="CASCADE", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"
        ),
    )
    op.create_table(
        "wakeup_reminders",
        sa.Column("job_id", sa.VARCHAR(length=191), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["apscheduler_jobs.id"], onupdate="CASCADE", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"
        ),
    )

    op.execute(
        "INSERT INTO bedtime_reminders (job_id, user_id, created_at, updated_at) "
        "SELECT job_id, user_id, created_at, updated_at FROM reminders"
    )

    op.drop_table("reminders")
    op.drop_column("users", "first_name")
    op.drop_column("users", "last_name")


def downgrade():
    op.add_column(
        "users",
        sa.Column("last_name", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("first_name", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    op.create_table(
        "reminders",
        sa.Column(
            "job_id", sa.VARCHAR(length=191), autoincrement=False, nullable=False
        ),
        sa.Column("user_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["apscheduler_jobs.id"],
            name="reminders_job_id_fkey",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="reminders_user_id_fkey",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )

    op.execute(
        "INSERT INTO reminders (job_id, user_id, created_at, updated_at) "
        "SELECT job_id, user_id, created_at, updated_at FROM bedtime_reminders"
    )

    op.drop_table("wakeup_reminders")
    op.drop_table("bedtime_reminders")
