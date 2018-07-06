from pyramid.httpexceptions import *
from sys import exc_info
import types

# control variables to avoid infinite recursion in case of
# major programming error to avoid application hanging
RAISE_RECURSIVE_SAFEGUARD_MAX = 5
RAISE_RECURSIVE_SAFEGUARD_COUNT = 0


def verify_param(param, paramCompare=None, httpError=HTTPNotAcceptable, httpKWArgs=None, msgOnFail="",
                 content=None, contentType='application/json',
                 notNone=False, notEmpty=False, notIn=False, notEqual=False,
                 isNone=False,  isEmpty=False,  isIn=False,  isEqual=False, ofType=None,
                 withParam=True, paramName=None):
    """
    Evaluate various parameter combinations given the requested flags.
    Given a failing verification, directly raises the specified `httpError`.
    Invalid exceptions generated by this verification process are treated as `HTTPInternalServerError`.
    Exceptions are generated using the standard output method.

    :param param: (bool) parameter value to evaluate
    :param paramName: (str) name of the tested parameter returned in response if specified for debugging purposes
    :param paramCompare:
        other value(s) to test against, can be an iterable (single value resolved as iterable unless None)
        to test for None type, use `isNone`/`notNone` flags instead or `paramCompare`=[None]
    :param httpError: (HTTPError) derived exception to raise on test failure (default: `HTTPNotAcceptable`)
    :param httpKWArgs: (dict) additional keyword arguments to pass to `httpError` if called in case of HTTP exception
    :param msgOnFail: (str) message details to return in HTTP exception if flag condition failed
    :param content: json formatted additional content to provide in case of exception
    :param contentType: format in which to return the exception ('application/json', 'text/html' or 'text/plain')
    :param notNone: (bool) test that `param` is None type
    :param notEmpty: (bool) test that `param` is an empty string
    :param notIn: (bool) test that `param` does not exist in `paramCompare` values
    :param notEqual: (bool) test that `param` is not equal to `paramCompare` value
    :param isNone: (bool) test that `param` is None type
    :param isEmpty: (bool) test `param` for an empty string
    :param isIn: (bool) test that `param` exists in `paramCompare` values
    :param isEqual: (bool) test that `param` equals `paramCompare` value
    :param ofType: (type) test that `param` is of same type as specified type by `ofType` (except NoneType)
    :param withParam: (bool) adds values of `param` and `paramCompare` as applicable to json on raise (default: True)
    :raises `HTTPError`: if tests fail, specified exception is raised (default: `HTTPNotAcceptable`)
    :raises `HTTPInternalServerError`: for evaluation error
    :return: nothing if all tests passed
    """
    content = {} if content is None else content

    # precondition evaluation of input parameters
    try:
        if type(notNone) is not bool:
            raise Exception("`notNone` is not a `bool`")
        if type(notEmpty) is not bool:
            raise Exception("`notEmpty` is not a `bool`")
        if type(notIn) is not bool:
            raise Exception("`notIn` is not a `bool`")
        if type(notEqual) is not bool:
            raise Exception("`notEqual` is not a `bool`")
        if type(isNone) is not bool:
            raise Exception("`isNone` is not a `bool`")
        if type(isEmpty) is not bool:
            raise Exception("`isEmpty` is not a `bool`")
        if type(isIn) is not bool:
            raise Exception("`isIn` is not a `bool`")
        if type(isEqual) is not bool:
            raise Exception("`isEqual` is not a `bool`")
        if paramCompare is None and (isIn or notIn or isEqual or notEqual):
            raise Exception("`paramCompare` cannot be `None` with specified test flags")
        if type(param) != type(paramCompare) and (isEqual or notEqual):
            raise Exception("`paramCompare` cannot be of different type with specified test flags")
        if not hasattr(paramCompare, '__iter__') and (isIn or notIn):
            paramCompare = [paramCompare]
    except Exception as e:
        content[u'traceback'] = repr(exc_info())
        content[u'exception'] = repr(e)
        raise_http(httpError=HTTPInternalServerError, httpKWArgs=httpKWArgs,
                   content=content, contentType=contentType,
                   detail="Error occurred during parameter verification")

    # evaluate requested parameter combinations
    status = False
    if notNone:
        status = status or (param is None)
    if isNone:
        status = status or (param is not None)
    if notEmpty:
        status = status or (param == "")
    if isEmpty:
        status = status or (param != "")
    if notIn:
        status = status or (param in paramCompare)
    if isIn:
        status = status or (param not in paramCompare)
    if notEqual:
        status = status or (param == paramCompare)
    if isEqual:
        status = status or (param != paramCompare)
    if ofType is not None:
        status = status or (not type(param) == ofType)
    if status:
        if withParam:
            content[u'param'] = {u'value': str(param) if type(param) in types.StringTypes else repr(param)}
            if paramName is not None:
                content[u'param'][u'name'] = str(paramName)
            if paramCompare is not None:
                content[u'param'][u'compare'] = repr(paramCompare)
        raise_http(httpError, httpKWArgs=httpKWArgs, detail=msgOnFail, content=content, contentType=contentType)


def evaluate_call(call, fallback=None, httpError=HTTPInternalServerError, httpKWArgs=None, msgOnFail="",
                  content=None, contentType='application/json'):
    """
    Evaluates the specified `call` with a wrapped HTTP exception handling.
    On failure, tries to call `fallback` if specified, and finally raises the specified `httpError`.
    Any potential error generated by `fallback` or `httpError` themselves are treated as `HTTPInternalServerError`.
    Exceptions are generated using the standard output method formatted based on the specified `contentType`.

    Example:
        normal call::

            try:
                res = func(args)
            except Exception as e:
                fb_func()
                raise HTTPExcept(e.message)

        wrapped call::

            res = evaluate_call(lambda: func(args), fallback=lambda: fb_func(), httpError=HTTPExcept, msgOnFail="...")


    :param call: function to call, *MUST* be specified as `lambda: <function_call>`
    :param fallback: function to call (if any) when `call` failed, *MUST* be `lambda: <function_call>`
    :param httpError: (HTTPError) alternative exception to raise on `call` failure
    :param httpKWArgs: (dict) additional keyword arguments to pass to `httpError` if called in case of HTTP exception
    :param msgOnFail: (str) message details to return in HTTP exception if `call` failed
    :param content: json formatted additional content to provide in case of exception
    :param contentType: format in which to return the exception ('application/json', 'text/html' or 'text/plain')
    :raises httpError: on `call` failure
    :raises `HTTPInternalServerError`: on `fallback` failure
    :return: whichever return value `call` might have if no exception occurred
    """
    msgOnFail = repr(msgOnFail) if type(msgOnFail) is not str else msgOnFail
    if not islambda(call):
        raise_http(httpError=HTTPInternalServerError, httpKWArgs=httpKWArgs,
                   detail="Input `call` is not a lambda expression",
                   content={u'call': {u'detail': msgOnFail, u'content': repr(content)}},
                   contentType=contentType)

    # preemptively check fallback to avoid possible call exception without valid recovery
    if fallback is not None:
        if not islambda(fallback):
            raise_http(httpError=HTTPInternalServerError, httpKWArgs=httpKWArgs,
                       detail="Input `fallback`  is not a lambda expression, not attempting `call`",
                       content={u'call': {u'detail': msgOnFail, u'content': repr(content)}},
                       contentType=contentType)
    try:
        return call()
    except Exception as e:
        ce = repr(e)
    try:
        if fallback is not None:
            fallback()
    except Exception as e:
        fe = repr(e)
        raise_http(httpError=HTTPInternalServerError, httpKWArgs=httpKWArgs,
                   detail="Exception occurred during `fallback` called after failing `call` exception",
                   content={u'call': {u'exception': ce, u'detail': msgOnFail, u'content': repr(content)},
                            u'fallback': {u'exception': fe}},
                   contentType=contentType)
    raise_http(httpError, detail=msgOnFail, httpKWArgs=httpKWArgs,
               content={u'call': {u'exception': ce, u'content': repr(content)}},
               contentType=contentType)


def valid_http(httpSuccess=HTTPOk, httpKWArgs=None, detail="", content=None, contentType='application/json'):
    """
    Returns successful HTTP with standardized information formatted with content type.
    (see `valid_http` for HTTP error calls)

    :param httpSuccess: any derived class from base `HTTPSuccessful` (default: HTTPOk)
    :param httpKWArgs: (dict) additional keyword arguments to pass to `httpSuccess` when called
    :param detail: additional message information (default: empty)
    :param content: json formatted content to include
    :param contentType: format in which to return the exception ('application/json', 'text/html' or 'text/plain')
    :return `HTTPSuccessful`: formatted successful with additional details and HTTP code
    """
    global RAISE_RECURSIVE_SAFEGUARD_COUNT

    content = dict() if content is None else content
    detail = repr(detail) if type(detail) is not str else detail
    httpCode, detail, content = validate_params(httpSuccess, [HTTPSuccessful, HTTPRedirection],
                                                detail, content, contentType)
    json_body = format_content_json_str(httpCode, detail, content, contentType)
    resp = generate_response_http_format(httpSuccess, httpKWArgs, json_body, outputType=contentType)
    RAISE_RECURSIVE_SAFEGUARD_COUNT = 0  # reset counter for future calls (don't accumulate for different requests)
    return resp


def raise_http(httpError=HTTPInternalServerError, httpKWArgs=None,
               detail="", content=None, contentType='application/json', nothrow=False):
    """
    Raises error HTTP with standardized information formatted with content type.
    (see `valid_http` for HTTP successful calls)

    The content contains the corresponding http error code, the provided message as detail and
    optional specified additional json content (kwarg dict).

    :param httpError: any derived class from base `HTTPError` (default: HTTPInternalServerError)
    :param httpKWArgs: (dict) additional keyword arguments to pass to `httpError` if called in case of HTTP exception
    :param detail: additional message information (default: empty)
    :param content: json formatted content to include
    :param contentType: format in which to return the exception ('application/json', 'text/html' or 'text/plain')
    :param nothrow: returns the error response instead of raising it automatically, but still handles execution errors
    :raises `HTTPError`: formatted raised exception with additional details and HTTP code
    :return `HTTPError`: formatted exception with additional details and HTTP code only if `nothrow` is True
    """

    # fail-fast if recursion generates too many calls
    # this would happen only if a major programming error occurred within this function
    global RAISE_RECURSIVE_SAFEGUARD_MAX
    global RAISE_RECURSIVE_SAFEGUARD_COUNT
    RAISE_RECURSIVE_SAFEGUARD_COUNT = RAISE_RECURSIVE_SAFEGUARD_COUNT + 1
    if RAISE_RECURSIVE_SAFEGUARD_COUNT > RAISE_RECURSIVE_SAFEGUARD_MAX:
        raise HTTPInternalServerError(detail="Terminated. Too many recursions of `raise_http`")

    # try dumping content with json format, `HTTPInternalServerError` with caller info if fails.
    # content is added manually to avoid auto-format and suppression of fields by `HTTPException`
    httpCode, detail, content = validate_params(httpError, HTTPError, detail, content, contentType)
    json_body = format_content_json_str(httpError.code, detail, content, contentType)
    resp = generate_response_http_format(httpError, httpKWArgs, json_body, outputType=contentType)

    # reset counter for future calls (don't accumulate for different requests)
    # following raise is the last in the chain since it wasn't triggered by other functions
    RAISE_RECURSIVE_SAFEGUARD_COUNT = 0
    if nothrow: return resp
    raise resp


def validate_params(httpClass, httpBase, detail, content, contentType):
    """
    Validates parameter types and formats required by `valid_http` and `raise_http`.

    :param httpClass: any derived class from base `HTTPException` to verify
    :param httpBase: any derived sub-class(es) from base `HTTPException` as minimum requirement for `httpClass`
        (ie: 2xx, 4xx, 5xx codes). Can be a single class of an iterable of possible requirements (any).
    :param detail: additional message information (default: empty)
    :param content: json formatted content to include
    :param contentType: format in which to return the exception ('application/json', 'text/html' or 'text/plain')
    :raise `HTTPInternalServerError`: if any parameter is of invalid expected format
    :returns httpCode, detail, content: parameters with corrected and validated format if applicable
    """
    # verify input arguments, raise `HTTPInternalServerError` with caller info if invalid
    # cannot be done within a try/except because it would always trigger with `raise_http`
    content = dict() if content is None else content
    detail = repr(detail) if type(detail) not in [str, unicode] else detail
    if not isclass(httpClass):
        raise_http(httpError=HTTPInternalServerError,
                   detail="Object specified is not of type `HTTPError`",
                   contentType='application/json',
                   content={u'caller': {u'content': content,
                                        u'detail': detail,
                                        u'code': 520,  #'unknown' error
                                        u'type': contentType}})
    # if `httpClass` derives from `httpBase` (ex: `HTTPSuccessful` or `HTTPError`) it is of proper requested type
    # if it derives from `HTTPException`, it *could* be different than base (ex: 2xx instead of 4xx codes)
    # return 'unknown error' (520) if not of lowest level base `HTTPException`, otherwise use the available code
    httpBase = tuple(httpBase if hasattr(httpBase, '__iter__') else [httpBase])
    httpCode = httpClass.code if issubclass(httpClass, httpBase) else \
               httpClass.code if issubclass(httpClass, HTTPException) else 520
    if not issubclass(httpClass, httpBase):
        raise_http(httpError=HTTPInternalServerError,
                   detail="Invalid `httpBase` derived class specified",
                   contentType='application/json',
                   content={u'caller': {u'content': content,
                                        u'detail': detail,
                                        u'code': httpCode,
                                        u'type': contentType}})
    if contentType not in ['application/json', 'text/html', 'text/plain']:
        raise_http(httpError=HTTPInternalServerError,
                   detail="Invalid `contentType` specified for exception output",
                   contentType='application/json',
                   content={u'caller': {u'content': content,
                                        u'detail': detail,
                                        u'code': httpCode,
                                        u'type': contentType}})
    return httpCode, detail, content


def format_content_json_str(httpCode, detail, content, contentType):
    """
    Inserts the code, details, content and type within the body using json format.
    Includes also any other specified json formatted content in the body.
    Returns the whole json body as a single string for output.

    :raise `HTTPInternalServerError`: if parsing of the json content failed
    :returns: formatted json content as string with added HTTP code and details
    """
    json_body = {}
    try:
        content[u'code'] = httpCode
        content[u'detail'] = detail
        content[u'type'] = contentType
        json_body = json.dumps(content)
    except Exception as e:
        msg = "Dumping json content `" + str(content) + \
              "` resulted in exception `" + repr(e) + "`"
        raise_http(httpError=HTTPInternalServerError, detail=msg,
                   contentType='application/json',
                   content={u'traceback': repr(exc_info()), u'exception': repr(e),
                            u'caller': {u'content': repr(content),   # raw string to avoid recursive json.dumps error
                                        u'detail': detail,
                                        u'code': httpCode,
                                        u'type': contentType}})
    return json_body


def generate_response_http_format(httpClass, httpKWArgs, jsonContent, outputType='text/plain'):
    """
    Formats the HTTP response output according to desired `outputType` using provided HTTP code and content.

    :param httpClass: HTTPException derived class to use for output (code, generic title/explanation, etc.)
    :param httpKWArgs: (dict) additional keyword arguments to pass to `httpClass` when called
    :param jsonContent: (str) formatted json content providing additional details for the response cause
    :param outputType: {'application/json','text/html','text/plain'} (default: 'text/plain')
    :return: modified HTTPException derived class with information and output type if `outputMode` is 'return'
    :raises: modified HTTPException derived class with information and output type if `outputMode` is 'raise'
    """
    # content body is added manually to avoid auto-format and suppression of fields by `HTTPException`
    jsonContent = str(jsonContent) if not type(jsonContent) == str else jsonContent

    # adjust additional keyword arguments and try building the http response class with them
    httpKWArgs = dict() if httpKWArgs is None else httpKWArgs
    try:
        # directly output json if asked with 'application/json'
        if outputType == 'application/json':
            httpResponse = httpClass(body=jsonContent, content_type='application/json', **httpKWArgs)

        # otherwise json is contained within the html <body> section
        elif outputType == 'text/html':
            # add preformat <pre> section to output as is within the <body> section
            htmlBody = httpClass.explanation + "<br><h2>Exception Details</h2>" + \
                       "<pre style='word-wrap: break-word; white-space: pre-wrap;'>" + \
                       jsonContent + "</pre>"
            httpResponse = httpClass(body_template=htmlBody, content_type='text/html', **httpKWArgs)

        # default back to 'text/plain'
        else:
            httpResponse = httpClass(body=jsonContent, content_type='text/plain', **httpKWArgs)

        return httpResponse
    except Exception as e:
        raise_http(httpError=HTTPInternalServerError, detail="Failed to build HTTP response",
                   content={u'traceback': repr(exc_info()), u'exception': repr(e),
                            u'caller': {u'httpKWArgs': repr(httpKWArgs),
                                        u'httpClass': repr(httpClass),
                                        u'outputType': str(outputType)}})


def islambda(func):
    return isinstance(func, types.LambdaType) and func.__name__ == (lambda: None).__name__


def isclass(obj):
    """
    Evaluate an object for class type (ie: class definition, not an instance nor any other type).

    :param obj: object to evaluate for class type
    :return: (bool) indicating if `object` is a class
    """
    return isinstance(obj, (type, types.ClassType))
