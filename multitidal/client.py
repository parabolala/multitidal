#!/usr/bin/env python
from tornado.ioloop import IOLoop

from multitidal import client_lib


async def main():
    client = client_lib.Client("ws://192.168.1.9:3000/console", 5)
    await client.connect()


if __name__ == "__main__":
    IOLoop.current().add_callback(main)
    IOLoop.current().start()
