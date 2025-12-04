"""remove_category_system

Revision ID: 2f38cd0d5501
Revises: add_proof_expiry_and_status
Create Date: 2025-12-04 10:58:28.260038

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f38cd0d5501'
down_revision: Union[str, Sequence[str], None] = 'add_proof_expiry_and_status'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove category system from database."""
    # Drop foreign key constraints
    op.drop_constraint('goals_category_id_fkey', 'goals', type_='foreignkey')
    op.drop_constraint('goal_templates_category_id_fkey', 'goal_templates', type_='foreignkey')
    
    # Drop columns
    op.drop_column('goals', 'category_id')
    op.drop_column('goal_templates', 'category_id')
    
    # Drop goal_categories table
    op.drop_table('goal_categories')


def downgrade() -> None:
    """Restore category system to database."""
    # Recreate goal_categories table
    op.create_table(
        'goal_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('emoji', sa.String(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug')
    )
    
    # Restore columns
    op.add_column('goals', sa.Column('category_id', sa.Integer(), nullable=True))
    op.add_column('goal_templates', sa.Column('category_id', sa.Integer(), nullable=False))
    
    # Restore foreign key constraints
    op.create_foreign_key('goals_category_id_fkey', 'goals', 'goal_categories', ['category_id'], ['id'])
    op.create_foreign_key('goal_templates_category_id_fkey', 'goal_templates', 'goal_categories', ['category_id'], ['id'])
