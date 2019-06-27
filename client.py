#!/usr/bin/env python
from tornado.ioloop import IOLoop

import client_lib



async def main():
    client = client_lib.Client("ws://localhost:3000/console", 5)
    await client.connect()

if __name__ == "__main__":
    IOLoop.current().add_callback(main)
    IOLoop.current().start()
