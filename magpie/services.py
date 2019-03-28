from magpie.constants import get_constant
from magpie.definitions.ziggurat_definitions import UserService, ResourceService, permission_to_pyramid_acls
from magpie.definitions.pyramid_definitions import (
    EVERYONE,
    ALLOW,
    HTTPNotFound,
    HTTPBadRequest,
    HTTPNotImplemented,
    HTTPInternalServerError,
)
from magpie.api import api_except as ax
from magpie.owsrequest import ows_parser_factory
from magpie import models, permissions as p
from typing import TYPE_CHECKING
from six import with_metaclass
if TYPE_CHECKING:
    from magpie.definitions.typedefs import Str, List, Dict, Union  # noqa: F401
    from magpie.definitions.pyramid_definitions import Request  # noqa: F401
    ResourcePermissionType = Union[models.GroupPermission, models.UserPermission]


class ServiceMeta(type):
    @property
    def resource_types(cls):
        # type: (...) -> List[Str]
        """Allowed resources types under the service."""
        return list(cls.resource_types_permissions.keys())

    @property
    def child_resource_allowed(cls):
        # type: (...) -> bool
        return len(cls.resource_types) > 0


class ServiceI(with_metaclass(ServiceMeta)):
    # required request parameters for the service
    params_expected = []                # type: List[Str]
    # global permissions allowed for the service (top-level resource)
    permission_names = []               # type: List[Str]
    # dict of list for each corresponding allowed resource permissions (children resources)
    resource_types_permissions = {}     # type: Dict[Str, List[Str]]

    def __init__(self, service, request):
        self.service = service
        self.request = request
        self.acl = []
        self.parser = ows_parser_factory(request)
        self.parser.parse(self.params_expected)

    @property
    def __acl__(self):
        raise NotImplementedError

    def expand_acl(self, resource, user):
        # type: (models.Resource, models.User) -> None
        if resource:
            for ace in resource.__acl__:
                self.acl.append(ace)

            if user:
                permissions = ResourceService.perms_for_user(resource, user, db_session=self.request.db)
                for outcome, perm_user, perm_name in permission_to_pyramid_acls(permissions):
                    self.acl.append((outcome, perm_user, perm_name,))
            else:
                user = UserService.by_user_name(get_constant('MAGPIE_ANONYMOUS_USER'), db_session=self.request.db)
                if user is None:
                    raise Exception('No Anonymous user in the database')
                else:
                    permissions = ResourceService.perms_for_user(resource, user, db_session=self.request.db)
                    for outcome, perm_user, perm_name in permission_to_pyramid_acls(permissions):
                        self.acl.append((outcome, EVERYONE, perm_name,))

    def permission_requested(self):
        # type: (...) -> Str
        try:
            return self.parser.params[u'request']
        except Exception as e:
            # if 'ServiceI', 'params_expected' is empty and will raise a KeyError
            raise NotImplementedError("Exception: [" + repr(e) + "]")

    def effective_permissions(self, resource, user):
        # type: (models.Resource, models.User) -> List[ResourcePermissionType]
        """
        Recursively rewind the resource tree from the specified resource up to the topmost parent service resource
        and retrieve permissions along the way that should be applied to children when using resource inheritance.
        """
        resource_effective_perms = list()
        while resource is not None:
            current_resource_perms = ResourceService.perms_for_user(resource, user, db_session=self.request.db)
            resource_effective_perms.extend(current_resource_perms)
            if resource.parent_id:
                resource = ResourceService.by_resource_id(resource.parent_id, db_session=self.request.db)
            else:
                resource = None
        return resource_effective_perms


class ServiceWPS(ServiceI):

    permission_names = [
        p.PERMISSION_GET_CAPABILITIES,
        p.PERMISSION_DESCRIBE_PROCESS,
        p.PERMISSION_EXECUTE,
    ]

    params_expected = [
        u'service',
        u'request',
        u'version'
    ]

    resource_types_permissions = {}

    def __init__(self, service, request):
        super(ServiceWPS, self).__init__(service, request)

    @property
    def __acl__(self):
        self.expand_acl(self.service, self.request.user)
        return self.acl


class ServiceWMS(ServiceI):
    permission_names = [
        p.PERMISSION_GET_CAPABILITIES,
        p.PERMISSION_GET_MAP,
        p.PERMISSION_GET_FEATURE_INFO,
        p.PERMISSION_GET_LEGEND_GRAPHIC,
        p.PERMISSION_GET_METADATA,
    ]

    params_expected = [
        u'service',
        u'request',
        u'version',
        u'layers',
        u'layername',
        u'dataset'
    ]

    resource_types_permissions = {
        models.Workspace.resource_type_name: [
            p.PERMISSION_GET_CAPABILITIES,
            p.PERMISSION_GET_MAP,
            p.PERMISSION_GET_FEATURE_INFO,
            p.PERMISSION_GET_LEGEND_GRAPHIC,
            p.PERMISSION_GET_METADATA,
        ]
    }

    def __init__(self, service, request):
        super(ServiceWMS, self).__init__(service, request)

    @property
    def __acl__(self):
        raise NotImplementedError


class ServiceNCWMS2(ServiceWMS):

    resource_types_permissions = {
        models.File.resource_type_name: [
            p.PERMISSION_GET_CAPABILITIES,
            p.PERMISSION_GET_MAP,
            p.PERMISSION_GET_FEATURE_INFO,
            p.PERMISSION_GET_LEGEND_GRAPHIC,
            p.PERMISSION_GET_METADATA,
        ],
        models.Directory.resource_type_name: [
            p.PERMISSION_GET_CAPABILITIES,
            p.PERMISSION_GET_MAP,
            p.PERMISSION_GET_FEATURE_INFO,
            p.PERMISSION_GET_LEGEND_GRAPHIC,
            p.PERMISSION_GET_METADATA,
        ]
    }

    def __init__(self, service, request):
        super(ServiceNCWMS2, self).__init__(service, request)

    @property
    def __acl__(self):
        self.expand_acl(self.service, self.request.user)

        # According to the permission, the resource we want to authorize is not formatted the same way
        permission_requested = self.permission_requested()
        netcdf_file = None
        if permission_requested == p.PERMISSION_GET_CAPABILITIES:
            # https://colibri.crim.ca/twitcher/ows/proxy/ncWMS2/wms?SERVICE=WMS&REQUEST=GetCapabilities&
            #   VERSION=1.3.0&DATASET=outputs/ouranos/subdaily/aet/pcp/aet_pcp_1961.nc
            if 'dataset' in self.parser.params.keys():
                netcdf_file = self.parser.params['dataset']

        elif permission_requested == p.PERMISSION_GET_MAP:
            # https://colibri.crim.ca/ncWMS2/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&FORMAT=image%2Fpng&
            #   TRANSPARENT=TRUE&ABOVEMAXCOLOR=extend&STYLES=default-scalar%2Fseq-Blues&
            #   LAYERS=outputs/ouranos/subdaily/aet/pcp/aet_pcp_1961.nc/PCP&EPSG=4326
            netcdf_file = self.parser.params['layers']
            if netcdf_file:
                netcdf_file = netcdf_file.rsplit('/', 1)[0]

        elif permission_requested == p.PERMISSION_GET_METADATA:
            # https://colibri.crim.ca/ncWMS2/wms?request=GetMetadata&item=layerDetails&
            #   layerName=outputs/ouranos/subdaily/aet/pcp/aet_pcp_1961.nc/PCP
            netcdf_file = self.parser.params['layername']
            if netcdf_file:
                netcdf_file = netcdf_file.rsplit('/', 1)[0]

        else:
            return [(ALLOW, EVERYONE, permission_requested,)]

        if netcdf_file:
            ax.verify_param('outputs/', paramCompare=netcdf_file, httpError=HTTPNotFound,
                            msgOnFail='outputs/ is not in path', notIn=True)
            netcdf_file = netcdf_file.replace('outputs/', 'birdhouse/')

            db_session = self.request.db
            path_elems = netcdf_file.split('/')
            new_child = self.service
            while new_child and path_elems:
                elem_name = path_elems.pop(0)
                new_child = models.find_children_by_name(
                    elem_name, parent_id=new_child.resource_id, db_session=db_session
                )
                self.expand_acl(new_child, self.request.user)

        return self.acl


class ServiceGeoserver(ServiceWMS):

    def __init__(self, service, request):
        super(ServiceGeoserver, self).__init__(service, request)

    @property
    def __acl__(self):
        self.expand_acl(self.service, self.request.user)

        # localhost:8087/geoserver/WATERSHED/wms?layers=WATERSHED:BV_1NS&request=getmap
        # localhost:8087/geoserver/wms?layers=WATERERSHED:BV1_NS&request=getmap
        # those two request lead to the same thing so, here we need to check the workspace in the layer

        # localhost:8087/geoserver/wms?request=getcapabilities (dangerous, get all workspace)
        # localhost:8087/geoserver/WATERSHED/wms?request=getcapabilities (only for the workspace in the path)
        # here we need to check the workspace in the path

        request_type = self.permission_requested()
        if request_type == p.PERMISSION_GET_CAPABILITIES:
            path_elem = self.request.path.split('/')
            wms_idx = path_elem.index('wms')
            if path_elem[wms_idx - 1] != 'geoserver':
                workspace_name = path_elem[wms_idx - 1]
            else:
                workspace_name = ''
        else:
            layer_name = self.parser.params['layers']
            workspace_name = layer_name.split(':')[0]

        # load workspace resource from the database
        workspace = models.find_children_by_name(child_name=workspace_name,
                                                 parent_id=self.service.resource_id,
                                                 db_session=self.request.db)
        if workspace:
            self.expand_acl(workspace, self.request.user)
        return self.acl


class ServiceAccess(ServiceI):
    permission_names = [p.PERMISSION_ACCESS]
    params_expected = []
    resource_types_permissions = {}

    def __init__(self, service, request):
        super(ServiceAccess, self).__init__(service, request)

    @property
    def __acl__(self):
        self.expand_acl(self.service, self.request.user)
        return self.acl

    def permission_requested(self):
        return p.PERMISSION_ACCESS


class ServiceAPI(ServiceI):
    permission_names = models.Route.permission_names

    params_expected = []

    resource_types_permissions = {
        models.Route.resource_type_name: models.Route.permission_names
    }

    def __init__(self, service, request):
        super(ServiceAPI, self).__init__(service, request)

    @property
    def __acl__(self):
        return self.route_acl()

    def route_acl(self, sub_api_route=None):
        self.expand_acl(self.service, self.request.user)

        match_index = 0
        route_parts = self.request.path.split('/')
        route_api_base = self.service.resource_name if sub_api_route is None else sub_api_route

        if self.service.resource_name in route_parts and route_api_base in route_parts:
            api_idx = route_parts.index(route_api_base)
            # keep only parts after api base route to process it
            if len(route_parts) - 1 > api_idx:
                route_parts = route_parts[api_idx + 1::]
                route_child = self.service

                # process read/write inheritance permission access
                while route_child and route_parts:
                    part_name = route_parts.pop(0)
                    route_res_id = route_child.resource_id
                    route_child = models.find_children_by_name(part_name, parent_id=route_res_id,
                                                               db_session=self.request.db)
                    match_index = len(self.acl)
                    self.expand_acl(route_child, self.request.user)

        # process read/write-match specific permission access
        # (convert exact route 'match' to read/write counterparts only if matching last item's permissions)
        for i in range(match_index, len(self.acl)):
            if self.acl[i][2] == p.PERMISSION_READ_MATCH:
                self.acl[i] = (self.acl[i][0], self.acl[i][1], p.PERMISSION_READ)
            if self.acl[i][2] == p.PERMISSION_WRITE_MATCH:
                self.acl[i] = (self.acl[i][0], self.acl[i][1], p.PERMISSION_WRITE)

        return self.acl

    def permission_requested(self):
        # only read/write are used for 'real' access control, 'match' permissions must be updated accordingly
        if self.request.method.upper() in ['GET', 'HEAD']:
            return p.PERMISSION_READ
        return p.PERMISSION_WRITE

    def effective_permissions(self, resource, user):
        # if 'match' permissions are on the specified 'resource', keep them
        # otherwise, keep only the non 'match' variations from inherited parent resources permissions
        resource_effective_perms = super(ServiceAPI, self).effective_permissions(resource, user)
        return filter(lambda perm:
                      (perm.perm_name in [p.PERMISSION_READ, p.PERMISSION_WRITE]) or
                      (perm.perm_name in [p.PERMISSION_READ_MATCH, p.PERMISSION_WRITE_MATCH] and
                       perm.resource.resource_id == resource.resource_id),
                      resource_effective_perms)


class ServiceWFS(ServiceI):

    permission_names = [
        p.PERMISSION_GET_CAPABILITIES,
        p.PERMISSION_DESCRIBE_FEATURE_TYPE,
        p.PERMISSION_GET_FEATURE,
        p.PERMISSION_LOCK_FEATURE,
        p.PERMISSION_TRANSACTION,
    ]

    params_expected = [
        u'service',
        u'request',
        u'version',
        u'typenames'
    ]

    resource_types_permissions = {}

    def __init__(self, service, request):
        super(ServiceWFS, self).__init__(service, request)

    @property
    def __acl__(self):
        self.expand_acl(self.service, self.request.user)
        request_type = self.permission_requested()
        if request_type == p.PERMISSION_GET_CAPABILITIES:
            path_elem = self.request.path.split('/')
            wms_idx = path_elem.index('wfs')
            if path_elem[wms_idx - 1] != 'geoserver':
                workspace_name = path_elem[wms_idx - 1]
            else:
                workspace_name = ''
        else:
            layer_name = self.parser.params['typenames']
            workspace_name = layer_name.split(':')[0]

        # load workspace resource from the database
        workspace = models.find_children_by_name(child_name=workspace_name,
                                                 parent_id=self.service.resource_id,
                                                 db_session=self.request.db)
        if workspace:
            self.expand_acl(workspace, self.request.user)
        return self.acl


class ServiceTHREDDS(ServiceI):

    permission_names = [
        p.PERMISSION_READ,
        p.PERMISSION_WRITE,
    ]

    params_expected = [
        u'request'
    ]

    resource_types_permissions = {
        models.Directory.resource_type_name: permission_names,
        models.File.resource_type_name: permission_names,
    }

    def __init__(self, service, request):
        super(ServiceTHREDDS, self).__init__(service, request)

    @property
    def __acl__(self):
        self.expand_acl(self.service, self.request.user)
        elems = self.request.path.split('/')

        if 'fileServer' in elems:
            first_idx = elems.index('fileServer')
        elif 'dodsC' in elems:
            first_idx = elems.index('dodsC')
            elems[-1] = elems[-1].replace('.html', '')
        elif 'catalog' in elems:
            first_idx = elems.index('catalog')
        elif elems[-1] == 'catalog.html':
            first_idx = elems.index(self.service.resource_name) - 1
        else:
            return self.acl

        elems = elems[first_idx + 1::]
        new_child = self.service
        while new_child and elems:
            elem_name = elems.pop(0)
            if ".nc" in elem_name:
                elem_name = elem_name.split(".nc")[0] + ".nc"  # in case there is more extension to discard such as .dds
            parent_id = new_child.resource_id
            new_child = models.find_children_by_name(elem_name, parent_id=parent_id, db_session=self.request.db)
            self.expand_acl(new_child, self.request.user)

        return self.acl

    def permission_requested(self):
        return u'read'


service_type_dict = {
    u'access':          ServiceAccess,      # noqa: E241
    u'api':             ServiceAPI,         # noqa: E241
    u'geoserverwms':    ServiceGeoserver,   # noqa: E241
    u'ncwms':           ServiceNCWMS2,      # noqa: E241
    u'thredds':         ServiceTHREDDS,     # noqa: E241
    u'wfs':             ServiceWFS,         # noqa: E241
    u'wps':             ServiceWPS,         # noqa: E241
}


def service_factory(service, request):
    # type: (models.Service, Request) -> ServiceI
    """Retrieve the specific service class from the provided database service entry."""
    ax.verify_param(service, paramCompare=models.Service, ofType=True,
                    httpError=HTTPBadRequest, content={u'service': repr(service)},
                    msgOnFail="Cannot process invalid service object")
    service_type = ax.evaluate_call(lambda: service.type, httpError=HTTPInternalServerError,
                                    msgOnFail="Cannot retrieve service type from object")
    ax.verify_param(service_type, isIn=True, paramCompare=service_type_dict.keys(),
                    httpError=HTTPNotImplemented, content={u'service_type': service_type},
                    msgOnFail="Undefined service type mapping to service object")
    return ax.evaluate_call(lambda: service_type_dict[service_type](service, request),
                            httpError=HTTPInternalServerError,
                            msgOnFail="Failed to find requested service type.")


def get_all_service_permission_names():
    all_permission_names_list = set()
    for service_type in service_type_dict.keys():
        all_permission_names_list.update(service_type_dict[service_type].permission_names)
    return all_permission_names_list
