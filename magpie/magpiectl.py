#!/usr/bin/env python
# coding: utf-8

"""
Magpie is a service for AuthN and AuthZ based on Ziggurat-Foundations
"""

# -- Project specific --------------------------------------------------------
from magpie.common import print_log, str2bool
from magpie.constants import get_constant
from magpie.helpers.register_default_users import register_default_users
from magpie.register import (
    magpie_register_services_from_config,
    magpie_register_permissions_from_config,
)
from magpie.security import auth_config_from_settings
from magpie import db, constants

# -- Standard library --------------------------------------------------------
# noinspection PyUnresolvedReferences
import logging
import logging.config   # find config in 'logging.ini'
LOGGER = logging.getLogger(__name__)


# noinspection PyUnusedLocal
def main(global_config=None, **settings):
    """
    This function returns a Pyramid WSGI application.
    """
    settings['magpie.root'] = constants.MAGPIE_ROOT
    settings['magpie.module'] = constants.MAGPIE_MODULE_DIR

    print_log('Setting up loggers...')
    log_lvl = get_constant('MAGPIE_LOG_LEVEL', settings, 'magpie.log_level', default_value='INFO',
                           raise_missing=False, raise_not_set=False, print_missing=True)
    LOGGER.setLevel(log_lvl)
    sa_settings = db.set_sqlalchemy_log_level(log_lvl)

    print_log('Looking for db migration requirement...')
    db.run_database_migration_when_ready(settings)  # cannot pass db session as it might not even exist yet!

    # HACK:
    #   migration can cause sqlalchemy engine to reset its internal logger level, although it is properly set
    #   to 'echo=False' because engines are re-created as needed... (ie: missing db)
    #   apply configs to re-enforce the logging level of `sqlalchemy.engine.base.Engine`"""
    db.set_sqlalchemy_log_level(log_lvl)
    # fetch db session here, otherwise, any following db engine connection will re-initialize
    # with a new engine class and logging settings don't get re-evaluated/applied
    db_session = db.get_db_session_from_config_ini(constants.MAGPIE_INI_FILE_PATH, settings_override=sa_settings)

    print_log('Register default users...')
    register_default_users(db_session=db_session)

    print_log('Register configuration providers...', LOGGER)
    push_phoenix = str2bool(get_constant('PHOENIX_PUSH', settings=settings, settings_name='magpie.phoenix_push',
                                         raise_missing=False, raise_not_set=False, print_missing=True))
    magpie_register_services_from_config(constants.MAGPIE_PROVIDERS_CONFIG_PATH, push_to_phoenix=push_phoenix,
                                         force_update=True, disable_getcapabilities=False, db_session=db_session)

    print_log('Register configuration permissions...', LOGGER)
    magpie_register_permissions_from_config(constants.MAGPIE_PERMISSIONS_CONFIG_PATH, db_session=db_session)

    print_log('Running configurations setup...')
    magpie_url_template = 'http://{hostname}:{port}'
    port = get_constant('MAGPIE_PORT', settings=settings, settings_name='magpie.port')
    if port:
        settings['magpie.port'] = port
    hostname = get_constant('HOSTNAME')
    if hostname:
        settings['magpie.url'] = magpie_url_template.format(hostname=hostname, port=settings['magpie.port'])

    # avoid cornice conflicting with magpie exception views
    settings['handle_exceptions'] = False

    config = auth_config_from_settings(settings)
    config.include('magpie')
    # Don't use scan otherwise modules like 'magpie.adapter' are
    # automatically found and cause import errors on missing packages
    # config.scan('magpie')
    config.set_default_permission(get_constant('MAGPIE_ADMIN_PERMISSION'))

    print_log('Starting Magpie app...')
    wsgi_app = config.make_wsgi_app()
    return wsgi_app


if __name__ == '__main__':
    main()
