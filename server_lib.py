import json
import logging

import tornado.websocket

import instance_manager



class Controller(object):
    def __init__(self):
        self._sessions = {}
        self._observers = {}

    def list_sessions(self):
        return list(self._sessions.keys())

    def add_session(self, session):
        self._sessions[session.i] = session
        self._observers[session.i] = []

    def remove_session(self, session):
        logging.info("Removing session %r from %r", session.i, self._sessions)
        assert session.i in self._sessions
        session = self._sessions.pop(session.i)
        observers = self._observers.pop(session.i)
        for o in observers:
            o.on_console_close()

    def start_observation(self, observer, session_id):
        logging.info("Starting observation of session %r of %r", session_id, self._sessions)
        assert session_id in self._sessions
        observers = self._observers[session_id]
        if not observers:
            self._sessions[session_id].start_session()
        observers.append(observer)
        observer.on_connection_details(
                self._sessions[session_id].get_ssh_hostport(),
                self._sessions[session_id].get_mp3_url(),
        )

    def stop_observation(self, observer, session_id):
        logging.info("Stopping observation of session %r of %r", session_id, self._sessions)
        assert session_id in self._sessions
        observers = self._observers[session_id]
        assert observer in observers
        observers.remove(observer)
        logging.info("remaining observers: %r", observers)
        if not observers:
            self._sessions[session_id].stop_session()


class Application(tornado.web.Application):

    def __init__(self):
        self._instance_manager = instance_manager.InstanceManager()
        self._c = c = Controller()
        handlers = [
                (r"/console", ConsoleHandler, dict(
                    c=c, im=self._instance_manager)),
                (r"/", IndexHandler, dict(c=c)),
                (r"/list", ListHandler, dict(c=c)),
                (r"/observe/(\d+)", ObserveHandler, dict(c=c)),
        ]
        settings = dict(debug=True)
        tornado.web.Application.__init__(self, handlers, **settings)



class ConsoleHandler(tornado.websocket.WebSocketHandler):
    i = 0

    def check_origin(self, origin):
        return True

    def initialize(self, c, im):
        self._c = c
        self._instance_manager = im
        self._instance = None

    def open(self):
        self.__class__.i += 1
        self.i = self.__class__.i

        logging.info("A console connected: %d" % self.i)
        self._c.add_session(self)
        sessions = self._c.list_sessions()
        print(sessions)
        self.write_message({'sessions': sessions})

    def on_close(self):
        logging.info("A client disconnected: %d" % self.i)
        self._c.remove_session(self)
        if self._instance:
            self.stop_session()

    def on_message(self, message):
        logging.info("message from {}: {}".format(self.i, message))

    def get_mp3_url(self):
        return 'http://%s:%s/stream.mp3' % (
                self._instance.hostname,
                self._instance.mp3_port,
        )

    def get_ssh_hostport(self):
        return (self._instance.hostname, self._instance.ssh_port)

    def start_session(self):
        logging.info("Starting container")
        instance = self._instance_manager.start_one()
        self._instance = instance
        logging.info("Connecting console to ssh")
        self.write_message(json.dumps({
            'mode': 'ssh',
            'ssh': {
                'host': instance.hostname,
                'port': instance.ssh_port,
            },
            'audio': self.get_mp3_url(),
        }))

    def stop_session(self):
        logging.info("Disonnecting console from ssh")
        self.write_message(json.dumps({
            'mode': 'idle',
        }))
        logging.info("Stopping container")
        self._instance_manager.stop_instance(self._instance)
        self._instance = None
        logging.info("Stopped")



class IndexHandler(tornado.web.RequestHandler):
    def initialize(self, c):
        self._c = c

    def get(self):
        self.write("Hello, world, sessions: %s " % self._c.list_sessions())


class ListHandler(tornado.web.RequestHandler):
    def initialize(self, c):
        self._c = c

    def get(self):
        self.write(json.dumps(self._c.list_sessions()))


class ObserveHandler(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True
    def initialize(self, c):
        self._c = c

    def open(self, session_id):
        self.i = int(session_id)
        logging.info("Web starting obsevation of: %d" % self.i)
        self.write_message(json.dumps({
            'status': 'connecting',
        }))
        self._c.start_observation(self, self.i)

    def on_close(self):
        logging.info("Web stopped observing: %d" % self.i)
        self._c.stop_observation(self, self.i)

    def on_message(self, message):
        logging.info("message from {}: {}".format(self.i, message))

    def on_console_close(self):
        logging.info("Observed console closed")

    def on_connection_details(self, hostport, mp3_url):
        logging.info("Sending ssh details to web client")
        self.write_message(json.dumps({
            'status': 'connected',
            'ssh': {
                'host': hostport[0],
                'port': hostport[1],
            },
            'mp3': {
                'url': mp3_url,
            },
        }))
