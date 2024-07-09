import os

import lockfile
from daemon import DaemonContext
from socketserver import UnixStreamServer, StreamRequestHandler

OK_RESPONSE = b"OK"
ERROR_RESPONSE = b"ERROR"


class Server(UnixStreamServer):
    def __init__(self, config_path: str, sock_file: str, log_file: str, pid_file: str):
        super().__init__(sock_file, CmdHandler)
        self.config_path = config_path
        self.log_file = log_file
        self.pid_file_path = pid_file
        # self.context = DaemonContext(
        #     pidfile=pid_file, #signal_map={signal.SIGTERM: self.shutdown}
        # )
        print(f"Inited server with config: {config_path}, log: {log_file}, pid: {pid_file}")

    @classmethod
    def start_daemon(cls, *args, **kwargs):
        server = cls(*args, **kwargs)
        print(f"Demonizing server. New pid: {os.getpid()}")
        # server.context.open()
        server.serve_forever()


class CmdHandler(StreamRequestHandler):
    def handle(self):
        with open(self.server.log_file, "a") as f:
            f.write(f"Connected...\n")
        self.wfile.write(b"OK\n")
