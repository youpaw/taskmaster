import os
import sys
import threading
import time

import lockfile
from daemon import DaemonContext
from socketserver import UnixStreamServer, StreamRequestHandler
from configuration import Configuration
import signal
import json

BUFFER_SIZE = 1024
MSG_ENCODING = 'utf-8'

class Server(UnixStreamServer):
    def __init__(self, config_path: str, sock_file: str, log_file: str):
        super().__init__(sock_file, CmdHandler)
        self.config = Configuration(config_path)
        # self.monitor = Monitor(self.config)
        self.sock_file = sock_file
        self.log_file = log_file
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGHUP, self.reload_config)

    @classmethod
    def run_in_background(cls, config_path: str, sock_file: str, log_file: str, pid_file: str):
        """Start the server in the background."""
        pid = os.fork()
        if pid > 0:
            # Parent process.
            print(f"Server started in the background at {time.ctime()}.")
            return
        # Child process.
        with DaemonContext(
            pidfile=lockfile.FileLock(pid_file) # TODO idk about lockfile, it's from doc. Check it.
        ):
            # uncomment to redirect stdout and stderr to a current terminal
            out = open("/dev/pts/0", "w")
            sys.stderr = out
            sys.stdout = out
            with open(log_file, "a") as f:
                f.write(f"Server started at {time.ctime()}.\n")
            server = cls(config_path, sock_file, log_file)
            server.serve_forever()
            with open(log_file, "a") as f:
                f.write(f"Server stopped at {time.ctime()}.")

    def stop(self, signum=None, frame=None):
        """Stop the server."""
        threading.Thread(target=self._stop).start()  # look shutdown method in base class

    def reload_config(self, signum=None, frame=None):
        """Reload the configuration."""
        with open(self.log_file, "a") as f:
            f.write("Reloading the configuration.\n")

    def status(self):
        """Show the status of programs."""
        pass

    def _stop(self):
        """Actually stop the server."""
        self.shutdown()  # look shutdown method in parent server class
        os.remove(self.sock_file)
        with open(self.log_file, "a") as f:
            f.write("Socket file removed.\n")
        sys.exit(0)


class CmdHandler(StreamRequestHandler):
    def validate_command(self, cmd: str):
        pass

    def handle(self):
        data = self.request.recv(BUFFER_SIZE).strip()
        cmd_data = json.loads(data.decode(MSG_ENCODING))
        with open(self.server.log_file, "a") as f:
            f.write(f"Received command: {cmd_data}\n")
        func = getattr(self.server, cmd_data["cmd"], None)
        if func:
            with open(self.server.log_file, "a") as f:
                f.write(f"Executing command: {func}\n")
            msg = func(self)
            resp_data = {"msg": msg, "status": 0}
        else:
            resp_data = {"msg": "command not found", "status": 1}
        json_resp = json.dumps(resp_data)
        self.wfile.write(json_resp.encode(MSG_ENCODING))
