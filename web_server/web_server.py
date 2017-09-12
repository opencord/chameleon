#!/usr/bin/env python
#
# Copyright 2017 the original author or authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os

import grpc
from klein import Klein
from simplejson import dumps, load
from structlog import get_logger
from twisted.internet import reactor, endpoints
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.tcp import Port
from twisted.internet.endpoints import SSL4ServerEndpoint
from twisted.internet.ssl import DefaultOpenSSLContextFactory
from twisted.web.server import Site
from twisted.web.static import File
from OpenSSL.SSL import TLSv1_2_METHOD
from werkzeug.exceptions import BadRequest
from grpc import StatusCode
import json


log = get_logger()


class WebServer(object):

    app = Klein()

    def __init__(self, port, work_dir, swagger_url, grpc_client, key=None, cert=None):
        self.port = port
        self.site = None
        self.work_dir = work_dir
        self.swagger_url = swagger_url
        self.grpc_client = grpc_client
        self.key = key
        self.cert = cert

        self.swagger_ui_root_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../swagger_ui'))

        self.tcp_port = None
        self.shutting_down = False

        self.add_swagger_routes(self.app, swagger_url)

    def add_swagger_routes(self, app, swagger_url):
        log.info('Publishing swagger docs at %s' % swagger_url)

        @app.route(swagger_url + '/', branch=True)
        def static(self, request):
            try:
                log.debug(request=request)
                return File(self.swagger_ui_root_dir)
            except Exception, e:
                log.exception('file-not-found', request=request)

        @app.route(swagger_url + '/v1/swagger.json')
        def swagger_json(self, request):
            try:
                return File(os.path.join(self.work_dir, 'swagger.json'))
            except Exception, e:
                log.exception('file-not-found', request=request)

    @inlineCallbacks
    def start(self):
        log.debug('starting')
        yield self._open_endpoint()
        log.info('started')
        returnValue(self)

    @inlineCallbacks
    def stop(self):
        log.debug('stopping')
        self.shutting_down = True
        if self.tcp_port is not None:
            assert isinstance(self.tcp_port, Port)
            yield self.tcp_port.socket.close()
        log.info('stopped')

    @inlineCallbacks
    def _open_endpoint(self):
        try:
            if self.key == None or self.cert == None:
                endpoint = endpoints.TCP4ServerEndpoint(reactor, self.port)
            else:
                # Enforce TLSv1_2_METHOD
                ctx = DefaultOpenSSLContextFactory(self.key, self.cert, TLSv1_2_METHOD)
                endpoint = SSL4ServerEndpoint(reactor, self.port, ctx)

            self.site = Site(self.app.resource())
            self.tcp_port = yield endpoint.listen(self.site)
            log.info('web-server-started', port=self.port)
            self.endpoint = endpoint
        except Exception, e:
            self.log.exception('web-server-failed-to-start', e=e)

    def reload_generated_routes(self):
        for fname in os.listdir(self.work_dir):
            if fname.endswith('_gw.py'):
                module_name = fname.replace('.py', '')
                m = __import__(module_name)
                assert hasattr(m, 'add_routes')
                m.add_routes(self.app, self.grpc_client)
                log.info('routes-loaded', module=module_name)

    @app.handle_errors(grpc._channel._Rendezvous)
    def grpc_exception(self, request, failure):
        code = failure.value.code()
        if code == StatusCode.NOT_FOUND:
            request.setResponseCode(404)
            return failure.value.details()
        elif code == StatusCode.INVALID_ARGUMENT:
            request.setResponseCode(400)
            return failure.value.details()
        elif code == StatusCode.ALREADY_EXISTS:
            request.setResponseCode(409)
            return failure.value.details()
        elif code == StatusCode.UNAUTHENTICATED:
            request.setResponseCode(401)
            return failure.value.details()
        elif code == StatusCode.PERMISSION_DENIED:
            request.setResponseCode(403)
            return failure.value.details()
        else:
            request.setResponseCode(500)
            return json.dumps({'error': 'Internal Server Error', 'specific_error': failure.value.details()})

