# Configuration file for jupyterhub.

import os
import subprocess
import os
import errno
import stat

c = get_config()
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

mounts = [{'type' : 'volume',
           'source' : 'jupyterhub-user-{username}',
           'target' : notebook_dir}]

c.SwarmSpawner.container_spec = {
    # The command to run inside the service
    'args' : '/usr/local/bin/start-singleuser.sh', #(string or list)
    'Image' : 'YourImage',
    'mounts' : mounts
    }

c.SwarmSpawner.resource_spec = {
                'cpu_limit' : 1000, # (int) – CPU limit in units of 10^9 CPU shares.
                'mem_limit' : int(512 * 1e6), # (int) – Memory limit in Bytes.
                'cpu_reservation' : 1000, # (int) – CPU reservation in units of 10^9 CPU shares.
                'mem_reservation' : int(512 * 1e6), # (int) – Memory reservation in Bytes
                }