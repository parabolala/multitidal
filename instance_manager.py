from dataclasses import dataclass
import logging
import socket
from concurrent.futures import ThreadPoolExecutor
import uuid

import docker

# For executing dockere commands out of main io loop.
EXECUTOR = ThreadPoolExecutor(max_workers=4)

CLIENT = docker.client.from_env()


NUM_INSTANCES = 0

@dataclass
class Instance:
    id: int
    network: str
    hostname: str
    ssh_port: int
    mp3_port: int
    webssh_port: int

    tidal_container: docker.models.containers.Container
    webssh_container: docker.models.containers.Container


SSH_PORT_NAME = '22/tcp'
MP3_PORT_NAME = '8090/tcp'
WEBSSH_PORT_NAME = '2222/tcp'

def get_port(container, port_name):
    return int(container.ports[port_name][0]['HostPort'])


class InstanceManager(object):
    def __init__(self):
        self._instances = {}

    def start_one(self):
        t_cont = None
        w_cont = None
        network = None

        host = socket.gethostname()
        host = 'yvaravva-macbookpro2'
        try:
            global NUM_INSTANCES
            NUM_INSTANCES += 1
            network = CLIENT.networks.create(name=str(uuid.uuid4()))

            t_cont = CLIENT.containers.run(
                    image='quay.io/doubledensity/tidebox:0.2',
                    ports={
                        '22/tcp': (host, None),
                        '8090/tcp': (host, None),
                    },
                    detach=True,
                    network=network.id,
            )
            # Resolve autoassigned ports.
            t_cont = CLIENT.containers.get(t_cont.id)
            logging.info('Started tidal container')

            w_cont = CLIENT.containers.run(
                    image='webssh2',
                    ports={
                        '2222/tcp': (host, None),
                    },
                    detach=True,
                    network=network.id,
            )
            # Resolve autoassigned ports.
            w_cont = CLIENT.containers.get(w_cont.id)
            logging.info('Started webssh2 container')

            instance = Instance(
                    id=network.name,
                    network=network,
                    tidal_container=t_cont,
                    webssh_container=w_cont,

                    hostname=host,
                    ssh_port=get_port(t_cont, SSH_PORT_NAME),
                    mp3_port=get_port(t_cont, MP3_PORT_NAME),
                    webssh_port=get_port(w_cont, WEBSSH_PORT_NAME),
            )
            self._instances[instance.id] = instance

            return instance
        except Exception:
            if t_cont:
                t_cont.stop()
                t_cont.remove()
            if w_cont:
                w_cont.stop()
                w_cont.remove()
            if network:
                network.remove()
            raise

    def stop_instance(self, instance):
        instance = self._instances.pop(instance.id)
        logging.info("Stopping webssh container")
        instance.webssh_container.stop()
        instance.webssh_container.remove()
        logging.info("Stopping tidal container")
        instance.tidal_container.stop()
        instance.tidal_container.remove()
        instance.network.remove()
        logging.info("Done")

    def __del__(self):
        if self._instances:
            logging.error("InstanceManager being destroyed while some "
                          "instances are still alive")
            for instance in self._instances.keys()[:]:
                self.stop_instance(instance)

