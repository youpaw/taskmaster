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
    allowed_cmds = ["start", "stop", "restart", "status", "reload", "stop_server", "help"]
    commands_info = {
        "start": "Start a program",
        "stop": "Stop a program",
        "restart": "Restart a program",
        "status": "Show the status of programs",
        "reload": "Reload the configuration",
        "stop_server": "Stop the server",
        "help": "Show the available commands"
    }

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

    # Server commands which can be sent via the socket

    def start(self, program_names: list[str]):
        """Start a program."""
        for program_name in program_names:
            self.monitor.start_by_name(program_name)

    def stop(self, program_name: list[str]):
        """Stop a program."""
        for program_name in program_name:
            self.monitor.stop_by_name(program_name)

    def restart(self, program_name: list[str]):
        """Restart a program."""
        for program_name in program_name:
            self.monitor.restart_by_name(program_name)

    def stop_server(self, signum=None, frame=None):
        """Stop the server."""

        def _stop():
            """Actually stop the server."""
            self.shutdown()  # look shutdown method in parent server class

        threading.Thread(target=_stop).start()  # Check shutdown method in base class
        return "Server stopped."

    def reload(self, signum=None, frame=None):
        """Reload the configuration."""
        with open(self.log_file, "a") as f:
            f.write("Reloading the configuration.\n")
        self.monitor.reload_config()
        return "Configuration reloaded."

    def status(self):
        """Show the status of programs."""
        status_msg = "Programs status:\n"
        for name, task in self.monitor.tasks.items():
            status_msg += f"{name}: {task.status}\n"
        return status_msg

    def help(self):
        """Show the available commands."""
        help_msg = "Available commands:\n"
        for cmd in self.allowed_cmds:
            help_msg += f"{cmd}: {self.commands_info.get(cmd, 'No info')}\n"
        return help_msg


class CmdHandler(StreamRequestHandler):

    def parse_request(self, cmd: str) -> tuple or None:
        try:
            cmd_data = json.loads(cmd.decode(MSG_ENCODING))
        except json.JSONDecodeError:
            return None
        if not isinstance(cmd_data, dict):
            return None
        if "cmd" not in cmd_data:
            return None
        if cmd_data["cmd"] not in self.server.allowed_cmds:
            return None
        if "args" not in cmd_data:
            return None
        if not isinstance(cmd_data["args"], list):
            return None
        command = getattr(self.server, cmd_data["cmd"], None)
        if not command:
            return None
        return command, cmd_data["args"]

    def handle(self):
        data = self.request.recv(BUFFER_SIZE).strip()
        parsed_request = self.parse_request(data)
        if not parsed_request:
            response = {"msg": "Invalid command", "status": 1}
            json_response = json.dumps(response)
            self.wfile.write(json_response.encode(MSG_ENCODING))
            return

        command, args = parsed_request
        try:
            message = command(*args)
            response = {"msg": message, "status": 0}
        except Exception as e:
            response = {f"msg": f"An error {e} occurred", "status": 1}

        response_json = json.dumps(response)
        self.wfile.write(response_json.encode(MSG_ENCODING))
