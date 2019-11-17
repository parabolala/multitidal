import abc
import concurrent.futures
import json
import functools
import logging
import os.path

from tornado.ioloop import IOLoop
import tornado.websocket
import tornado.template

from . import instance_manager


class Error(Exception):
    pass


class Application(tornado.web.Application):

    def __init__(self):
        self._sc = SessionsController()
        base_path = os.path.dirname(os.path.abspath(__file__))
        settings = dict(
            debug=True,
            template_path=os.path.join(base_path, 'templates'),
            static_path=os.path.join(base_path, 'media'),
        )
        handlers = [
            (r"/console", KeyboardHandler, dict(sc=self._sc)),
            (r"/", IndexHandler),
            (r"/list", ListHandler, dict(sc=self._sc)),
            (r"/watch_list", WatchListHandler, dict(sc=self._sc)),
            (r"/observe/(new|\d+)?", ObserveHandler, dict(sc=self._sc)),
            (r"/media/(.*)", tornado.web.StaticFileHandler,
             dict(path=settings['static_path'])),
        ]
        tornado.web.Application.__init__(self, handlers, **settings)
        tornado.autoreload.add_reload_hook(self.stop)

    def stop(self):
        IOLoop.instance().add_callback(self._sc.stop)


class SessionObserver(abc.ABC):

    @abc.abstractmethod
    def on_session_state_change(self, session, state):
        raise NotImplementedError()


class KeyboardHandler(tornado.websocket.WebSocketHandler, SessionObserver):
    i = 0
    _instance: instance_manager.MusicBox
    _session = None

    def check_origin(self, origin):
        return True

    def initialize(self, sc):
        self._instance = None
        self._sc = sc

    def open(self):  # pylint: disable=arguments-differ
        self.__class__.i += 1
        self.i = self.__class__.i

        logging.info("A keyboard connected: %d", self.i)
        self._session = self._sc.keyboard_connected(self)

    def on_close(self):
        logging.info("A keyboard disconnected: %d", self.i)
        self._sc.keyboard_disconnected(self)

    def on_message(self, message):
        logging.info("message from %s: %s", self.i, message)
        msg = json.loads(message)
        if msg['client_command'] == 'keystrokes':
            self._sc.on_keystrokes(self._session)

    def on_session_state_change(self, session, state):
        if state == Session.RUNNING:
            host, port = session.get_ssh_hostport()
            resp = {
                'mode': 'ssh',
                'ssh': {
                    'host': host,
                    'port': port,
                },
                'audio': session.get_mp3_url(),
            }
        else:
            resp = {
                'mode': 'idle',
            }
        logging.info("Sending ssh details to keyboard client: %s" % str(resp))
        self.write_message(json.dumps(resp))


class Session:
    IDLE, STARTING, RUNNING, FAILED, STOPPING = range(5)

    i = 0

    def __init__(self, session_controller, hostname, keyboard=None):
        """Initializes a session object.

        Args:
          session_controller: reference to the parent controller.
          host: Current host name to use for constructing URLs.
          keyboard: Whether this session is initialized by a keyboard client.
        """
        self.i = Session.i
        Session.i += 1
        self._observers = []
        self._keyboard = keyboard
        self._state = self.IDLE
        self._musicbox = instance_manager.MusicBox()
        self._session_controller = session_controller
        self._hostname = hostname

    def add_observer(self, observer: SessionObserver):
        self._observers.append(observer)
        observer.on_session_state_change(self, self._state)

    def remove_observer(self, observer):
        self._observers.remove(observer)

    def set_keyboard(self, keyboard: KeyboardHandler):
        self._keyboard = keyboard
        self._change_state(self._state)

    def _change_state(self, new_state):
        self._state = new_state
        for o in self._observers:
            o.on_session_state_change(self, new_state)
        if self._keyboard:
            self._keyboard.on_session_state_change(self, new_state)
        self._session_controller.on_session_state_change(self, new_state)

    async def start(self):
        self._change_state(self.STARTING)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as e:
                await IOLoop.instance().run_in_executor(
                        e, functools.partial(self._musicbox.start,
                            hostname=self._hostname))
        except (Error, instance_manager.Error) as e:
            self._change_state(self.FAILED)
            raise Error("Failed to start session: %s" % str(e))
        self._change_state(self.RUNNING)

    async def stop(self):
        self._change_state(self.STOPPING)
        try:
            #self._musicbox.stop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as e:
                await IOLoop.instance().run_in_executor(
                        e, self._musicbox.stop)
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
                    webssh_host=self._hostname,
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

    def to_dict(self):
        state_map = ['idle', 'starting', 'running', 'failed', 'stopping']
        return {
            'id': self.i,
            'state': state_map[self._state],
            'kb': self.has_keyboard(),
        }


class SessionsController:
    def __init__(self):
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

    def on_session_state_change(self, session, state):
        for w in self._list_watchers:
            w.on_session_state_change(session, state)

    async def start_observation(self, observer, session_id) -> Session:
        if session_id is None:
            session = Session(self, hostname=observer.request.host.split(':')[0])
            self.add_session(session)
        else:
            session = self._sessions[int(session_id)]
        session.add_observer(observer)
        self._observer_to_session[observer] = session
        if session.get_state() == Session.IDLE:
            await session.start()
        return session

    async def stop_observation(self, observer: SessionObserver):
        session = self._observer_to_session[observer]
        session.remove_observer(observer)
        del self._observer_to_session[observer]
        if not session.has_observers():
            await session.stop()
            if not session.has_keyboard():
                self.remove_session(session)

    def keyboard_connected(self, keyboard: KeyboardHandler) -> Session:
        session = Session(self, hostname=keyboard.request.host.split(':')[0])
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

    async def stop(self):
        for session in list(self._sessions.values()):
            await session.stop()
            self.remove_session(session)



class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('index.html')


class ListHandler(tornado.web.RequestHandler):
    _sc: SessionsController

    def initialize(self, sc):
        self._sc = sc

    def get(self):
        self.write(json.dumps([{
            'id': s.i,
            'kb': s.has_keyboard(),
        }] for s in self._sc.list_sessions()))


class WatchListHandler(tornado.websocket.WebSocketHandler):

    def initialize(self, sc):
        self._sc = sc

    def open(self):  # pylint: disable=arguments-differ
        self._sc.add_list_watcher(self)

    def on_close(self):
        self._sc.remove_list_watcher(self)

    def on_session_remove(self, session):
        self.write_message(json.dumps({
            'command': 'session_remove',
            'session': session.to_dict(),
        }))

    def on_session_add(self, session):
        self.write_message(json.dumps({
            'command': 'session_add',
            'session': session.to_dict(),
        }))

    def on_session_state_change(self, session, state):
        self.write_message(json.dumps({
            'command': 'session_state',
            'session': session.to_dict(),
        }))

    def on_keystrokes(self, session):
        self.write_message(json.dumps({
            'command': 'keystrokes',
            'keystrokes': {
                'session': session.to_dict(),
            },
        }))


class ObserveHandler(tornado.websocket.WebSocketHandler):
    i = 0

    def check_origin(self, origin):
        return True

    def initialize(self, sc):
        self._sc = sc
        self._session = None

    async def _start_observation(self, session_id):
        try:
            await self._sc.start_observation(self, session_id)
        except tornado.web.HTTPError:
            self.write_message(json.dumps({
                'status': 'unknown session',
            }))
        except Error as e:
            logging.error("Failed to start observation: %s" % str(e))

    def open(self, session_id):  # pylint: disable=arguments-differ
        self.i = ObserveHandler.i
        ObserveHandler.i += 1
        msg = "Web %d starting observation" % self.i
        if session_id != 'new':
            msg += ' of session %s' % session_id
        logging.info(msg)

        if session_id == 'new':
            session_id = None
        IOLoop.instance().add_callback(self._start_observation, session_id)

    def on_close(self):
        logging.info("Web stopped observing: %d", self.i)
        IOLoop.instance().add_callback(self._sc.stop_observation, self)

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
                session,
                session.get_ssh_url(),
                session.get_mp3_url(),
            )
        elif state == Session.STOPPING:
            self.write_message(json.dumps({
                'id': session.i,
                'status': 'disconnected',
            }))
        elif state == Session.STARTING:
            self.write_message(json.dumps({
                'id': session.i,
                'session': session.to_dict(),
                'status': 'connecting',
            }))
        elif state == Session.FAILED:
            self.write_message(json.dumps({
                'id': session.i,
                'status': 'error',
            }))
            self.close()
        elif state == Session.IDLE:
            pass
        else:
            logging.error("Unexpected session state in WS handler: %s",
                          state)


    def on_connection_details(self, session, ssh_url, mp3_url):
        resp = {
            'status': 'connected',
            'ssh': {
                'url': ssh_url,
            },
            'mp3': {
                'url': mp3_url,
            },
            'session': session.to_dict(),
        }
        logging.info("Sending ssh details to web client: %s" % str(resp))
        self.write_message(json.dumps(resp))

