import json
import logging
import socket

import tornado.websocket
import tornado.template

from . import instance_manager


class Controller:
    def __init__(self):
        self._sessions = {}
        self._observers = {}

        self._list_watchers = []

    def list_sessions(self):
        return list(self._sessions.keys())

    def add_session(self, session):
        self._sessions[session.i] = session
        self._observers[session.i] = []
        for w in self._list_watchers:
            w.on_session_add(session.i)

    def on_keystrokes(self, session_id):
        for list_watcher in self._list_watchers:
            list_watcher.on_keystrokes(session_id)

    def remove_session(self, session):
        logging.info("Removing session %r from %r", session.i, self._sessions)
        assert session.i in self._sessions
        session = self._sessions[session.i]
        observers = list(self._observers[session.i])

        for o in observers:
            o.on_console_close()
            self._detach_observer(o, session.i)

        for w in self._list_watchers:
            w.on_session_remove(session.i)
        del self._sessions[session.i]
        del self._observers[session.i]

    def add_list_watcher(self, handler):
        self._list_watchers.append(handler)
        for s in self._sessions:
            handler.on_session_add(s)

    def remove_list_watcher(self, handler):
        self._list_watchers.remove(handler)

    def start_observation(self, observer, session_id):
        logging.info("Starting observation of session %r of %r",
                     session_id, self._sessions)
        if session_id not in self._sessions:
            raise tornado.web.HTTPError(404,
                                        'session %s not found' % session_id)
        observers = self._observers[session_id]
        if not observers:
            self._sessions[session_id].start_session()
        observers.append(observer)
        observer.on_connection_details(
            self._sessions[session_id].get_ssh_url(),
            self._sessions[session_id].get_mp3_url(),
        )

    def _detach_observer(self, observer, session_id):
        logging.info("Stopping observation of session %r of %r",
                     session_id, self._sessions)
        assert session_id in self._sessions
        observers = self._observers[session_id]
        assert observer in observers
        observers.remove(observer)
        logging.info("remaining observers: %r", observers)
        if not observers:
            self._sessions[session_id].stop_session()

    def stop_observation(self, observer, session_id):
        self._detach_observer(observer, session_id)

    def stop(self):
        for s in list(self._sessions.values()):
            self.remove_session(s)


class Application(tornado.web.Application):

    def __init__(self):
        self._instance_manager = instance_manager.InstanceManager()
        self._c = c = Controller()
        settings = dict(
            debug=True,
            template_path='templates',
            static_path='media',
        )
        handlers = [
            (r"/console", ConsoleHandler, dict(
                c=c, im=self._instance_manager)),
            (r"/", IndexHandler),
            (r"/list", ListHandler, dict(c=c)),
            (r"/watch_list", WatchListHandler, dict(c=c)),
            (r"/observe/(\d+)", ObserveHandler, dict(c=c)),
            (r"/media/(.*)", tornado.web.StaticFileHandler,
             dict(path=settings['static_path'])),
        ]
        tornado.web.Application.__init__(self, handlers, **settings)
        tornado.autoreload.add_reload_hook(self.stop)

    def stop(self):
        self._c.stop()


class ConsoleHandler(tornado.websocket.WebSocketHandler):
    i = 0
    _c: Controller
    _instance: instance_manager.Instance
    _instance_manager: instance_manager.InstanceManager

    def __init__(self, *args, **kwargs):
        super(ConsoleHandler, self).__init__(*args, **kwargs)
        self.i = None

    def check_origin(self, origin):
        return True

    def initialize(self, c, im):
        self._c = c
        self._instance_manager = im
        self._instance = None

    def open(self):  # pylint: disable=arguments-differ
        self.__class__.i += 1
        self.i = self.__class__.i

        logging.info("A console connected: %d", self.i)
        self._c.add_session(self)
        sessions = self._c.list_sessions()
        print(sessions)
        self.write_message({'sessions': sessions})

    def on_close(self):
        logging.info("A client disconnected: %d", self.i)
        self._c.remove_session(self)
        if self._instance:
            self.stop_session()

    def on_message(self, message):
        logging.info("message from %s: %s", self.i, message)
        msg = json.loads(message)
        if msg['client_command'] == 'keystrokes':
            self._c.on_keystrokes(self.i)

    def get_mp3_url(self):
        return 'http://%s:%s/stream.mp3' % (
            self._instance.hostname,
            self._instance.mp3_port,
        )

    def get_ssh_url(self):
        return ('http://{webssh_host}:{webssh_port}/'
                'ssh/host/{target_host}?port={target_port}').format(
                    webssh_host='localhost',
                    webssh_port=self._instance.webssh_port,
                    target_host=self._instance.tidal_container.
                    attrs['Config']['Hostname'],
                    target_port='22',
                )

    def get_ssh_hostport(self):
        return (self._instance.hostname, self._instance.ssh_port)

    def start_session(self):
        logging.info("Starting container")
        instance = self._instance_manager.start_one(
            hostname=self.request.host_name)
        self._instance = instance
        logging.info("Connecting console to ssh")
        self.write_message(json.dumps({
            'mode': 'ssh',
            'ssh': {
                'host': socket.gethostbyname(instance.hostname),
                'port': instance.ssh_port,
            },
            'audio': self.get_mp3_url(),
        }))

    def stop_session(self):
        logging.info("Disonnecting console from ssh")
        try:
            self.write_message(json.dumps({
                'mode': 'idle',
            }))
        except tornado.websocket.WebSocketClosedError:
            pass
        logging.info("Stopping container")
        self._instance_manager.stop_instance(self._instance)
        self._instance = None
        logging.info("Stopped")


class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('index.html')


class ListHandler(tornado.web.RequestHandler):
    _c: Controller

    def initialize(self, c):
        self._c = c

    def get(self):
        self.write(json.dumps(self._c.list_sessions()))


class WatchListHandler(tornado.websocket.WebSocketHandler):

    _controller: Controller

    def initialize(self, c):
        self._controller = c

    def open(self):  # pylint: disable=arguments-differ
        self._controller.add_list_watcher(self)

    def on_close(self):
        self._controller.remove_list_watcher(self)

    def on_session_remove(self, session_id):
        self.write_message(json.dumps({
            'command': 'session_remove',
            'session_id': session_id,
        }))

    def on_session_add(self, session_id):
        self.write_message(json.dumps({
            'command': 'session_add',
            'session_id': session_id,
        }))

    def on_keystrokes(self, session_id):
        self.write_message(json.dumps({
            'command': 'keystrokes',
            'keystrokes': {
                'session_id': session_id,
            },
        }))


class ObserveHandler(tornado.websocket.WebSocketHandler):

    def __init__(self, *args, **kwargs):
        super(ObserveHandler, self).__init__(*args, **kwargs)
        self.i = None
        self._c = None

    def check_origin(self, origin):
        return True

    def initialize(self, c):
        self._c = c

    def open(self, session_id):  # pylint: disable=arguments-differ
        self.i = int(session_id)
        logging.info("Web starting obsevation of: %d", self.i)
        self.write_message(json.dumps({
            'status': 'connecting',
        }))
        try:
            self._c.start_observation(self, self.i)
        except tornado.web.HTTPError:
            self.write_message(json.dumps({
                'status': 'unknown session',
            }))

    def on_close(self):
        logging.info("Web stopped observing: %d", self.i)
        self._c.stop_observation(self, self.i)

    def on_message(self, message):
        logging.info("message from %s: %s", self.i, message)

    def on_console_close(self):
        logging.info("Observed console closed")
        self.write_message(json.dumps({
            'status': 'disconnected',
        }))

    def on_connection_details(self, ssh_url, mp3_url):
        logging.info("Sending ssh details to web client")
        self.write_message(json.dumps({
            'status': 'connected',
            'ssh': {
                'url': ssh_url,
            },
            'mp3': {
                'url': mp3_url,
            },
        }))

    def data_received(self, unused_bytes):
        pass
