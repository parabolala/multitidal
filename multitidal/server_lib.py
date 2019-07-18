import abc
import json
import logging
import os.path

import tornado.websocket
import tornado.template

from . import instance_manager


class Error(Exception):
    pass


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

    def on_keystrokes(self, keyboard_id):
        for list_watcher in self._list_watchers:
            list_watcher.on_keystrokes(keyboard_id)

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
        self._sc = SessionsController(self._instance_manager)
        base_path = os.path.dirname(os.path.abspath(__file__))
        settings = dict(
            debug=True,
            template_path=os.path.join(base_path, 'templates'),
            static_path=os.path.join(base_path, 'media'),
        )
        handlers = [
            (r"/console", KeyboardHandler, dict(
                c=c, im=self._instance_manager, sc=self._sc)),
            (r"/", IndexHandler),
            (r"/list", ListHandler, dict(sc=self._sc)),
            (r"/watch_list", WatchListHandler, dict(sc=self._sc)),
            (r"/observe(?:/(\d+))?", ObserveHandler, dict(c=c, sc=self._sc)),
            (r"/media/(.*)", tornado.web.StaticFileHandler,
             dict(path=settings['static_path'])),
        ]
        tornado.web.Application.__init__(self, handlers, **settings)
        tornado.autoreload.add_reload_hook(self.stop)

    def stop(self):
        self._c.stop()
        self._sc.stop()


class SessionObserver(abc.ABC):

    @abc.abstractmethod
    def on_session_state_change(self, session, state):
        raise NotImplementedError()


class KeyboardHandler(tornado.websocket.WebSocketHandler, SessionObserver):
    i = 0
    _c: Controller
    _instance: instance_manager.MusicBox
    _instance_manager: instance_manager.InstanceManager
    _session = None

    def check_origin(self, origin):
        return True

    def initialize(self, c, im, sc):
        self._c = c
        self._instance_manager = im
        self._instance = None
        self._sc = sc

    def open(self):  # pylint: disable=arguments-differ
        self.__class__.i += 1
        self.i = self.__class__.i

        logging.info("A keyboard connected: %d", self.i)
        #self._c.add_session(self)
        #sessions = self._c.list_sessions()
        #print(sessions)
        #self.write_message({'sessions': sessions})
        self._session = self._sc.keyboard_connected(self)

    def on_close(self):
        logging.info("A keyboard disconnected: %d", self.i)
        #self._c.remove_session(self)
        #if self._instance:
        #    self.stop_session()
        self._sc.keyboard_disconnected(self)

    def on_message(self, message):
        logging.info("message from %s: %s", self.i, message)
        msg = json.loads(message)
        if msg['client_command'] == 'keystrokes':
            self._sc.on_keystrokes(self._session)

#    def get_mp3_url(self):
#        return 'http://%s:%s/stream.mp3' % (
#            self._instance.hostname,
#            self._instance.mp3_port,
#        )
#
#    def get_ssh_url(self):
#        return ('http://{webssh_host}:{webssh_port}/'
#                'ssh/host/{target_host}?port={target_port}').format(
#                    webssh_host='localhost',
#                    webssh_port=self._instance.webssh_port,
#                    target_host=self._instance.tidal_container.
#                    attrs['Config']['Hostname'],
#                    target_port='22',
#                )
#
#    def get_ssh_hostport(self):
#        return (self._instance.hostname, self._instance.ssh_port)

    def on_session_state_change(self, session, state):
        if state == Session.RUNNING:
            host, port = session.get_ssh_hostport()
            self.write_message(json.dumps({
                'mode': 'ssh',
                'ssh': {
                    'host': host,
                    'port': port,
                },
                'audio': session.get_mp3_url(),
            }))
        else:
            self.write_message(json.dumps({
                'mode': 'idle',
            }))


#    def start_session(self):
#        logging.info("Starting container")
#        instance = self._instance_manager.start_one(
#            hostname=self.request.host_name)
#        self._instance = instance
#        logging.info("Connecting console to ssh")
#        self.write_message(json.dumps({
#            'mode': 'ssh',
#            'ssh': {
#                'host': socket.gethostbyname(instance.hostname),
#                'port': instance.ssh_port,
#            },
#            'audio': self.get_mp3_url(),
#        }))
#
#    def stop_session(self):
#        logging.info("Disonnecting console from ssh")
#        try:
#            self.write_message(json.dumps({
#                'mode': 'idle',
#            }))
#        except tornado.websocket.WebSocketClosedError:
#            pass
#        logging.info("Stopping container")
#        self._instance_manager.stop_instance(self._instance)
#        self._instance = None
#        logging.info("Stopped")



class Session:
    IDLE, STARTING, RUNNING, STOPPING = range(4)

    i = 0

    def __init__(self, keyboard=None):
        self.i = Session.i
        Session.i += 1
        self._observers = []
        self._keyboard = keyboard
        self._state = self.IDLE
        self._musicbox = instance_manager.MusicBox()

    def add_observer(self, observer: SessionObserver):
        self._observers.append(observer)
        observer.on_session_state_change(self, self._state)

    def remove_observer(self, observer):
        self._observers.remove(observer)

    def set_keyboard(self, keyboard: KeyboardHandler):
        self._keyboard = keyboard

    def _change_state(self, new_state):
        self._state = new_state
        for o in self._observers:
            o.on_session_state_change(self, new_state)
        if self._keyboard:
            self._keyboard.on_session_state_change(self, new_state)

    def start(self):
        self._change_state(self.STARTING)
        try:
            self._musicbox.start(hostname='localhost')  # TODO hostname
        except Error:
            self._change_state(self.STOPPING)
            self._change_state(self.IDLE)
            return
        self._change_state(self.RUNNING)

    def stop(self):
        self._change_state(self.STOPPING)
        try:
            self._musicbox.stop()
        finally:
            self._change_state(self.IDLE)

    def get_state(self):
        return self._state

    def has_observers(self) -> bool:
        return len(self._observers) > 0

    def has_keyboard(self):
        return self._keyboard != None

    def get_mp3_url(self):
        return 'http://%s:%s/stream.mp3' % (
            self._musicbox.hostname,
            self._musicbox.mp3_port,
        )

    def get_ssh_url(self):
        return ('http://{webssh_host}:{webssh_port}/'
                'ssh/host/{target_host}?port={target_port}').format(
                    webssh_host='localhost',
                    webssh_port=self._musicbox.webssh_port,
                    target_host=self._musicbox.tidal_container.
                        attrs['Config']['Hostname'],
                    target_port='22',
                )

    def get_ssh_hostport(self):
        return (self._musicbox.hostname, self._musicbox.ssh_port)

    def __del__(self):
        if self._state != self.IDLE:
            logging.warning("Destroying non-idle session")


class SessionsController:
    def __init__(self, _instance_manager):
        self._sessions = {}
        self._keyboard_to_session = {}
        self._observer_to_session = {}

        self._list_watchers = []

    def list_sessions(self):
        return self._sessions.values()

    def add_list_watcher(self, handler):
        self._list_watchers.append(handler)
        for s in self._sessions.values():
            handler.on_session_add(s)

    def remove_list_watcher(self, handler):
        self._list_watchers.remove(handler)

    def on_keystrokes(self, session):
        for w in self._list_watchers:
            w.on_keystrokes(session)

    def add_session(self, session):
        self._sessions[session.i] = session
        for w in self._list_watchers:
            w.on_session_add(session)

    def remove_session(self, session):
        del self._sessions[session.i]
        for w in self._list_watchers:
            w.on_session_remove(session)

    def start_observation(self, observer, session_id) -> Session:
        if session_id is None:
            session = Session()
            self.add_session(session)
        else:
            session = self._sessions[int(session_id)]
        session.add_observer(observer)
        self._observer_to_session[observer] = session
        if session.get_state() == Session.IDLE:
            session.start()
        return session

    def stop_observation(self, observer: SessionObserver):
        session = self._observer_to_session[observer]
        session.remove_observer(observer)
        del self._observer_to_session[observer]
        if not session.has_observers():
            session.stop()
            if not session.has_keyboard():
                del self._sessions[session.i]

    def keyboard_connected(self, keyboard: KeyboardHandler) -> Session:
        session = Session()
        session.set_keyboard(keyboard)
        self.add_session(session)
        self._keyboard_to_session[keyboard] = session
        return session

    def keyboard_disconnected(self, keyboard: KeyboardHandler):
        session = self._keyboard_to_session[keyboard]
        session.set_keyboard(None)
        del self._keyboard_to_session[keyboard]
        if not session.has_observers():
            self.remove_session(session)

    def stop(self):
        for session in self._sessions.values():
            session.stop()
            self.remove_session(session)



class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('index.html')


class ListHandler(tornado.web.RequestHandler):
    _sc: Controller

    def initialize(self, sc):
        self._sc = sc

    def get(self):
        self.write(json.dumps([{
            'id': s.i,
            'kb': s.has_keyboard(),
        }] for s in self._sc.list_sessions()))


class WatchListHandler(tornado.websocket.WebSocketHandler):

    _controller: Controller

    def initialize(self, sc):
        self._sc = sc

    def open(self):  # pylint: disable=arguments-differ
        self._sc.add_list_watcher(self)

    def on_close(self):
        self._sc.remove_list_watcher(self)

    def on_session_remove(self, session):
        self.write_message(json.dumps({
            'command': 'session_remove',
            'session': {
                'id': session.i,
            },
        }))

    def on_session_add(self, session):
        self.write_message(json.dumps({
            'command': 'session_add',
            'session': {
                'id': session.i,
                'kb': session.has_keyboard(),
            },
        }))

    def on_keystrokes(self, session):
        self.write_message(json.dumps({
            'command': 'keystrokes',
            'keystrokes': {
                'session': {
                    'id': session.i,
                },
            },
        }))


class ObserveHandler(tornado.websocket.WebSocketHandler):
    i = 0

    def check_origin(self, origin):
        return True

    def initialize(self, c, sc):
        self._c = c
        self._sc = sc
        self._session = None

    def open(self, session_id=None):  # pylint: disable=arguments-differ
        ObserveHandler.i += 1
        self.i = ObserveHandler.i
        ObserveHandler.i += 1
        msg = "Web %d starting obsevation" % self.i
        if session_id:
            msg += ' of session %s' % session_id
        logging.info(msg)

        try:
            #self._c.start_observation(self, self.i)
            self._sc.start_observation(self, session_id)
        except tornado.web.HTTPError:
            self.write_message(json.dumps({
                'status': 'unknown session',
            }))

    def on_close(self):
        logging.info("Web stopped observing: %d", self.i)
        self._sc.stop_observation(self)

    def on_message(self, message):
        logging.info("message from %s: %s", self.i, message)

    def on_console_close(self):
        logging.info("Observed console closed")
        #self.write_message(json.dumps({
        #    'status': 'disconnected',
        #}))

    def on_session_state_change(self, session, state):
        if state == Session.RUNNING:
            self.on_connection_details(
                session.get_ssh_url(),
                session.get_mp3_url(),
            )
        elif state == Session.STOPPING:
            self.write_message(json.dumps({
                'status': 'disconnected',
            }))
        elif state == Session.STARTING:
            self.write_message(json.dumps({
                'status': 'connecting',
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

