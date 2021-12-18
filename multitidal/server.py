#!/usr/bin/env python
import logging

import docker
import tornado.ioloop
import tornado.web

from tornado.options import define, options

from multitidal import server_lib

define("port", default=3001, help="run on the given port", type=int)


def main():
    try:
        docker.client.from_env().ping()
    except Exception:  # pylint: disable=broad-except
        logging.error("Docker not responding")
        return 1
    tornado.options.parse_command_line()
    app = server_lib.Application()
    app.listen(options.port)
    print(f"Server started at port {options.port}")
    try:
        tornado.ioloop.IOLoop.instance().start()
    except Exception:  # pylint: disable=broad-except
        app.stop()
        raise
    return 0


if __name__ == "__main__":
    main()
