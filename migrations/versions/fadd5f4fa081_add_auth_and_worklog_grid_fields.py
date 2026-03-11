"""add auth and worklog grid fields

Revision ID: fadd5f4fa081
Revises: 
Create Date: 2026-03-06 05:06:46.928429

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fadd5f4fa081'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'user' not in inspector.get_table_names():
        op.create_table(
            'user',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(length=120), nullable=False),
            sa.Column('full_name', sa.String(length=120), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('user', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_user_email'), ['email'], unique=True)

    work_cols = {col['name']: col for col in inspector.get_columns('work_log')}
    index_names = {index['name'] for index in inspector.get_indexes('work_log')}
    fk_names = {fk.get('name') for fk in inspector.get_foreign_keys('work_log')}

    add_manager_user_id = 'manager_user_id' not in work_cols
    add_work_category = 'work_category' not in work_cols
    add_team_name = 'team_name' not in work_cols
    make_project_nullable = 'project_id' in work_cols and (work_cols['project_id'].get('nullable') is False)
    add_manager_index = 'ix_work_log_manager_user_id' not in index_names
    add_manager_fk = 'fk_work_log_manager_user_id_user' not in fk_names

    if any(
        [
            add_manager_user_id,
            add_work_category,
            add_team_name,
            make_project_nullable,
            add_manager_index,
            add_manager_fk,
        ]
    ):
        with op.batch_alter_table('work_log', schema=None) as batch_op:
            if add_manager_user_id:
                batch_op.add_column(sa.Column('manager_user_id', sa.Integer(), nullable=True))
            if add_work_category:
                batch_op.add_column(
                    sa.Column('work_category', sa.String(length=20), nullable=False, server_default='Project')
                )
            if add_team_name:
                batch_op.add_column(sa.Column('team_name', sa.String(length=120), nullable=True))
            if make_project_nullable:
                batch_op.alter_column('project_id', existing_type=sa.INTEGER(), nullable=True)
            if add_manager_index:
                batch_op.create_index(batch_op.f('ix_work_log_manager_user_id'), ['manager_user_id'], unique=False)
            if add_manager_fk:
                batch_op.create_foreign_key(
                    'fk_work_log_manager_user_id_user',
                    'user',
                    ['manager_user_id'],
                    ['id'],
                )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    work_cols = {col['name']: col for col in inspector.get_columns('work_log')}
    index_names = {index['name'] for index in inspector.get_indexes('work_log')}
    fk_names = {fk.get('name') for fk in inspector.get_foreign_keys('work_log')}

    drop_manager_fk = 'fk_work_log_manager_user_id_user' in fk_names
    drop_manager_index = 'ix_work_log_manager_user_id' in index_names
    make_project_non_nullable = 'project_id' in work_cols and (work_cols['project_id'].get('nullable') is True)
    drop_team_name = 'team_name' in work_cols
    drop_work_category = 'work_category' in work_cols
    drop_manager_user_id = 'manager_user_id' in work_cols

    if any(
        [
            drop_manager_fk,
            drop_manager_index,
            make_project_non_nullable,
            drop_team_name,
            drop_work_category,
            drop_manager_user_id,
        ]
    ):
        with op.batch_alter_table('work_log', schema=None) as batch_op:
            if drop_manager_fk:
                batch_op.drop_constraint('fk_work_log_manager_user_id_user', type_='foreignkey')
            if drop_manager_index:
                batch_op.drop_index(batch_op.f('ix_work_log_manager_user_id'))
            if make_project_non_nullable:
                batch_op.alter_column('project_id', existing_type=sa.INTEGER(), nullable=False)
            if drop_team_name:
                batch_op.drop_column('team_name')
            if drop_work_category:
                batch_op.drop_column('work_category')
            if drop_manager_user_id:
                batch_op.drop_column('manager_user_id')

    if 'user' in inspector.get_table_names():
        with op.batch_alter_table('user', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_user_email'))
        op.drop_table('user')
