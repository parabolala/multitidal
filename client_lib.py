import json
import sys, tty, termios

import tornado.iostream
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.websocket import websocket_connect

class Client(object):
    def __init__(self, url, timeout):
        self.url = url
        self.timeout = timeout
        self.ioloop = IOLoop.instance()
        self.ws = None
        self.mode = termios.tcgetattr(sys.stdin.fileno())
        self.fn = sys.stdin.fileno()
        self.inp = tornado.iostream.PipeIOStream(self.fn)
        PeriodicCallback(self.keep_alive, 20000).start()

    async def connect(self):
        print("trying to connect")
        try:
            self.ws = await websocket_connect(self.url)
        except Exception as e:
            print(f"connection error: {str(e)}")
        else:
            print("connected")
            #await self.ws.write_message({'client': self.i})
            await self.run()

    async def finish(self):
        if not self.ws:
            self.ws.close()
            self.ws = None
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.mode)
        if self.inp and not self.inp.closed():
            self.inp.close()
            self.inp = None
        self.ioloop.stop()

    async def on_stdin_keys(self):

        while True:
            try:
                content = await self.inp.read_bytes(100, partial=True)
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
                        'client_command': 'keystrokes',
                        'keystrokes': [int(x) for x in content],
                    }))

    async def run(self):
        fn = sys.stdin.fileno()
        self.ioloop.spawn_callback(self.on_stdin_keys)
        try:
            tty.setraw(fn)
            while True:
                msg = await self.ws.read_message()
                if msg is None:
                    print("connection closed", end="\r\n")
                    await self.finish()
                    break
                else:
                    print("got msg: %s" % msg, end="\r\n")
        finally:
            await self.finish()

    async def keep_alive(self):
        if self.ws is None:
            await self.connect()
        else:
            self.ws.write_message("keep alive")
