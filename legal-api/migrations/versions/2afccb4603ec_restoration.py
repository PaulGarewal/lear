"""restoration

Revision ID: 2afccb4603ec
Revises: d087a6ee9230
Create Date: 2023-01-25 13:16:21.914920

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2afccb4603ec'
down_revision = 'd087a6ee9230'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('businesses', sa.Column('restoration_expiry_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('businesses_version', sa.Column('restoration_expiry_date', sa.DateTime(timezone=True), autoincrement=False, nullable=True))
    op.add_column('filings', sa.Column('filing_sub_type', sa.String(length=30), nullable=True))
    op.add_column('filings', sa.Column('approval_type', sa.String(length=15), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('filings', 'approval_type')
    op.drop_column('filings', 'filing_sub_type')
    op.drop_column('businesses_version', 'restoration_expiry_date')
    op.drop_column('businesses', 'restoration_expiry_date')
    # ### end Alembic commands ###
