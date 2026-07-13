"""add api audit table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-12 12:00:02.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_audit",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("consumer_id", sa.BigInteger(), nullable=True),
        sa.Column("consumer_name", sa.String(length=64), nullable=True),
        sa.Column("consumer_perms", sa.JSON(), nullable=True),
        sa.Column("required_perm", sa.String(length=64), nullable=True),
        sa.Column("method", sa.String(length=8), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("error", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["consumer_id"], ["api_consumers.id"]),
        sa.Index("ix_api_audit_timestamp", "timestamp"),
        sa.Index("ix_api_audit_request_id", "request_id"),
        sa.Index("ix_api_audit_consumer_id", "consumer_id"),
    )


def downgrade() -> None:
    op.drop_table("api_audit")
