"""reorder members table columns for logical grouping

Revision ID: 32ff5bc60920
Revises: 12c509b3fd8c
Create Date: 2026-01-25 23:09:41.669759

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "32ff5bc60920"
down_revision: Union[str, None] = "12c509b3fd8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reorder columns for logical grouping
    # MySQL supports MODIFY COLUMN with AFTER clause

    # Move nickname after discord_id (Identity group)
    op.execute(
        """
        ALTER TABLE members
        MODIFY COLUMN nickname VARCHAR(12) NOT NULL
        AFTER discord_id
    """
    )

    # Move active after nickname (Status group starts)
    op.execute(
        """
        ALTER TABLE members
        MODIFY COLUMN active TINYINT(1) NOT NULL DEFAULT 1
        AFTER nickname
    """
    )

    # Move role after active (Status group)
    op.execute(
        """
        ALTER TABLE members
        MODIFY COLUMN role ENUM(
            'BANNED', 'GUEST', 'APPLICANT', 'PROSPECT', 'MEMBER',
            'BOOSTER', 'BLACKLISTED', 'MODERATOR', 'STAFF',
            'BRIGADIER', 'ADMIRAL', 'LEADERSHIP', 'MARSHAL', 'OWNER'
        ) NOT NULL DEFAULT 'GUEST'
        AFTER active
    """
    )

    # Move rank after role (Status group)
    op.execute(
        """
        ALTER TABLE members
        MODIFY COLUMN rank ENUM(
            'GOD_ZAMORAK', 'GOD_GUTHIX', 'GOD_SARADOMIN', 'GOD',
            'MYTH', 'LEGEND', 'DRAGON', 'RUNE', 'ADAMANT', 'MITHRIL', 'IRON'
        ) NOT NULL
        AFTER role
    """
    )

    # Move ingots after rank (Metadata group starts)
    op.execute(
        """
        ALTER TABLE members
        MODIFY COLUMN ingots BIGINT NOT NULL DEFAULT 0
        AFTER rank
    """
    )

    # joined_date and last_changed_date are already in correct position


def downgrade() -> None:
    # Reverse the order back to original

    # Move active back before nickname
    op.execute(
        """
        ALTER TABLE members
        MODIFY COLUMN active TINYINT(1) NOT NULL DEFAULT 1
        AFTER discord_id
    """
    )

    # Move nickname back after active
    op.execute(
        """
        ALTER TABLE members
        MODIFY COLUMN nickname VARCHAR(12) NOT NULL
        AFTER active
    """
    )

    # Move ingots back before rank
    op.execute(
        """
        ALTER TABLE members
        MODIFY COLUMN ingots BIGINT NOT NULL DEFAULT 0
        AFTER nickname
    """
    )

    # Move rank back before role
    op.execute(
        """
        ALTER TABLE members
        MODIFY COLUMN rank ENUM(
            'GOD_ZAMORAK', 'GOD_GUTHIX', 'GOD_SARADOMIN', 'GOD',
            'MYTH', 'LEGEND', 'DRAGON', 'RUNE', 'ADAMANT', 'MITHRIL', 'IRON'
        ) NOT NULL
        AFTER ingots
    """
    )

    # Move role back after rank (last position before dates)
    op.execute(
        """
        ALTER TABLE members
        MODIFY COLUMN role ENUM(
            'BANNED', 'GUEST', 'APPLICANT', 'PROSPECT', 'MEMBER',
            'BOOSTER', 'BLACKLISTED', 'MODERATOR', 'STAFF',
            'BRIGADIER', 'ADMIRAL', 'LEADERSHIP', 'MARSHAL', 'OWNER'
        ) NOT NULL DEFAULT 'GUEST'
        AFTER rank
    """
    )
