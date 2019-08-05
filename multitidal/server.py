#!/usr/bin/env python
import logging

import docker
import tornado.ioloop
import tornado.web

from tornado.options import define, options

from multitidal import server_lib

define('port', default=3000, help='run on the given port', type=int)


def main():
    try:
        docker.client.from_env().ping()
    except Exception:
        logging.error("Docker not responding")
        return 1
    tornado.options.parse_command_line()
    app = server_lib.Application()
    app.listen(options.port)
    print('Server started')
    try:
        tornado.ioloop.IOLoop.instance().start()
    except Exception:
        app.stop()
        raise


if __name__ == '__main__':
    main()
