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

"""A REST protocol gateway to self-describing GRPC end-points"""

import argparse
import os
import sys

import yaml
from twisted.internet.defer import inlineCallbacks

from chameleon.utils.dockerhelpers import get_my_containers_name
from chameleon.utils.nethelpers import get_my_primary_local_ipv4
from chameleon.utils.structlog_setup import setup_logging

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)
sys.path.append(os.path.join(base_dir, '/chameleon/protos/third_party'))

from chameleon.grpc_client.grpc_client import GrpcClient
from chameleon.web_server.web_server import WebServer


defs = dict(
    config=os.environ.get('CONFIG', './chameleon.yml'),
    consul=os.environ.get('CONSUL', 'localhost:8500'),
    external_host_address=os.environ.get('EXTERNAL_HOST_ADDRESS',
                                         get_my_primary_local_ipv4()),
    grpc_endpoint=os.environ.get('GRPC_ENDPOINT', 'localhost:50055'),
    fluentd=os.environ.get('FLUENTD', None),
    instance_id=os.environ.get('INSTANCE_ID', os.environ.get('HOSTNAME', '1')),
    internal_host_address=os.environ.get('INTERNAL_HOST_ADDRESS',
                                         get_my_primary_local_ipv4()),
    rest_port=os.environ.get('REST_PORT', 8881),
    work_dir=os.environ.get('WORK_DIR', '/tmp/chameleon'),
    swagger_url=os.environ.get('SWAGGER_URL', ''),
    enable_tls=os.environ.get('ENABLE_TLS',"True"),
    key=os.environ.get('KEY','/chameleon/pki/voltha.key'),
    cert=os.environ.get('CERT','/chameleon/pki/voltha.crt'),
)


def parse_args():

    parser = argparse.ArgumentParser()

    _help = ('Path to chameleon.yml config file (default: %s). '
             'If relative, it is relative to main.py of chameleon.'
             % defs['config'])
    parser.add_argument('-c', '--config',
                        dest='config',
                        action='store',
                        default=defs['config'],
                        help=_help)

    _help = '<hostname>:<port> to consul agent (default: %s)' % defs['consul']
    parser.add_argument(
        '-C', '--consul', dest='consul', action='store',
        default=defs['consul'],
        help=_help)

    _help = ('<hostname> or <ip> at which Chameleon is reachable from outside '
             'the cluster (default: %s)' % defs['external_host_address'])
    parser.add_argument('-E', '--external-host-address',
                        dest='external_host_address',
                        action='store',
                        default=defs['external_host_address'],
                        help=_help)

    _help = ('<hostname>:<port> to fluentd server (default: %s). (If not '
             'specified (None), the address from the config file is used'
             % defs['fluentd'])
    parser.add_argument('-F', '--fluentd',
                        dest='fluentd',
                        action='store',
                        default=defs['fluentd'],
                        help=_help)

    _help = ('gRPC end-point to connect to. It can either be a direct'
             'definition in the form of <hostname>:<port>, or it can be an'
             'indirect definition in the form of @<service-name> where'
             '<service-name> is the name of the grpc service as registered'
             'in consul (example: @voltha-grpc). (default: %s'
             % defs['grpc_endpoint'])
    parser.add_argument('-G', '--grpc-endpoint',
                        dest='grpc_endpoint',
                        action='store',
                        default=defs['grpc_endpoint'],
                        help=_help)

    _help = ('<hostname> or <ip> at which Chameleon is reachable from inside'
             'the cluster (default: %s)' % defs['internal_host_address'])
    parser.add_argument('-H', '--internal-host-address',
                        dest='internal_host_address',
                        action='store',
                        default=defs['internal_host_address'],
                        help=_help)

    _help = ('unique string id of this Chameleon instance (default: %s)'
             % defs['instance_id'])
    parser.add_argument('-i', '--instance-id',
                        dest='instance_id',
                        action='store',
                        default=defs['instance_id'],
                        help=_help)

    _help = 'omit startup banner log lines'
    parser.add_argument('-n', '--no-banner',
                        dest='no_banner',
                        action='store_true',
                        default=False,
                        help=_help)

    _help = ('port number for the rest service (default: %d)'
             % defs['rest_port'])
    parser.add_argument('-R', '--rest-port',
                        dest='rest_port',
                        action='store',
                        type=int,
                        default=defs['rest_port'],
                        help=_help)

    _help = "suppress debug and info logs"
    parser.add_argument('-q', '--quiet',
                        dest='quiet',
                        action='count',
                        help=_help)

    _help = 'enable verbose logging'
    parser.add_argument('-v', '--verbose',
                        dest='verbose',
                        action='count',
                        help=_help)

    _help = ('work dir to compile and assemble generated files (default=%s)'
             % defs['work_dir'])
    parser.add_argument('-w', '--work-dir',
                        dest='work_dir',
                        action='store',
                        default=defs['work_dir'],
                        help=_help)

    _help = ('use docker container name as Chameleon instance id'
             ' (overrides -i/--instance-id option)')
    parser.add_argument('--instance-id-is-container-name',
                        dest='instance_id_is_container_name',
                        action='store_true',
                        default=False,
                        help=_help)

    _help = ('override swagger url (default=%s)'
             % defs['swagger_url'])
    parser.add_argument('-S', '--swagger-url',
                        dest='swagger_url',
                        action='store',
                        default=defs['swagger_url'],
                        help=_help)

    _help = ('Enable TLS or not (default: %s). '
             % defs['enable_tls'])
    parser.add_argument('-t', '--tls-enable',
                        dest='enable_tls',
                        action='store',
                        default=defs['enable_tls'],
                        help=_help)

    _help = ('Path to chameleon ssl server private key (default: %s). '
             'If relative, it is relative to main.py of chameleon.'
             % defs['key'])
    parser.add_argument('-k', '--key',
                        dest='key',
                        action='store',
                        default=defs['key'],
                        help=_help)

    _help = ('Path to chameleon ssl server certificate file (default: %s). '
             'If relative, it is relative to main.py of chameleon.'
             % defs['cert'])
    parser.add_argument('-f', '--cert-file',
                        dest='cert',
                        action='store',
                        default=defs['cert'],
                        help=_help)


    args = parser.parse_args()

    # post-processing

    if args.instance_id_is_container_name:
        args.instance_id = get_my_containers_name()

    return args


def load_config(args):
    path = args.config
    if path.startswith('.'):
        dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(dir, path)
    path = os.path.abspath(path)
    with open(path) as fd:
        config = yaml.load(fd)
    return config

banner = r'''
   ____   _                                  _
  / ___| | |__     __ _   _ __ ___     ___  | |   ___    ___    _ __
 | |     | '_ \   / _` | | '_ ` _ \   / _ \ | |  / _ \  / _ \  | '_ \
 | |___  | | | | | (_| | | | | | | | |  __/ | | |  __/ | (_) | | | | |
  \____| |_| |_|  \__,_| |_| |_| |_|  \___| |_|  \___|  \___/  |_| |_|

'''

def print_banner(log):
    for line in banner.strip('\n').splitlines():
        log.info(line)
    log.info('(to stop: press Ctrl-C)')


class Main(object):

    def __init__(self):

        self.args = args = parse_args()
        self.config = load_config(args)

        verbosity_adjust = (args.verbose or 0) - (args.quiet or 0)
        self.log = setup_logging(self.config.get('logging', {}),
                                 args.instance_id,
                                 verbosity_adjust=verbosity_adjust,
                                 fluentd=args.fluentd)

        # components
        self.rest_server = None
        self.grpc_client = None

        if not args.no_banner:
            print_banner(self.log)

        self.startup_components()

    def start(self):
        self.start_reactor()  # will not return except Keyboard interrupt

    @inlineCallbacks
    def startup_components(self):
        try:
            self.log.info('starting-internal-components')
            args = self.args
            self.grpc_client = yield \
                GrpcClient(args.consul, args.work_dir, args.grpc_endpoint)

            if args.enable_tls == "False":
                self.log.info('tls-disabled-through-configuration')
                self.rest_server = yield \
                    WebServer(args.rest_port, args.work_dir, args.swagger_url,\
                    self.grpc_client).start()
            else:
                # If TLS is enabled, but the server key or cert is not found,
                # then automatically disable TLS
                if not os.path.exists(args.key) or \
                   not os.path.exists(args.cert):
                    if not os.path.exists(args.key):
                        self.log.error('key-not-found')
                    if not os.path.exists(args.cert):
                        self.log.error('cert-not-found')
                    self.log.info('disabling-tls-due-to-missing-pki-files')
                    self.rest_server = yield \
                                        WebServer(args.rest_port, args.work_dir,\
                                        args.swagger_url,\
                                        self.grpc_client).start()
                else:
                    self.log.info('tls-enabled')
                    self.rest_server = yield \
                                        WebServer(args.rest_port, args.work_dir,\
                                        args.swagger_url,\
                                        self.grpc_client, args.key,\
                                        args.cert).start()

            self.grpc_client.set_reconnect_callback(
                self.rest_server.reload_generated_routes).start()
            self.log.info('started-internal-services')
        except Exception, e:
            self.log.exception('startup-failed', e=e)

    @inlineCallbacks
    def shutdown_components(self):
        """Execute before the reactor is shut down"""
        self.log.info('exiting-on-keyboard-interrupt')
        if self.rest_server is not None:
            yield self.rest_server.stop()
        if self.grpc_client is not None:
            yield self.grpc_client.stop()

    def start_reactor(self):
        from twisted.internet import reactor
        reactor.callWhenRunning(
            lambda: self.log.info('twisted-reactor-started'))
        reactor.addSystemEventTrigger('before', 'shutdown',
                                      self.shutdown_components)
        reactor.run()


if __name__ == '__main__':
    Main().start()
