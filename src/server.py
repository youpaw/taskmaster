import os
import sys
import threading
import time

import atexit
from daemon import DaemonContext
from socketserver import UnixStreamServer, StreamRequestHandler
import signal
import json

from configuration import Configuration
from monitor import Monitor

BUFFER_SIZE = 1024
MSG_ENCODING = 'utf-8'


def clean_up(*files):
    for file in files:
        if os.path.exists(file):
            os.remove(file)


class Server(UnixStreamServer):
    allowed_cmds = ["start", "stop", "restart", "status"]

    def __init__(self, config_path: str, sock_file: str, log_file: str, pid_file: str):
        """Initialize the server."""
        super().__init__(sock_file, CmdHandler)
        self.config_path = config_path
        self.sock_file = sock_file
        self.log_file = log_file
        self.pid_file = pid_file
        self.configuration = None
        self.monitor = None

    def startup(self):
        """Load the configuration and monitor."""
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGHUP, self.reload)
        self.configuration = Configuration(self.config_path)
        self.monitor = Monitor(self.configuration)
        self.monitor.reload_config()
        atexit.register(clean_up, self.pid_file, self.sock_file)

    def service_actions(self):
        """Update the status of programs."""
        self.monitor.update()

    @classmethod
    def start_in_background(cls, config_path: str, sock_file: str, log_file: str, pid_file: str):
        """Start the server in the background."""
        pid = os.fork()
        if pid > 0:
            # Parent process.
            print(f"Server started in the background at {time.ctime()}.")
            return
        # Child process.
        with DaemonContext():
            if os.path.exists(pid_file):
                raise ValueError("Server is already running.")
            # uncomment to redirect stdout and stderr to a current terminal
            out = open("/dev/pts/0", "w")
            sys.stderr = out
            sys.stdout = out
            with open(log_file, "a") as f:
                f.write(f"Server started at {time.ctime()}.\n")

            with cls(config_path, sock_file, log_file, pid_file) as server:
                server.startup()
                server.serve_forever()
            with open(log_file, "a") as f:
                f.write(f"Server stopped at {time.ctime()}.")

    def stop(self, signum=None, frame=None):
        def _stop():
            """Actually stop the server."""
            self.shutdown()  # look shutdown method in parent server class

        """Stop the server."""
        threading.Thread(target=_stop).start()  # look shutdown method in base class

    def reload(self, signum=None, frame=None):
        """Reload the configuration."""
        with open(self.log_file, "a") as f:
            f.write("Reloading the configuration.\n")
        self.monitor.reload_config()

    def status(self):
        """Show the status of programs."""
        return self.monitor.status()


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
