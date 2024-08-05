import os
import sys
import threading
import time

import lockfile
from daemon import DaemonContext
from socketserver import UnixStreamServer, StreamRequestHandler
import signal

OK_RESPONSE = b"OK"
ERROR_RESPONSE = b"ERROR"


class Server(UnixStreamServer):
    def __init__(self, config_path: str, sock_file: str, log_file: str):
        super().__init__(sock_file, CmdHandler)
        self.config_path = config_path # TODO ipmlement config class
        self.sock_file = sock_file
        self.log_file = log_file
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGHUP, self.reload_config)

    def mock_server(self):
        i = 0
        while True:
            with open(self.log_file, "a") as f:
                f.write(f"Server is running {i}.\n")
            i += 1
            time.sleep(1)

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
            # out = open("/dev/pts/2", "w")
            # sys.stderr = out
            # sys.stdout = out
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

    def _stop(self):
        """Actually stop the server."""
        self.shutdown()  # look shutdown method in parent server class
        os.remove(self.sock_file)
        with open(self.log_file, "a") as f:
            f.write("Socket file removed.\n")
        sys.exit(0)


class CmdHandler(StreamRequestHandler):
    def handle(self):
        data = self.request.recv(1024).strip()
        data = data.decode("utf-8")
        with open(self.server.log_file, "a") as f:
            f.write(f"Received command: {data}\n")
        func = getattr(self.server, data, None)
        if func:
            with open(self.server.log_file, "a") as f:
                f.write(f"Executing command: {func}\n")
            func(self)
            self.wfile.write(OK_RESPONSE)
        else:
            self.wfile.write(ERROR_RESPONSE)
        self.wfile.write(b"\n")
