"""A simple jupyter config file for testing the spawner."""

import docker
import stat

c = get_config()

c.JupyterHub.spawner_class = 'cassinyspawner.SwarmSpawner'
c.JupyterHub.hub_ip = '0.0.0.0'

# The name of the service that's running the hub
c.SwarmSpawner.jupyterhub_service_name = "jupyterhub"

# The name of the overlay network that everything's connected to
c.SwarmSpawner.networks = ["jh_test"]


c.SwarmSpawner.container_spec = {
    'args' : ['/usr/local/bin/start-singleuser.sh'],
    'Image' : "jupyterhub/singleuser:0.8",
    "mounts": []
    }

c.JupyterHub.authenticator_class = 'dummyauthenticator.DummyAuthenticator'
c.DummyAuthenticator.password = "just magnets"
