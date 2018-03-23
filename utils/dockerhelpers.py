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
import sys
from distutils.version import LooseVersion

from structlog import get_logger
log = get_logger()

# handle the python docker v1 to v2 API differences
try:
    from docker import __version__ as docker_version

    if LooseVersion(docker_version) < LooseVersion('2.0.0'):
        log.error("Unsupported python docker module!"
                  "Please upgrade to docker 2.x or later")

        # <2.x compatible import
        from docker import Client as DockerClient
    else:
        # >2.x compatible import
        from docker import APIClient as DockerClient

except ImportError:
    log.error("Unable to load python docker module!")
    sys.exit(1)

docker_socket = os.environ.get('DOCKER_SOCK', 'unix://tmp/docker.sock')


def get_my_containers_name():
    """
    Return the docker containers name in which this process is running.
    To look up the container name, we use the container ID extracted from the
    $HOSTNAME environment variable (which is set by docker conventions).
    :return: String with the docker container name (or None if any issue is
             encountered)
    """
    my_container_id = os.environ.get('HOSTNAME', None)

    try:
        docker_cli = DockerClient(base_url=docker_socket)
        info = docker_cli.inspect_container(my_container_id)

    except Exception, e:
        log.exception('failed', my_container_id=my_container_id, e=e)
        raise

    name = info['Name'].lstrip('/')

    return name
