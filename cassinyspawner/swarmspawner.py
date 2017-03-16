"""
A Spawner for JupyterHub that runs each user's
server in a separate Docker Service
"""

import os
import string
import hashlib
from textwrap import dedent
from concurrent.futures import ThreadPoolExecutor
from pprint import pformat

import docker
from docker.errors import APIError
from docker.utils import kwargs_from_env
from tornado import gen

from jupyterhub.spawner import Spawner
from traitlets import (
    Dict,
    Unicode,
    List,
    Bool,
    Int,
)


class UnicodeOrFalse(Unicode):
    info_text = 'a unicode string or False'

    def validate(self, obj, value):
        if value is False:
            return value
        return super(UnicodeOrFalse, self).validate(obj, value)


class SwarmSpawner(Spawner):
    """A Spawner for JupyterHub using Docker Engine in Swarm mode
    """

    _executor = None

    @property
    def executor(self, max_workers=1):
        """single global executor"""
        cls = self.__class__
        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(max_workers)
        return cls._executor

    _client = None

    @property
    def client(self):
        """single global client instance"""
        cls = self.__class__
        if cls._client is None:
            if self.use_docker_client_env:
                kwargs = kwargs_from_env(
                    assert_hostname=self.tls_assert_hostname
                )
                client = docker.APIClient(version='auto', **kwargs)
            else:
                if self.tls:
                    tls_config = True
                elif self.tls_verify or self.tls_ca or self.tls_client:
                    tls_config = docker.tls.TLSConfig(
                        client_cert=self.tls_client,
                        ca_cert=self.tls_ca,
                        verify=self.tls_verify,
                        assert_hostname=self.tls_assert_hostname)
                else:
                    tls_config = None

                docker_host = os.environ.get('DOCKER_HOST', 'unix://var/run/docker.sock')

                client = docker.APIClient(base_url=docker_host,
                                          tls=tls_config,
                                          version='auto')
            cls._client = client
        return cls._client

    service_id = Unicode()
    service_port = Int(8888, min=1, max=65535, config=True)
    service_image = Unicode("jupyterhub/singleuser", config=True)
    service_prefix = Unicode(
        "jupyter",
        config=True,
        help=dedent(
            """
            Prefix for service names. The full service name for a particular
            user will be <prefix>-<hash(username)>-<server_name>.
            """
        )
    )

    use_docker_client_env = Bool(False, config=True,
                                 help="If True, will use Docker client env \
                                 variable (boot2docker friendly)")
    tls = Bool(False, config=True, help="If True, connect to docker with --tls")
    tls_verify = Bool(False, config=True, help="If True, connect to docker with --tlsverify")
    tls_ca = Unicode("", config=True, help="Path to CA certificate for docker TLS")
    tls_cert = Unicode("", config=True, help="Path to client certificate for docker TLS")
    tls_key = Unicode("", config=True, help="Path to client key for docker TLS")
    tls_assert_hostname = UnicodeOrFalse(default_value=None,
                                         allow_none=True,
                                         config=True,
                                         help="If False, do not verify hostname of docker daemon",)

    container_spec = Dict({}, config=True, help="Params to create the service")
    resource_spec = Dict({}, config=True, help="Params about cpu and memory limits")
    networks = List([], config=True, help="Additional args to create_host_config for service create")

    _docker_safe_chars = set(string.ascii_letters + string.digits + '-')
    _docker_escape_char = '_'

    use_user_options = Bool(False, config=True, help="the spawner will use the dict passed through the form or as json body when using the Hub Api")
    jupyterhub_service_name = Unicode(config=True,
                                      help=dedent("""Name of the service running the JupyterHub"""))

    @property
    def tls_client(self):
        """A tuple consisting of the TLS client certificate and key if they
        have been provided, otherwise None.

        """
        if self.tls_cert and self.tls_key:
            return (self.tls_cert, self.tls_key)
        return None

    _service_owner = None

    @property
    def service_owner(self):
        if self._service_owner is None:
            m = hashlib.md5()
            m.update(self.user.name.encode('utf-8'))
            self._service_owner = m.hexdigest()
        return self._service_owner

    @property
    def service_name(self):
        """
        Service name inside the Docker Swarm

        service_suffix should be a numerical value unique for user
        {service_prefix}-{service_owner}-{service_suffix}
        """
        # JupyterHub with multi-server-per-user should pass server_name
        # In the future we can remove this part
        server_name = getattr(self, "server_name", None)
        if server_name is None:
            server_name = 1

        return "{}-{}-{}".format(self.service_prefix,
                                 self.service_owner,
                                 server_name
                                )

    def load_state(self, state):
        super().load_state(state)
        self.service_id = state.get('service_id', '')

    def get_state(self):
        state = super().get_state()
        if self.service_id:
            state['service_id'] = self.service_id
        return state

    def _env_keep_default(self):
        """it's called in traitlets. It's a special method name.
        Don't inherit any env from the parent process"""
        return []

    def _public_hub_api_url(self):
        proto, path = self.hub.api_url.split('://', 1)
        _, rest = path.split(':', 1)
        return '{proto}://{name}:{rest}'.format(
            proto=proto,
            name=self.jupyterhub_service_name,
            rest=rest
        )

    def get_env(self):
        env = super().get_env()
        env.update(dict(
            JPY_USER=self.user.name,
            JPY_COOKIE_NAME=self.user.server.cookie_name,
            JPY_BASE_URL=self.user.server.base_url,
            JPY_HUB_PREFIX=self.hub.server.base_url
        ))

        if self.notebook_dir:
            env['NOTEBOOK_DIR'] = self.notebook_dir

        env['JPY_HUB_API_URL'] = self._public_hub_api_url()

        return env

    def _docker(self, method, *args, **kwargs):
        """wrapper for calling docker methods

        to be passed to ThreadPoolExecutor
        """
        m = getattr(self.client, method)
        return m(*args, **kwargs)

    def docker(self, method, *args, **kwargs):
        """Call a docker method in a background thread

        returns a Future
        """
        return self.executor.submit(self._docker, method, *args, **kwargs)

    @gen.coroutine
    def poll(self):
        """Check for a task state like `docker service ps id`"""
        service = yield self.get_service()
        if not service:
            self.log.warn("Service not found")
            return ""

        task_filter = {'service': service['Spec']['Name']}

        task = yield self.docker(
            'tasks', task_filter
        )

        # use the first task and only task
        task = task[0]

        task_state = task['Status']['State']
        self.log.debug(
            "Task %s of Service %s status: %s",
            task['ID'][:7],
            self.service_id[:7],
            pformat(task_state),
        )

        if task_state == 'running':
            return None
        else:
            return (
                "ExitCode={ExitCode}, "
                "Error='{Error}', "
                "FinishedAt={FinishedAt}".format(**task_state)
            )

    @gen.coroutine
    def get_service(self):
        self.log.debug("Getting service '%s'", self.service_name)
        try:
            service = yield self.docker(
                'inspect_service', self.service_name
            )
            self.service_id = service['ID']
        except APIError as err:
            if err.response.status_code == 404:
                self.log.info("Service '%s' is gone", self.service_name)
                service = None
                # Docker service is gone, remove service id
                self.service_id = ''
            elif err.response.status_code == 500:
                self.log.info("Docker Swarm Server error")
                service = None
                # Docker service is unhealthy, remove the service_id
                self.service_id = ''
            else:
                raise
        return service

    @gen.coroutine
    def start(self):
        """Start the single-user server in a docker service.
        You can specify the params for the service through jupyterhub_config.py
        or using the user_options
        """
        if self.use_user_options:
            user_options = self.user_options

        else:
            user_options = {}

        self.log.warn("user_options: ".format(user_options))

        service = yield self.get_service()

        if service is None:

            if 'name' in user_options:
                self.server_name = user_options['name']

            if hasattr(self, 'container_spec') and self.container_spec is not None:
                container_spec = dict(**self.container_spec)
            elif user_options == {}:
                raise("A container_spec is needed in to create a service")

            container_spec.update(user_options.get('container_spec', {}))

            # iterates over mounts to create
            # a new mounts list of docker.types.Mount
            container_spec['mounts'] = []
            for mount in self.container_spec['mounts']:
                m = dict(**mount)
                if m['type'] == 'volume' and 'source' in m:
                    m['source'] = m['source'].format(username=self.service_owner)
                container_spec['mounts'].append(docker.types.Mount(**m))

            # some Envs are required by the single-user-image
            container_spec['env'] = self.get_env()

            if hasattr(self, 'resource_spec'):
                resource_spec = self.resource_spec
            resource_spec.update(user_options.get('resource_spec', {}))

            if hasattr(self, 'networks'):
                networks = self.networks
            if user_options.get('networks') is not None:
                networks = user_options.get('networks')

            image = container_spec['Image']
            del container_spec['Image']

            # create the service
            container_spec = docker.types.ContainerSpec(image, **container_spec)
            resources = docker.types.Resources(**resource_spec)

            task_spec = {'container_spec': container_spec,
                         'resources': resources,
                         'placement': user_options.get('placement')
                         }
            task_tmpl = docker.types.TaskTemplate(**task_spec)

            resp = yield self.docker('create_service',
                                     task_tmpl,
                                     name=self.service_name,
                                     networks=networks)

            self.service_id = resp['ID']

            self.log.info(
                "Created service '%s' (id: %s) from image %s",
                self.service_name, self.service_id[:7], image)

        else:
            self.log.info(
                "Found existing service '%s' (id: %s)",
                self.service_name, self.service_id[:7])
            # Handle re-using API token.
            # Get the API token from the environment variables
            # of the running service:
            for line in service['Config']['Env']:
                if line.startswith('JPY_API_TOKEN='):
                    self.api_token = line.split('=', 1)[1]
                    break

        ip = self.service_name
        port = self.service_port

        # we use service_name instead of ip
        # https://docs.docker.com/engine/swarm/networking/#use-swarm-mode-service-discovery
        # service_port is actually equal to 8888
        return (ip, port)

    @gen.coroutine
    def stop(self, now=False):
        """Stop and remove the service

        Consider using stop/start when Docker adds support
        """
        self.log.info(
            "Stopping and removing service %s (id: %s)",
            self.service_name, self.service_id[:7])
        yield self.docker('remove_service', self.service_id[:7])
        self.log.info(
            "Service removed %s (id: %s)",
            self.service_name, self.service_id[:7])

        self.clear_state()
