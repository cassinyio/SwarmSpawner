"""
A Spawner for JupyterHub that runs each user's
server in a separate Docker Service
"""

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
            kwargs = {}
            if self.tls_config:
                kwargs['tls'] = docker.tls.TLSConfig(**self.tls_config)
            kwargs.update(kwargs_from_env())
            client = docker.APIClient(version='auto', **kwargs)

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
    tls_config = Dict(
        config=True,
        help=dedent(
            """Arguments to pass to docker TLS configuration.
            Check for more info: http://docker-py.readthedocs.io/en/stable/tls.html
            """
        )
    )

    container_spec = Dict({}, config=True, help="Params to create the service")
    resource_spec = Dict(
        {}, config=True, help="Params about cpu and memory limits")

    networks = List([], config=True,
                    help=dedent(
                        """Additional args to create_host_config for service create
                        """))
    use_user_options = Bool(False, config=True,
                            help=dedent(
                                """the spawner will use the dict passed through the form
                                or as json body when using the Hub Api
                                """))
    jupyterhub_service_name = Unicode(config=True,
                                      help=dedent(
                                          """Name of the service running the JupyterHub
                                          """))

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
        if hasattr(self, "server_name") and self.server_name:
            server_name = self.server_name
        else:
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
            self.log.warn("Docker service not found")
            return 0

        task_filter = {'service': service['Spec']['Name']}

        task = yield self.docker(
            'tasks', task_filter
        )

        # use the first and only task
        task = task[0]

        task_state = task['Status']['State']
        self.log.debug(
            "Task %s of Docker service %s status: %s",
            task['ID'][:7],
            self.service_id[:7],
            pformat(task_state),
        )

        if task_state == 'running':
            return None
        else:
            return 1

    @gen.coroutine
    def get_service(self):
        self.log.debug("Getting Docker service '%s'", self.service_name)
        try:
            service = yield self.docker(
                'inspect_service', self.service_name
            )
            self.service_id = service['ID']
        except APIError as err:
            if err.response.status_code == 404:
                self.log.info("Docker service '%s' is gone", self.service_name)
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

        # https://github.com/jupyterhub/jupyterhub/blob/master/jupyterhub/user.py#L202
        # By default jupyterhub calls the spawner passing user_options
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

                if 'source' in m:
                    m['source'] = m['source'].format(
                        username=self.service_owner)

                if 'driver_config' in m:
                    device = m['driver_config']['options']['device'].format(
                        username=self.service_owner
                    )
                    m['driver_config']['options']['device'] = device
                    m['driver_config'] = docker.types.DriverConfig(
                        **m['driver_config'])

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
            container_spec = docker.types.ContainerSpec(
                image, **container_spec)
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
                "Created Docker service '%s' (id: %s) from image %s",
                self.service_name, self.service_id[:7], image)

        else:
            self.log.info(
                "Found existing Docker service '%s' (id: %s)",
                self.service_name, self.service_id[:7])
            # Handle re-using API token.
            # Get the API token from the environment variables
            # of the running service:
            envs = service['Spec']['TaskTemplate']['ContainerSpec']['Env']
            for line in envs:
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
            "Stopping and removing Docker service %s (id: %s)",
            self.service_name, self.service_id[:7])
        yield self.docker('remove_service', self.service_id[:7])
        self.log.info(
            "Docker service %s (id: %s) removed",
            self.service_name, self.service_id[:7])

        self.clear_state()
