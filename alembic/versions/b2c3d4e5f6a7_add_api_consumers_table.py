"""add api consumers table

Revision ID: b2c3d4e5f6a7
Revises: ff14108b4c64
Create Date: 2026-07-12 12:00:01.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "ff14108b4c64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_consumers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), unique=True, nullable=False),
        sa.Column("token_hash", sa.String(length=128), unique=True, nullable=False),
        sa.Column("perms", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("api_consumers")
