"""
normalize constraint and key names correct keys for pre 0.5.6 naming convention.

Revision ID: 438c27ec1c9
Revises: 439766f6104d
Create Date: 2015-06-13 21:16:32.358778
"""
from __future__ import unicode_literals

import os
import sys
cur_file = os.path.abspath(__file__)
root_dir = os.path.dirname(cur_file)    # version
root_dir = os.path.dirname(root_dir)    # alembic
root_dir = os.path.dirname(root_dir)    # magpie
root_dir = os.path.dirname(root_dir)    # root
sys.path.insert(0, root_dir)

# noinspection PyUnresolvedReferences
from magpie.definitions.alembic_definitions import op, get_context              # noqa: F401
from magpie.definitions.sqlalchemy_definitions import PGDialect, Inspector      # noqa: F401

# revision identifiers, used by Alembic.
revision = '438c27ec1c9'
down_revision = '439766f6104d'

# correct keys for pre 0.5.6 naming convention


def upgrade():
    context = get_context()
    insp = Inspector.from_engine(context.connection.engine)
    # existing migration
    # pre naming convention keys
    groups_permissions_pkey = 'groups_permissions_pkey'
    groups_pkey = 'groups_pkey'
    groups_resources_permissions_pkey = 'groups_resources_permissions_pkey'
    users_groups_pkey = 'users_groups_pkey'
    users_permissions_pkey = 'users_permissions_pkey'
    users_resources_permissions_pkey = 'users_resources_permissions_pkey'

    if isinstance(context.connection.engine.dialect, PGDialect):
        op.execute(
            'ALTER INDEX groups_unique_group_name_key RENAME to ix_groups_uq_group_name_key')

        op.drop_constraint('groups_permissions_perm_name_check',
                           'groups_permissions')
        op.execute('''
        ALTER TABLE groups_permissions
            ADD CONSTRAINT ck_groups_permissions_perm_name CHECK (perm_name::text = lower(perm_name::text));
        ''')

        op.drop_constraint('groups_resources_permissions_perm_name_check',
                           'groups_resources_permissions')
        op.execute('''
        ALTER TABLE groups_resources_permissions
              ADD CONSTRAINT ck_groups_resources_permissions_perm_name CHECK (perm_name::text = lower(perm_name::text));
        ''')

        op.drop_constraint('user_permissions_perm_name_check',
                           'users_permissions')
        op.execute('''
        ALTER TABLE users_permissions
          ADD CONSTRAINT ck_user_permissions_perm_name CHECK (perm_name::text = lower(perm_name::text));
        ''')

        op.drop_constraint('users_resources_permissions_perm_name_check',
                           'users_resources_permissions')
        op.execute('''
        ALTER TABLE users_resources_permissions
          ADD CONSTRAINT ck_users_resources_permissions_perm_name CHECK (perm_name::text = lower(perm_name::text));
        ''')

        op.execute(
            'ALTER INDEX users_email_key2 RENAME to ix_users_uq_lower_email')

        op.execute(
            'ALTER INDEX users_username_uq2 RENAME to ix_users_ux_lower_username')

        if groups_permissions_pkey == \
                insp.get_pk_constraint('groups_permissions')['name']:
            op.execute(
                'ALTER INDEX groups_permissions_pkey RENAME to pk_groups_permissions')

        if groups_pkey == insp.get_pk_constraint('groups')['name']:
            op.execute('ALTER INDEX groups_pkey RENAME to pk_groups')

        if groups_resources_permissions_pkey == \
                insp.get_pk_constraint('groups_resources_permissions')['name']:
            op.execute(
                'ALTER INDEX groups_resources_permissions_pkey RENAME to pk_groups_resources_permissions')

        if users_groups_pkey == insp.get_pk_constraint('users_groups')['name']:
            op.execute(
                'ALTER INDEX users_groups_pkey RENAME to pk_users_groups')

        if users_permissions_pkey == \
                insp.get_pk_constraint('users_permissions')['name']:
            op.execute(
                'ALTER INDEX users_permissions_pkey RENAME to pk_users_permissions')

        if users_resources_permissions_pkey == \
                insp.get_pk_constraint('users_resources_permissions')['name']:
            op.execute(
                'ALTER INDEX users_resources_permissions_pkey RENAME to pk_users_resources_permissions')

        if 'external_identities_pkey' == \
                insp.get_pk_constraint('external_identities')['name']:
            op.execute(
                'ALTER INDEX external_identities_pkey RENAME to pk_external_identities')

        if 'external_identities_local_user_name_fkey' in [
                c['name'] for c in insp.get_foreign_keys('external_identities')]:
            op.drop_constraint('external_identities_local_user_name_fkey',
                               'external_identities', type_='foreignkey')
            op.create_foreign_key(None, 'external_identities', 'users',
                                  remote_cols=['user_name'],
                                  local_cols=['local_user_name'],
                                  onupdate='CASCADE',
                                  ondelete='CASCADE')

        if 'groups_permissions_group_id_fkey' in [
                c['name'] for c in insp.get_foreign_keys('groups_permissions')]:
            op.drop_constraint('groups_permissions_group_id_fkey',
                               'groups_permissions', type_='foreignkey')
            op.create_foreign_key(None, 'groups_permissions', 'groups',
                                  remote_cols=['id'],
                                  local_cols=['group_id'], onupdate='CASCADE',
                                  ondelete='CASCADE')

        if 'groups_group_name_key' in [c['name'] for c in
                                       insp.get_unique_constraints('groups')]:
            op.execute(
                'ALTER INDEX groups_group_name_key RENAME to uq_groups_group_name')

        if 'groups_resources_permissions_group_id_fkey' in [
                c['name'] for c in insp.get_foreign_keys('groups_resources_permissions')]:
            op.drop_constraint('groups_resources_permissions_group_id_fkey',
                               'groups_resources_permissions',
                               type_='foreignkey')
            op.create_foreign_key(None, 'groups_resources_permissions',
                                  'groups', remote_cols=['id'],
                                  local_cols=['group_id'], onupdate='CASCADE',
                                  ondelete='CASCADE')

        if 'groups_resources_permissions_resource_id_fkey' in [
                c['name'] for c in insp.get_foreign_keys('groups_resources_permissions')]:
            op.drop_constraint('groups_resources_permissions_resource_id_fkey',
                               'groups_resources_permissions',
                               type_='foreignkey')
            op.create_foreign_key(None, 'groups_resources_permissions',
                                  'resources', remote_cols=['resource_id'],
                                  local_cols=['resource_id'],
                                  onupdate='CASCADE',
                                  ondelete='CASCADE')

        if 'resources_pkey' == insp.get_pk_constraint('resources')['name']:
            op.execute('ALTER INDEX resources_pkey RENAME to pk_resources')

        if 'resources_owner_group_id_fkey' in [
                c['name'] for c in insp.get_foreign_keys('resources')]:
            op.drop_constraint('resources_owner_group_id_fkey', 'resources',
                               type_='foreignkey')
            op.create_foreign_key(None, 'resources', 'groups',
                                  remote_cols=['id'],
                                  local_cols=['owner_group_id'],
                                  onupdate='CASCADE',
                                  ondelete='SET NULL')

        if 'resources_owner_user_id_fkey' in [
                c['name'] for c in insp.get_foreign_keys('resources')]:
            op.drop_constraint('resources_owner_user_id_fkey', 'resources',
                               type_='foreignkey')
            op.create_foreign_key(None, 'resources', 'users',
                                  remote_cols=['id'],
                                  local_cols=['owner_user_id'],
                                  onupdate='CASCADE',
                                  ondelete='SET NULL')

        if 'resources_parent_id_fkey' in [
                c['name'] for c in insp.get_foreign_keys('resources')]:
            op.drop_constraint('resources_parent_id_fkey', 'resources',
                               type_='foreignkey')
            op.create_foreign_key(None, 'resources', 'resources',
                                  remote_cols=['resource_id'],
                                  local_cols=['parent_id'], onupdate='CASCADE',
                                  ondelete='SET NULL')

        if 'users_pkey' == insp.get_pk_constraint('users')['name']:
            op.execute('ALTER INDEX users_pkey RENAME to pk_users')

        if 'users_email_key' in [
                c['name'] for c in insp.get_unique_constraints('users')]:
            op.execute('ALTER INDEX users_email_key RENAME to uq_users_email')

        if 'users_user_name_key' in [
                c['name'] for c in insp.get_unique_constraints('users')]:
            op.execute(
                'ALTER INDEX users_user_name_key RENAME to uq_users_user_name')

        if 'users_groups_group_id_fkey' in [
                c['name'] for c in insp.get_foreign_keys('users_groups')]:
            op.drop_constraint('users_groups_group_id_fkey', 'users_groups',
                               type_='foreignkey')
            op.create_foreign_key(None, 'users_groups', 'groups',
                                  remote_cols=['id'],
                                  local_cols=['group_id'], onupdate='CASCADE',
                                  ondelete='CASCADE')

        if 'users_groups_user_id_fkey' in [
                c['name'] for c in insp.get_foreign_keys('users_groups')]:
            op.drop_constraint('users_groups_user_id_fkey', 'users_groups',
                               type_='foreignkey')
            op.create_foreign_key(None, 'users_groups', 'users',
                                  remote_cols=['id'],
                                  local_cols=['user_id'], onupdate='CASCADE',
                                  ondelete='CASCADE')

        if 'users_permissions_user_id_fkey' in [
                c['name'] for c in insp.get_foreign_keys('users_permissions')]:
            op.drop_constraint('users_permissions_user_id_fkey',
                               'users_permissions', type_='foreignkey')
            op.create_foreign_key(None, 'users_permissions', 'users',
                                  remote_cols=['id'],
                                  local_cols=['user_id'], onupdate='CASCADE',
                                  ondelete='CASCADE')

        if 'users_resources_permissions_resource_id_fkey' in [
                c['name'] for c in insp.get_foreign_keys('users_resources_permissions')]:
            op.drop_constraint('users_resources_permissions_resource_id_fkey',
                               'users_resources_permissions',
                               type_='foreignkey')
            op.create_foreign_key(None, 'users_resources_permissions',
                                  'resources', remote_cols=['resource_id'],
                                  local_cols=['resource_id'],
                                  onupdate='CASCADE',
                                  ondelete='CASCADE')

        if 'users_resources_permissions_user_id_fkey' in [
                c['name'] for c in insp.get_foreign_keys('users_resources_permissions')]:
            op.drop_constraint('users_resources_permissions_user_id_fkey',
                               'users_resources_permissions',
                               type_='foreignkey')
            op.create_foreign_key(None, 'users_resources_permissions', 'users',
                                  remote_cols=['id'],
                                  local_cols=['user_id'], onupdate='CASCADE',
                                  ondelete='CASCADE')


def downgrade():
    pass
