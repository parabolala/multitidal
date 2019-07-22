import logging
import socket
from concurrent.futures import ThreadPoolExecutor
import uuid
import time

import docker

# For executing dockere commands out of main io loop.
EXECUTOR = ThreadPoolExecutor(max_workers=4)

CLIENT = docker.client.from_env()


SSH_PORT_NAME = '22/tcp'
MP3_PORT_NAME = '8090/tcp'
WEBSSH_PORT_NAME = '2222/tcp'


class MusicBox:
    id: int
    network: str = None
    hostname: str
    ssh_port: int
    mp3_port: int
    webssh_port: int

    tidal_container: docker.models.containers.Container = None
    webssh_container: docker.models.containers.Container = None

    _cleaned_up = True

    def start(self, hostname):
        self._cleaned_up = False
        try:
            network = CLIENT.networks.create(name=str(uuid.uuid4()))
            self.id = network.name
            self.network = network

            t_cont = CLIENT.containers.run(
                image='quay.io/doubledensity/tidebox:0.2',
                ports={
                    '22/tcp': ('0.0.0.0', None),
                    '8090/tcp': ('0.0.0.0', None),
                },
                detach=True,
                network=network.id,
            )
            # Resolve autoassigned ports.
            t_cont = CLIENT.containers.get(t_cont.id)
            logging.info('Started tidal container.')
            wait_for_healthy_tidal(t_cont)
            self.tidal_container = t_cont

            w_cont = CLIENT.containers.run(
                image='webssh2',
                ports={
                    '2222/tcp': ('0.0.0.0', None),
                },
                detach=True,
                network=network.id,
            )
            # Resolve autoassigned ports.
            w_cont = CLIENT.containers.get(w_cont.id)
            logging.info('Started webssh2 container')
            wait_for_healthy_webssh(w_cont)
            self.webssh_container = w_cont

            self.hostname = hostname
            self.ssh_port = get_port(t_cont, SSH_PORT_NAME)
            self.mp3_port = get_port(t_cont, MP3_PORT_NAME)
            self.webssh_port = get_port(w_cont, WEBSSH_PORT_NAME)
        except Exception:
            self.stop()
            raise

    def stop(self):
        if self._cleaned_up:
            return
        self._cleaned_up = True

        if self.tidal_container:
            logging.info('Stopping tidal container')
            self.tidal_container.stop()
            self.tidal_container.remove()
            self.tidal_container = None
        if self.webssh_container:
            logging.info('Stopping webssh container')
            self.webssh_container.stop()
            self.webssh_container.remove()
        if self.network:
            self.network.remove()

    def __del__(self):
        if not self._cleaned_up:
            logging.warning("Instance being destroyed without cleaning up")


def get_port(container, port_name):
    return int(container.ports[port_name][0]['HostPort'])


def check_port_open(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0


def wait_for_healthy_tidal(container):
    attempts = 30
    while attempts > 0:
        unused_exit_code, output = container.exec_run([
            'cat', '/tmp/supervisord.log'])
        if b'success: sshd' in output:
            logging.info('SSHd started inside tidal')
            break
        else:
            logging.info('SSHd still not started remaining: %d', attempts)
            attempts -= 1
            time.sleep(.5)
    else:
        raise Exception('Tidal container SSH port never became healthy')


def wait_for_healthy_webssh(container):
    attempts = 30
    while attempts > 0:
        log_output = container.logs()
        if b'WebSSH2 service listening on 0.0.0.0:2222' in log_output:
            logging.info('WebSSH listening started inside tidal')
            break
        else:
            logging.info('WebSSH still not started remaining: %d', attempts)
            attempts -= 1
            time.sleep(.5)
    else:
        raise Exception('Tidal container SSH port never became healthy')

