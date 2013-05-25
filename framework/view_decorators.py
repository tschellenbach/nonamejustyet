import json

from django import shortcuts as django_shortcuts
from coffin import shortcuts as jinja_shortcuts
from django import http
from django.template import RequestContext
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth import decorators
from functools import partial


__all__ = ['content_admin_env']

class ViewError(Exception):
    pass

class UnknownViewResponseError(ViewError):
    pass

REQUEST_PROPERTIES = {
    'redirect': http.HttpResponseRedirect,
    'permanent_redirect': http.HttpResponsePermanentRedirect,
    'not_found': http.HttpResponseNotFound,
}

def _prepare_request(request, name):
    '''Add context and extra methods to the request'''
    request.context = RequestContext(request)
    request.context['tab'] = name

    for k, v in REQUEST_PROPERTIES.iteritems():
        setattr(request, k, v)

    return request

def _process_response(request, response):
    '''Generic response processing function, always returns HttpResponse'''

    '''If we add something to the context stack, pop it after adding'''
    pop = False


    try:
        if isinstance(response, (dict, list)):
            if request.ajax:
                output = json = json.dumps(response)
                callback = request.GET.get('callback', False)
                if callback:
                    output = '%s(%s)' % (callback, json)
                if request.GET.get('debug'):
                    output = '<html><head></head><body><textarea>%s</textarea></body></html>' % output
                    response = http.HttpResponse(output,mimetype='text/html')
                else:
                    response = http.HttpResponse(output,mimetype='text/plain')

                return response
            else:
                '''Add the dictionary to the context and let render_to_response
                handle it'''
                request.context.update(response)
                response = None
                pop = True

        if isinstance(response, http.HttpResponse):
            return response


        elif isinstance(response, basestring):
            if request.ajax:
                return http.HttpResponse(response, mimetype='text/plain')
            else:
                return http.HttpResponse(response)

        elif response is None:
            if request.jinja:
                render_to_response = jinja_shortcuts.render_to_response
            else:
                render_to_response = django_shortcuts.render_to_response

            return render_to_response(request.template,
                context_instance=request.context)

        else:
            raise UnknownViewResponseError(
                '"%s" is an unsupported response type' % type(response))
    finally:
        if pop:
            request.context.pop()

def content_admin_env(function=None, require_superuser=False, module=None):
    '''
    View decorator that automatically adds context and renders response

    Keyword arguments:
    require_superuser -- is every staff member allowed or only superusers?

    Adds a RequestContext (request.context) with the following context items:
    tab -- current function name

    Stores the template in request.template and assumes it to be in
    /admin/content_admin/<function_name>.html
    '''
    def _content_admin_env(request, *args, **kwargs):
        request.ajax = request.is_ajax() or bool(int(request.REQUEST.get('ajax', 0)))
        request.context = None
        request.jinja = True
        try:
            name = function.__name__
            request = _prepare_request(request, name)
            if module:
                request.template = 'content_admin/%s/%s.html' % (
                    module, name)
            else:
                request.template = 'content_admin/%s.html' % name

            response = function(request, *args, **kwargs)
            return _process_response(request, response)
        finally:
            '''Remove the context reference from request to prevent leaking'''
            try:
                del request.context, request.template
                for k, v in REQUEST_PROPERTIES.iteritems():
                    delattr(request, k)
            except AttributeError:
                pass

    if function:
        _content_admin_env.__name__ = function.__name__
        _content_admin_env.__doc__ = function.__doc__
        _content_admin_env.__module__ = function.__module__
        _content_admin_env.__dict__ = function.__dict__
        _content_admin_env._content_admin_environment = True

        if require_superuser:
            decorator = user_passes_test(lambda u: u.is_superuser)
        else:
            decorator = staff_member_required

        return decorator(_content_admin_env)
    else:
        return lambda f: content_admin_env(f, require_superuser, module)




def view_defaults(function=None, login_required=False):
    '''
    View decorator that automatically adds context and renders response

    Keyword arguments:
    login_required -- is everyone allowed or only authenticated users

    Adds a RequestContext (request.context) with the following context items:
    name -- current function name

    Stores the template in request.template and assumes it to be in
    <url>.html
    '''

    def _env(request, *args, **kwargs):
        request.ajax = request.is_ajax() or bool(int(request.REQUEST.get('ajax', 0)))
        request.context = None
        request.jinja = False
        try:
            name = function.__name__
            app = function.__module__.split('.')[0]

            request = _prepare_request(request, name)

            if app:
                request.template = '%s/%s.html' % (app, name)
            else:
                request.template = '%s.html' % name

            response = function(request, *args, **kwargs)



            return _process_response(request, response)
        finally:
            '''Remove the context reference from request to prevent leaking'''
            try:
                del request.context, request.template
                for k, v in REQUEST_PROPERTIES.iteritems():
                    delattr(request, k)
            except AttributeError:
                pass

    if function:
        _env.__name__ = function.__name__
        _env.__doc__ = function.__doc__
        _env.__module__ = function.__module__
        _env.__dict__ = function.__dict__
        _env._fashiolista_environment = True

        if login_required:
            return decorators.login_required(_env)
        else:
            return _env
    else:
        return lambda f: fashiolista_env(f, login_required)

