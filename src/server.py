import os
import time

import lockfile
from daemon import DaemonContext
from socketserver import UnixStreamServer, StreamRequestHandler

OK_RESPONSE = b"OK"
ERROR_RESPONSE = b"ERROR"


class Server(UnixStreamServer):
    def __init__(self, config_path: str, sock_file: str, log_file: str, pid_file: str):
        # UnixStreamServer.__init__(self, sock_file, CmdHandler)
        # Daemon.__init__(self, pid_file)
        # self.config_path = config_path
        # self.log_file = log_file
        # self.pid_file_path = pid_file
        # super().__init__(sock_file, CmdHandler)
        self.log_file = log_file
        self.context = DaemonContext()
        print(f"Inited server with config: {config_path}, log: {log_file}, pid: {pid_file}")

    def run(self):
        pid = os.fork()
        if pid > 0:
            print("Parent process")
        else:
            self._run()

    def _run(self):
        i = 0
        while True:
            with open(self.log_file, "a+") as f:
                f.write(f"Daemon with pid {os.getpid()} running for {i} seconds\n")
            time.sleep(1)
            i += 1


class CmdHandler(StreamRequestHandler):
    def handle(self):
        with open(self.server.log_file, "a") as f:
            f.write(f"Connected...\n")
        self.wfile.write(b"OK\n")
