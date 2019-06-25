#!/usr/bin/env python
import tty
import termios, sys

from tornado.ioloop import IOLoop

import ws



async def main():
    client = ws.Client("ws://localhost:3000/console", 5)
    await client.connect()

if __name__ == "__main__":
    IOLoop.current().add_callback(main)
    IOLoop.current().start()
