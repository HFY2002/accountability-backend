"""Add proof expiry and enhanced verification status

Revision ID: add_proof_expiry_and_status
Revises: f9eaa8128b38
Create Date: 2025-11-29 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_proof_expiry_and_status'
down_revision = 'f9eaa8128b38'
branch_labels = None
depends_on = None

def upgrade():
    # Add verification_expires_at column to proofs table
    op.add_column('proofs', sa.Column('verification_expires_at', sa.DateTime(timezone=True), nullable=True))
    
    # Update the proof_status enum to include 'expired'
    op.execute("ALTER TYPE proofstatus ADD VALUE IF NOT EXISTS 'expired'")
    
    # Update the notification_type enum to include 'proof_expired'
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'proof_expired'")

def downgrade():
    # Remove verification_expires_at column
    op.drop_column('proofs', 'verification_expires_at')
    
    # Note: Downgrading enums is complex and usually not needed
    # We'll skip removing the enum values as they don't hurt anything
    pass