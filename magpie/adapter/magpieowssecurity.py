from magpie.api.api_except import evaluate_call, verify_param
from magpie.constants import get_constant
from magpie.definitions.pyramid_definitions import (
    HTTPOk,
    HTTPNotFound,
    HTTPForbidden,
    IAuthenticationPolicy,
    IAuthorizationPolicy,
    asbool,
)
# noinspection PyUnresolvedReferences
from magpie.definitions.twitcher_definitions import (
    OWSSecurityInterface,
    OWSAccessForbidden,
    parse_service_name,
    get_twitcher_configuration,
    TWITCHER_CONFIGURATION_DEFAULT,
)
from magpie.models import Service
from magpie.services import service_factory
from magpie.utils import get_magpie_url, get_logger, CONTENT_TYPE_JSON
from requests.cookies import RequestsCookieJar
from six.moves.urllib.parse import urlparse
import requests
LOGGER = get_logger("TWITCHER")


class MagpieOWSSecurity(OWSSecurityInterface):

    def __init__(self, registry):
        super(MagpieOWSSecurity, self).__init__()
        self.magpie_url = get_magpie_url(registry)
        self.twitcher_ssl_verify = asbool(registry.settings.get('twitcher.ows_proxy_ssl_verify', True))
        self.twitcher_protected_path = registry.settings.get('twitcher.ows_proxy_protected_path', '/ows')

    def check_request(self, request):
        if request.path.startswith(self.twitcher_protected_path):
            service_name = parse_service_name(request.path, self.twitcher_protected_path)
            service = evaluate_call(lambda: Service.by_service_name(service_name, db_session=request.db),
                                    fallback=lambda: request.db.rollback(),
                                    httpError=HTTPForbidden, msgOnFail="Service query by name refused by db.")
            verify_param(service, notNone=True, httpError=HTTPNotFound, msgOnFail="Service name not found in db.")

            # return a specific type of service, ex: ServiceWPS with all the acl (loaded according to the service_type)
            service_specific = service_factory(service, request)
            # should contain all the acl, this the only thing important
            # parse request (GET/POST) to get the permission requested for that service
            permission_requested = service_specific.permission_requested()

            if permission_requested:
                self.update_request_cookies(request)
                authn_policy = request.registry.queryUtility(IAuthenticationPolicy)
                authz_policy = request.registry.queryUtility(IAuthorizationPolicy)
                principals = authn_policy.effective_principals(request)
                has_permission = authz_policy.permits(service_specific, principals, permission_requested)
                if not has_permission:
                    raise OWSAccessForbidden("Not authorized to access this resource. " +
                                             "User does not meet required permissions.")

    def update_request_cookies(self, request):
        """
        Ensure login of the user and update the request cookies if Twitcher is in a special configuration.
        Only update if `MAGPIE_COOKIE_NAME` is missing and is retrievable from `access_token` in `Authorization` header.
        Counter-validate the login procedure by calling Magpie's `/session` which should indicated a logged user.
        """
        token_name = get_constant('MAGPIE_COOKIE_NAME', settings_name=request.registry.settings)
        not_default = get_twitcher_configuration(request.registry.settings) != TWITCHER_CONFIGURATION_DEFAULT
        if not_default and 'Authorization' in request.headers and token_name not in request.cookies:
            magpie_prov = request.params.get('provider', 'WSO2')
            magpie_auth = '{host}/providers/{provider}/signin'.format(host=self.magpie_url, provider=magpie_prov)
            headers = dict(request.headers)
            headers.update({'Homepage-Route': '/session', 'Accept': CONTENT_TYPE_JSON})
            session_resp = requests.get(magpie_auth, headers=headers, verify=self.twitcher_ssl_verify)
            if session_resp.status_code != HTTPOk.code:
                raise OWSAccessForbidden("Not authorized to access this resource. " +
                                         "Provider login failed with following reason: [{}]."
                                         .format(session_resp.reason))

            # use specific domain to differentiate between `.{hostname}` and `{hostname}` variations if applicable
            # noinspection PyProtectedMember
            request_cookies = session_resp.request._cookies
            magpie_cookies = list(filter(lambda cookie: cookie.name == token_name, request_cookies))
            magpie_domain = urlparse(self.magpie_url).hostname if len(magpie_cookies) > 1 else None
            session_cookies = RequestsCookieJar.get(request_cookies, token_name, domain=magpie_domain)
            if not session_resp.json().get('authenticated') or not session_cookies:
                raise OWSAccessForbidden("Not authorized to access this resource. " +
                                         "Session authentication could not be verified.")
            request.cookies.update({token_name: session_cookies})
