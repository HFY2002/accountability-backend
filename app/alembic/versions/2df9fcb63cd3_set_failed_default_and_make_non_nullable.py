"""set_failed_default_and_make_non_nullable

Revision ID: 2df9fcb63cd3
Revises: 3e66992cff5a
Create Date: 2026-01-01 04:23:14.332279

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2df9fcb63cd3'
down_revision: Union[str, Sequence[str], None] = '3e66992cff5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Set all NULL failed values to False for existing milestones
    op.execute("UPDATE milestones SET failed = FALSE WHERE failed IS NULL")
    
    # Alter the column to be non-nullable with a default of False
    op.alter_column('milestones', 'failed',
                    existing_type=sa.Boolean(),
                    nullable=False,
                    server_default=sa.text('false'))


def downgrade() -> None:
    """Downgrade schema."""
    # Revert the column to nullable without server default
    op.alter_column('milestones', 'failed',
                    existing_type=sa.Boolean(),
                    nullable=True,
                    server_default=None)
