"""remove_is_public_column_from_notes

Revision ID: aef6ce5e012e
Revises: 35d4f677b5dc
Create Date: 2025-09-14 15:24:02.618781

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aef6ce5e012e'
down_revision = '35d4f677b5dc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove the is_public column from the notes table
    op.drop_column('notes', 'is_public')


def downgrade() -> None:
    # Add back the is_public column to the notes table
    op.add_column('notes', sa.Column('is_public', sa.Boolean(), nullable=True))
