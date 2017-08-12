# Configuration file for jupyterhub.

import os

c = get_config() # noqa
pwd = os.path.dirname(__file__)

c.JupyterHub.spawner_class = 'cassinyspawner.SwarmSpawner'

c.JupyterHub.ip = '0.0.0.0'
c.JupyterHub.hub_ip = '0.0.0.0'

c.JupyterHub.cleanup_servers = False

# First pulls can be really slow, so let's give it a big timeout
c.SwarmSpawner.start_timeout = 60 * 5

c.SwarmSpawner.jupyterhub_service_name = 'jupyterhub'

c.SwarmSpawner.networks = ["jupyterhub"]

notebook_dir = os.environ.get('NOTEBOOK_DIR') or '/home/jovyan/work'
c.SwarmSpawner.notebook_dir = notebook_dir

mounts = [{'type': 'volume',
           'source': 'jupyterhub-user-{username}',
           'target': notebook_dir}]

c.SwarmSpawner.container_spec = {
    # The command to run inside the service
    'args': '/usr/local/bin/start-singleuser.sh',  # (string or list)
    'Image': 'YourImage',
    'mounts': mounts
}

c.SwarmSpawner.resource_spec = {
    # (int) – CPU limit in units of 10^9 CPU shares.
    'cpu_limit': int(1 * 1e9),
    # (int) – Memory limit in Bytes.
    'mem_limit': int(512 * 1e6),
    # (int) – CPU reservation in units of 10^9 CPU shares.
    'cpu_reservation': int(1 * 1e9),
    # (int) – Memory reservation in bytes
    'mem_reservation': int(512 * 1e6),
}
