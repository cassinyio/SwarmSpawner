"""Define fixtures for SwarmSpawner tests."""

import os
import time

import docker
import pytest


HUB_IMAGE_TAG = "hub:test"
NETWORK_NAME = "jh_test"
HUB_SERVICE_NAME = "jupyterhub"

CONFIG_TEMPLATE_PATH = "tests/jupyter_config.j2"

@pytest.fixture(scope="session")
def swarm():
    """Initialize the docker swarm that's going to run the servers
    as services.
    """
    client = docker.from_env()
    client.swarm.init(advertise_addr="192.168.99.100")
    yield client.swarm.attrs
    client.swarm.leave(force=True)

@pytest.fixture(scope="session")
def hub_image():
    """Build the image for the jupyterhub. We'll run this as a service
    that's going to then spawn the notebook server services.
    """
    client = docker.from_env()

    # Build the image from the root of the package
    parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    image = client.images.build(path=parent_dir, tag=HUB_IMAGE_TAG, rm=True)
    yield image
    client.images.remove(image.tags[0])

@pytest.fixture(scope="session")
def network():
    """Create the overlay network that the hub and server services will
    use to communicate.
    """
    client = docker.from_env()
    network = client.networks.create(
        name=NETWORK_NAME,
        driver="overlay",
        options={"subnet": "192.168.0.0/20"},
        attachable=True)
    yield network
    network.remove()


@pytest.fixture
def hub_service(hub_image, swarm, network):
    """Launch the hub service.

    Note that we don't directly use any of the arguments, but those fixtures need to be
    in place before we can launch the service.
    """

    client = docker.from_env()
    config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "jupyter_config.py")
    service = client.services.create(
        image=HUB_IMAGE_TAG,
        name=HUB_SERVICE_NAME,
        mounts=[":".join(["/var/run/docker.sock", "/var/run/docker.sock", "rw"]),
                ":".join([config_path, "/srv/jupyterhub/jupyter_config.py", "ro"])],
        networks=[NETWORK_NAME],
        endpoint_spec=docker.types.EndpointSpec(ports={8000: 8000}))

    # Wait for the service's task to start running
    while service.tasks() and service.tasks()[0]["Status"]["State"] != "running":
        time.sleep(1)

    # And wait some more. This is...not great, but there seems to be a period after the task
    # is running but before the hub will accept connections. If the test code attempts to
    # connect to the hub during that time, it fails.
    time.sleep(10)

    yield service
    service.remove()
