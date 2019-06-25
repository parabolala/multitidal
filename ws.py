import sys, tty, termios
import logging
import tornado.websocket
import json

from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.websocket import websocket_connect


class MainHandler(tornado.websocket.WebSocketHandler):
    i = 0

    def initialize(self, app):
        self._app = app

    def open(self):
        MainHandler.i += 1
        self.i = MainHandler.i

        logging.info("A console connected: %d" % self.i)
        self._app.add_session(self)
        sessions = self._app.get_sessions()
        print(sessions)
        self.write_message({'sessions': sessions})

    def on_close(self):
        logging.info("A client disconnected: %d" % self.i)
        self._app.remove_session(self)

    def on_message(self, message):
        logging.info("message from {}: {}".format(self.i, message))



class Client(object):
    def __init__(self, url, timeout):
        self.url = url
        self.timeout = timeout
        self.ioloop = IOLoop.instance()
        self.ws = None
        self.mode = termios.tcgetattr(sys.stdin.fileno())
        PeriodicCallback(self.keep_alive, 20000).start()

    async def connect(self):
        print("trying to connect")
        try:
            self.ws = await websocket_connect(self.url)
        except Exception as e:
            print(f"connection error: {str(e)}")
        else:
            print("connected")
            await self.run()

    async def finish(self):
        if self.ws:
            self.ws.close()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.mode)
        self.ioloop.stop()

    async def run(self):
        fn = sys.stdin.fileno()
        inp = tornado.iostream.PipeIOStream(fn)

        async def send_keys():
            while True:
                try:
                    content = await inp.read_bytes(100, partial=True)
                except tornado.iostream.StreamClosedError:
                    await self.finish()
                    return
                print('stdin: %s' % content, end="\r\n")
                if content[0] == 3 or not content: # CTRL-C
                    await self.finish()
                    return
                else:
                    self.ioloop.add_callback(
                        self.ws.write_message,
                        json.dumps({
                        'keystrokes': [int(x) for x in content],
                    }))

        self.ioloop.add_callback(send_keys)
        try:
            tty.setraw(fn)
            while True:
                msg = await self.ws.read_message()
                if msg is None:
                    print("connection closed")
                    self.ws = None
                    self.ioloop.remove_handler(sys.stdin)
                    break
                else:
                    print("got msg: %s" % msg, end="\r\n")
        finally:
            self.finish()

    def keep_alive(self):
        if self.ws is None:
            self.connect()
        else:
            self.ws.write_message("keep alive")
