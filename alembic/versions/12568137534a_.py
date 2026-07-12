"""empty message

Revision ID: 12568137534a
Revises: 8797e836629f, c3d4e5f6a7b8
Create Date: 2026-07-12 12:06:11.888240

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "12568137534a"
down_revision: Union[str, None] = ("8797e836629f", "c3d4e5f6a7b8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
