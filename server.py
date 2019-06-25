
import tornado.ioloop
import tornado.web

from tornado.options import define, options

import ws

define("port", default=3000, help="run on the given port", type=int)


class Application(tornado.web.Application):
    _sessions = []

    def __init__(self):
        handlers = [(r"/console", ws.MainHandler, dict(app=self))]
        settings = dict(debug=True)
        tornado.web.Application.__init__(self, handlers, **settings)

    def get_sessions(self):
        return ['asd', 'qwe']

    def add_session(self, session):
        self._sessions.append(session)

    def remove_session(self, session):
        assert session in self._sessions
        self._sessions.remove(session)




def main():
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
