"""
project-api route resource.

Revision ID: c352a98d570e
Revises: a395ef9d3fe6
Create Date: 2018-06-20 13:31:55.666240
"""
import os
import sys
cur_file = os.path.abspath(__file__)
root_dir = os.path.dirname(cur_file)    # version
root_dir = os.path.dirname(root_dir)    # alembic
root_dir = os.path.dirname(root_dir)    # magpie
root_dir = os.path.dirname(root_dir)    # root
sys.path.insert(0, root_dir)

# noinspection PyUnresolvedReferences
from magpie.definitions.alembic_definitions import get_context, op              # noqa: F401
from magpie.definitions.sqlalchemy_definitions import PGDialect, sessionmaker   # noqa: F401
from magpie import models                                                       # noqa: F401

# revision identifiers, used by Alembic.
revision = 'c352a98d570e'
down_revision = 'a395ef9d3fe6'
branch_labels = None
depends_on = None

Session = sessionmaker()


def change_project_api_resource_type(new_type_name):
    context = get_context()
    if isinstance(context.connection.engine.dialect, PGDialect):
        # obtain service 'project-api'
        session = Session(bind=op.get_bind())
        project_api_svc_id = session.query(models.Service.resource_id).filter_by(resource_name='project-api').first()

        # nothing to edit if it doesn't exist, otherwise change resource types name
        if project_api_svc_id:
            columns = models.Resource.resource_type, models.Resource.root_service_id
            session.query(columns)\
                .filter(models.Resource.root_service_id == project_api_svc_id)\
                .update({models.Resource.resource_type: new_type_name})
            session.commit()


def upgrade():
    change_project_api_resource_type('route')


def downgrade():
    change_project_api_resource_type('directory')
