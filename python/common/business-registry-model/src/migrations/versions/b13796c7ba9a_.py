"""empty message

Revision ID: b13796c7ba9a
Revises: 60d9c14c2b7f
Create Date: 2023-07-13 23:03:01.394887

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b13796c7ba9a'
down_revision = '60d9c14c2b7f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('sent_to_gazette')
    with op.batch_alter_table('consent_continuation_outs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('filing_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('legal_entities_id', sa.Integer(), nullable=True))
        batch_op.drop_index('ix_consent_continuation_outs_change_filing_id')
        batch_op.create_unique_constraint(None, ['id'])
        batch_op.drop_constraint('consent_continuation_outs_change_filing_id_fkey', type_='foreignkey')
        batch_op.drop_constraint('consent_continuation_outs_legal_entity_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(None, 'filings', ['filing_id'], ['id'])
        batch_op.create_foreign_key(None, 'legal_entities', ['legal_entities_id'], ['id'])
        batch_op.drop_column('change_filing_id')
        batch_op.drop_column('legal_entity_id')

    with op.batch_alter_table('party_roles', schema=None) as batch_op:
        batch_op.drop_constraint('party_roles_change_filing_id_fkey', type_='foreignkey')
        batch_op.drop_column('change_filing_id')

    with op.batch_alter_table('party_roles_history', schema=None) as batch_op:
        batch_op.drop_constraint('party_roles_history_change_filing_id_fkey', type_='foreignkey')
        batch_op.drop_column('change_filing_id')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('party_roles_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('change_filing_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.create_foreign_key('party_roles_history_change_filing_id_fkey', 'filings', ['change_filing_id'], ['id'])

    with op.batch_alter_table('party_roles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('change_filing_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.create_foreign_key('party_roles_change_filing_id_fkey', 'filings', ['change_filing_id'], ['id'])

    with op.batch_alter_table('consent_continuation_outs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('legal_entity_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('change_filing_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key('consent_continuation_outs_legal_entity_id_fkey', 'legal_entities', ['legal_entity_id'], ['id'])
        batch_op.create_foreign_key('consent_continuation_outs_change_filing_id_fkey', 'filings', ['change_filing_id'], ['id'])
        batch_op.drop_constraint(None, type_='unique')
        batch_op.create_index('ix_consent_continuation_outs_change_filing_id', ['change_filing_id'], unique=False)
        batch_op.drop_column('legal_entities_id')
        batch_op.drop_column('filing_id')

    op.create_table('sent_to_gazette',
    sa.Column('filing_id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('identifier', sa.VARCHAR(length=10), autoincrement=False, nullable=False),
    sa.Column('sent_to_gazette_date', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('filing_id', name='sent_to_gazette_pkey')
    )
    # ### end Alembic commands ###
