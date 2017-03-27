# SwarmSpawner

**SwarmSpawner** enables [JupyterHub](https://github.com/jupyterhub/jupyterhub) 
to spawn single user notebook servers in Docker Services.

More info about Docker Services [here](https://docs.docker.com/engine/reference/commandline/service_create/).

## Prerequisites

Python version 3.3 and above is required.

Clone the repo:

```bash
git clone https://github.com/cassinyio/SwarmSpawner
cd SwarmSpawner
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Installation

Install SwarmSpawner to the system:
```bash
python setup.py install
```

## Configuration

You can find an example jupyter_config.py inside [examples](/examples)

### SwarmSpawner

Docker Engine in Swarm mode and the related services work in a different way compared to Docker containers.


Tell JupyterHub to use SwarmSpawner by adding the following lines to 
your `jupyterhub_config.py`:

```python
c.JupyterHub.spawner_class = 'cassinyspawner.SwarmSpawner'


# This should be the name of the jupyterhub service
c.JupyterHub.hub_ip = '0.0.0.0'
c.SwarmSpawner.jupyterhub_service_name = 'NameOfTheService'
```
What is `jupyterhub_service_name`?

Inside a Docker engine in Swarm mode the services use a `name` instead of a `ip` to communicate with each other.
'jupyterhub_service_name' is the name of ther service for the JupyterHub.

### Networks
It's important to put the JupyterHub service (also the proxy) and the services that are running jupyter notebook inside the same network, otherwise they couldn't reach each other.
SwarmSpawner use the service's name instead of the service's ip, as a consequence JupyterHub and servers should share the same overlay network (network across nodes).

```python
c.SwarmSpawner.networks = ["mynetwork"] #list of networks
```

### Define the services inside jupyterhub_config.py
You can define *container_spec*, *resource_spec* and _networks_ within jupyterhub_config.py.

#### [Container_spec](https://github.com/docker/docker-py/blob/master/docs/user_guides/swarm_services.md)
'command' and 'args' depends on the image that you are using.

If you use one of the images from the Jupyter docker stack you need to specify args as: /usr/local/bin/start-singleuser.sh

If you are using a specific image, well it's up to you to specify the right command.

```python
    c.SwarmSpawner.container_spec = {
                  # The command to run inside the service
                  # 'args' : '/usr/local/bin/start-singleuser.sh', #(string or list)
                  'Image' : 'YourImage',
                  'mounts' : mounts
          }
```


__Note:__ in a container spec, `args` sets the equivalent of CMD in the Dockerfile.
`command` sets the equivalent of ENTRYPOINT.
The notebook server itself should not be the ENTRYPOINT,
so generally use `args`, not `command`, to specify how to launch the notebook server.
See this [issue](https://github.com/cassinyio/SwarmSpawner/issues/6) for more info.

##### Bind a Host dir
With mounts your are going to mount a local directory of the host inside the container.

<u>Remember that source should exist in the node where you are creating the service.</u>

```python
notebook_dir = os.environ.get('NOTEBOOK_DIR') or '/home/jovyan/work'
c.SwarmSpawner.notebook_dir = notebook_dir
```

```python
mounts = [{'type' : 'bind',
           'source' : 'MountPointOnTheHost',
           'target' : 'MountPointInsideTheContainer',}]
```

##### Mount a named volume
With mounts your are going to mount a Docker Volume inside the container.
If the volume doesn't exist it will be created.

```python
mounts = [{'type' : 'volume',
           'source' : 'NameOfTheVolume',
           'target' : 'MountPointInsideTheContainer',}]
```

For this type of volume you can also specify something like this:

```python
mounts = [{'type' : 'volume',
           'source' : 'jupyterhub-user-{username}',
           'target' : 'MountPointInsideTheContainer',}]
```

username will be the hashed version of the username.


##### Mount an anonymous volume
__This kind of volume will be removed with the service__
```python
mounts = [{'type' : 'volume',
           'target' : 'MountPointInsideTheContainer',}]
```

#### Resource_spec

You can also specify some resource for each service

```python
c.SwarmSpawner.resource_spec = {
                'cpu_limit' : 1000, # (int) – CPU limit in units of 10^9 CPU shares.
                'mem_limit' : int(512 * 1e6), # (int) – Memory limit in Bytes.
                'cpu_reservation' : 1000, # (int) – CPU reservation in units of 10^9 CPU shares.
                'mem_reservation' : int(512 * 1e6), # (int) – Memory reservation in Bytes
                }
```

### Using user_options

There is the possibility to set parameters using `user_options`
```python
# To use user_options in service creation
c.SwarmSpawner.use_user_options = False
```

To control the creation of the services you have 2 ways, using _jupyterhub_config.py_ or _user_options_.

Remember that at the end you are just using the [Docker Engine API](https://docs.docker.com/engine/api/).

**user_options, if used, will overwrite jupyter_config.py for services.**

If you set 'c.SwarmSpawner.use_user_option = True' the spawner will use the dict passed through the form or as json body when using the Hub Api.

The spawner expect a dict with these keys:

```python
user_options = {
  'container_spec' : {
              'args' : ['/usr/local/bin/start-singleuser.sh'],   #(string or list) command to run in the image.
              'Image' : '', # name of the image
              'mounts' : mounts, # Same as jupyterhub_config 
  'resource_spec' : {
              'cpu_limit' : 1000, # (int) – CPU limit in units of 10^9 CPU shares.
              'mem_limit' : int(512 * 1e6),# (int) – Memory limit in Bytes.
              'cpu_reservation' : 1000, # (int) – CPU reservation in units of 10^9 CPU shares.
              'mem_reservation' : int(512 * 1e6), # (int) – Memory reservation in Bytes
      },
      'placement' : [], #list of constrains
      'network' : [], #list of networks
      'name' : '' # Name of service
```

### Names of the Jupyter notebook service inside Docker engine in Swarm mode

We JupyterHub spawns a new Jupyter notebook server the name of the service will be `{service_prefix}-{service_owner}-{service_suffix}`

You can change the service_prefix in this way:

Prefix of the service in Docker
```python
c.SwarmSpawner.service_prefix = "jupyterhub"
```

`service_owner` is the hexdigest() of the hashed `user.name`.

In case of named servers (more than one server for user) `service_suffix` is the name of the server, otherwise is always 1.

### Downloading images
Docker Engine in Swarm mode downloads images automatically from the repository.
Either the image is available on the remote repository or locally, if not you will get an error. 

Because before starting the service you have to complete the download of the image is better to have a longer timeout (default is 30 secs)

 ```
 c.SwarmSpawner.start_timeout = 60 * 5
```       

You can use all the docker images built for [JupyterHub](https://github.com/jupyter/docker-stacks).

## Contributing

If you would like to contribute to the project, please read [contributor documentation](http://jupyter.readthedocs.io/en/latest/contributor/content-contributor.html).

For a **development install**, clone the [repository](https://github.com/cassiny/SwarmSpawner) 
and then install from source:

```bash
git clone https://github.com/cassiny/SwarmSpawner
cd SwarmSpawner
pip3 install -r dev-requirements.txt -e .
```
## Credit

[DockerSpawner](https://github.com/jupyterhub/dockerspawner)

## License

All code is licensed under the terms of the revised BSD license.

  
