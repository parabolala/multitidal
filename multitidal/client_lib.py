import asyncio
import json
import os
import pty
import shutil
import sys
import tty
import termios
import time
import threading

import tornado.iostream
from tornado.ioloop import IOLoop
from tornado.websocket import websocket_connect

ioloop = tornado.ioloop.IOLoop.instance()


SSH_LOGIN = 'root'
SSH_PASSWORD = 'algorave'

SCREEN_TO_SCREEN_0_SEQ = b'ls -l\r\x1bOC' + b'\x010'  # ^A 0


async def send_stdin_to_ws_task(ws, on_finish_cb):
    print('mangling terminal')
    try:
        fn = os.dup(sys.stdin.fileno())
        inp = tornado.iostream.PipeIOStream(fn)
        mode = termios.tcgetattr(sys.stdin.fileno())
        tty.setraw(fn)
        while True:
            try:
                print('reading stdin', end='\r\n')
                content = await inp.read_bytes(100, partial=True)
                print('read stdin', end='\r\n')
            #    content = await self.inp.read_bytes(100, partial=True)
            except tornado.iostream.StreamClosedError:
                print('Stdin closed', end='\r\n')
                # await self.finish()
                ioloop.add_callback(on_finish_cb)
                break
            print('stdin: %s' % content, end='\r\n')
            if content[0] == 3 or not content:  # CTRL-C
                print('Got a ^C', end='\r\n')
                ioloop.add_callback(on_finish_cb)
                break
            else:
                ioloop.add_callback(
                    ws.write_message,
                    json.dumps({
                        'client_command': 'keystrokes',
                        'keystrokes': [int(x) for x in content],
                    }))
        print('no exc', end='\r\n')
    except asyncio.CancelledError:
        print('stdin read task cancelled', end='\r\n')
    except Exception as e:  # pylint: disable=broad-except
        print('Exception: %s' % e)
    finally:
        inp.close()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, mode)
        print('finally')


async def run_ssh(host, port, login=SSH_LOGIN, password=SSH_PASSWORD):
    os.environ['SSHPASS'] = password
    ssh_cmd = [
        'ssh',
        '-o', 'PreferredAuthentications=password',
        '-o', 'PubkeyAuthentication=no',
        '-o', 'StrictHostKeyChecking=no',  # Skip fingerpint warning.
        '%s@%s' % (login, host), '-p', str(port)]
    sshpass_cmd = [shutil.which('sshpass'), '-e'] + ssh_cmd
    args = sshpass_cmd
    print(' '.join(args))

    stdin_buf=b''
    e = threading.Event()
    master_buf =b''
    def stdin_read(fd):
        if not e.is_set():
            e.set()
            return SCREEN_TO_SCREEN_0_SEQ + os.read(fd, 1024)

        #nonlocal stdin_buf
        b = os.read(fd, 1024)
        #stdin_buf += b
        return b
    def master_read(fd):
        #nonlocal master_buf
        b = os.read(fd, 1024)
        #master_buf += b
        return b
    # Let Web UI connect to screen 0 first.
    time.sleep(3)
    res = pty.spawn(args, master_read=master_read, stdin_read=stdin_read)
    #sys.stdout.write("master:\n%s\n"% master_buf)
    #sys.stdout.write("stdin:\n%s\n"% stdin_buf)
    #sys.stdout.flush()
    print('ssh returned %s' % res)


class Client:
    mode: str

    def __init__(self, url, timeout):
        self.url = url
        self.timeout = timeout
        self.ioloop = IOLoop.instance()
        self.ws = None

        self.send_stdin_task = None

    async def connect(self):
        print('trying to connect')
        try:
            self.ws = await websocket_connect(self.url)
        except Exception as e:  # pylint: disable=broad-except
            print(f'connection error: {str(e)}')
        else:
            print('connected')
            # await self.ws.write_message({'client': self.i})
            self.mode = 'idle'
            self.ioloop.spawn_callback(self.run_idle)
            self.ioloop.spawn_callback(self.run)

    def finish_ws(self):
        if self.ws:
            self.ws.close()
            self.ws = None

    async def finish(self):
        if self.send_stdin_task:
            await self.stop_idle()

        self.finish_ws()
        self.ioloop.stop()

    async def run_idle(self):
        assert not self.send_stdin_task
        print('running idle, spawning task')
        self.send_stdin_task = asyncio.create_task(
            send_stdin_to_ws_task(self.ws, self.finish))

    async def stop_idle(self):
        assert self.send_stdin_task
        self.send_stdin_task.cancel()
        await self.send_stdin_task
        self.send_stdin_task = None

    async def run_ssh(self, host, port):
        # Blocks ioloop
        await run_ssh(host, port)

    async def run(self):
        while True:
            msg = await self.ws.read_message()
            if msg is None:
                print('server left, terminating', end='\r\n')
                self.ioloop.add_callback(self.finish)
                return

            msg = json.loads(msg)
            print('got msg: %s' % msg, end='\r\n')
            if 'mode' not in msg:
                continue
            if msg['mode'] == 'ssh':
                host, port = msg['ssh']['host'], msg['ssh']['port']
                print('Connecting to ssh %s:%s...' %
                      (host, port), end='\r\n')
                await self.stop_idle()
                await self.run_ssh(host, port)
                print('restarting idle task')
                self.finish_ws()
                await self.connect()
                break
                #self.ioloop.spawn_callback(self.run_idle)
                #print('restarted idle task')
