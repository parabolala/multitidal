#!/usr/bin/env python
import tornado.ioloop
import tornado.web

from tornado.options import define, options

from . import server_lib

define('port', default=3000, help='run on the given port', type=int)


def main():
    tornado.options.parse_command_line()
    app = server_lib.Application()
    app.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    main()
