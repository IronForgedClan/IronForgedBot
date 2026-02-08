"""add member boolean flags

Revision ID: 8797e836629f
Revises: 32ff5bc60920
Create Date: 2026-01-30 21:19:47.416255

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8797e836629f"
down_revision: Union[str, None] = "32ff5bc60920"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_booster", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("is_prospect", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "is_blacklisted", sa.Boolean(), nullable=False, server_default="0"
            )
        )
        batch_op.add_column(
            sa.Column("is_banned", sa.Boolean(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.drop_column("is_banned")
        batch_op.drop_column("is_blacklisted")
        batch_op.drop_column("is_prospect")
        batch_op.drop_column("is_booster")
