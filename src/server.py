import os
import threading
import shlex
import getopt

import atexit

from daemon import DaemonContext
from socketserver import UnixStreamServer, StreamRequestHandler
import signal
import json
import logging
import logging.config

from configuration import Configuration
from monitor import Monitor

BUFFER_SIZE = 1024
MSG_ENCODING = 'utf-8'


def clean_up(*files):
    for file in files:
        if os.path.exists(file):
            os.remove(file)


class Server(UnixStreamServer):
    commands_info = {
        "start": {
            "help": "Start tasks",
            "options": ["all", "help"],
            "args": "+",
            "usage": "Usage: start <task_list | option>\n\n"
                     "Start provided tasks.\n"
        },
        "stop": {
            "help": "Stop tasks",
            "options": ["all", "help"],
            "args": "+",
            "usage": "Usage: stop <task_list | option>\n\n"
                     "Stop provided tasks.\n"
        },
        "restart": {
            "help": "Restart tasks",
            "options": ["all", "help"],
            "args": "+",
            "usage": "Usage: restart <task_list | option>\n\n"
                     "Restart provided tasks.\n",
    },
        "status": {
            "help": "Show the status of tasks",
            "options": ["help"],
            "args": "*",
            "usage": "Usage: status [task_list | option]\n\n"
                     "Show status for the provided tasks.\n"
                     "Shows status for all tasks in case no tasks were provided.\n",
        },
        "reload": {
            "help": "Reload the configuration",
            "options": ["help"],
        },
        "stop_server": {
            "help": "Stop the server",
            "options": ["help"],
        },
        "help": {
            "help": "Show the available commands",
        },
    }

    options_info = {
        "all": "Execute for all tasks",
        "help": "Show this message",
    }
    # Default logging configuration with disabled loggers
    default_log_config = {
        "version": 1,
        "disable_existing_loggers": True,
        "loggers": {
            "Server": {
                "disabled": True
            },
            "Monitor": {
                "disabled": True
            },
            "Shell": {
                "disabled": True
            },
        },
    }

    def __init__(self, config_path: str, sock_file: str, log_config_file: str, pid_file: str):
        """Initialize the server."""
        super().__init__(sock_file, CmdHandler)
        self.config_path = config_path
        self.sock_file = sock_file
        self.log_config_file = log_config_file
        self.logger = None
        self.pid_file = pid_file
        self.configuration = None
        self.monitor = None

    def startup(self):
        """Load the configuration and monitor."""
        if self.log_config_file:
            logging.config.fileConfig(self.log_config_file, disable_existing_loggers=True)
        else:
            logging.config.dictConfig(self.default_log_config)
        self.logger = logging.getLogger("Server")
        signal.signal(signal.SIGTERM, self.stop_server)
        signal.signal(signal.SIGHUP, self.reload)
        self.configuration = Configuration(self.config_path)
        self.monitor = Monitor(self.configuration)
        self.monitor.reload_config()
        atexit.register(clean_up, self.pid_file, self.sock_file)
        self.logger.info("Server startup succeeded.")

    def service_actions(self):
        """Update the status of programs."""
        self.monitor.update()
        self.logger.debug("Service actions performed.")

    @classmethod
    def start_in_background(cls, config_path: str, sock_file: str, log_file: str, pid_file: str):
        """Start the server in the background."""
        pid = os.fork()
        if pid > 0:
            # Parent process.
            return
        # Child process.
        with DaemonContext(detach_process=False):
            if os.path.exists(pid_file):
                raise ValueError("Server is already running.")
            # uncomment to redirect stdout and stderr to a current terminal
            with cls(config_path, sock_file, log_file, pid_file) as server:
                server.startup()
                server.serve_forever()

    # Server commands which can be sent via the socket

    def start(self, tasks: list[str], all_tasks=False):
        """Start a program."""
        self.logger.debug(f"Starting tasks: {tasks}")
        for name in tasks:
            self.monitor.start_by_name(name)

    def stop(self, tasks: list[str], all_tasks=False):
        """Stop a program."""
        self.logger.debug(f"Stopping tasks: {tasks}")
        for name in tasks:
            self.monitor.stop_by_name(name)

    def restart(self, tasks: list[str], all_tasks=False):
        """Restart a program."""
        self.logger.debug(f"Restarting tasks: {tasks}")
        for name in tasks:
            self.monitor.restart_by_name(name)

    def stop_server(self, signum=None, frame=None):
        """Stop the server."""
        self.logger.info("Stopping server.")
        def _stop():
            """Actually stop the server."""
            self.shutdown()  # look shutdown method in parent server class

        threading.Thread(target=_stop).start()  # Check shutdown method in base class
        return "Server stopped."

    def reload(self, signum=None, frame=None):
        """Reload the configuration."""
        self.logger.info("Reloading configuration.")
        self.monitor.reload_config()
        return "Configuration reloaded."

    def status(self, tasks=()):
        """Show the status of programs."""
        self.logger.debug("Getting status.")
        status_msg = "Programs status:\n"
        for name, task in self.monitor.tasks.items():
            status_msg += f"  {name}: {task.status}\n"
        return status_msg


class CmdHandler(StreamRequestHandler):

    logger = logging.getLogger("CmdHandler")

    @staticmethod
    def format_help(cmd):
        if cmd == "help":
            msg = ("Usage: <command> [options] [<args>]\n\n"
                   "Available commands:\n")
            for cmd, info in Server.commands_info.items():
                msg += f"  {cmd:<11}  {info['help']}\n"
            return msg
        cmd_info = Server.commands_info[cmd]
        msg = Server.commands_info[cmd].get("usage", f"Usage: {cmd} [option]\n\n"
                                                     f"{cmd_info['help']}\n")
        msg += "\nOptions:\n"
        for opt in cmd_info["options"]:
            msg += f"  --{opt:<4}  {Server.options_info[opt]}\n"
        return msg


    @staticmethod
    def parse_args(tokens):
        if not tokens:
            raise ValueError("Parser: Input command is empty")
        cmd = tokens[0]
        if cmd not in Server.commands_info:
            raise ValueError(f"Parser: Unknown command '{cmd}'")
        arg_tokens = tokens[1:] if len(tokens) > 1 else []
        cmd_options = Server.commands_info[cmd].get("options", [])
        try:
            opts, args = getopt.getopt(arg_tokens, "", cmd_options)
        except getopt.GetoptError as e:
            raise ValueError(f"Parser: {e}")
        cmd_args = Server.commands_info[cmd].get("args", None)
        if args:
            if cmd_args is None:
                raise ValueError(f"Parser: {cmd}: Doesn't accept any arguments")
            if opts:
                raise ValueError(f"Parser: {cmd}: Only task list or an option can be specified")
            args = [args]
        elif cmd_args == "+" and not opts:
            raise ValueError(f"Parser: {cmd}: Task list or an option expected")
        elif len(opts) > 1:
            raise ValueError(f"Parser: {cmd}: Only one option can be provided")
        help_on = False
        for option, value in opts:
            if option == "--all":
                args = [[], True]
            elif option == "--help":
                help_on = True
            else:
                raise ValueError(f"Parser: {cmd}: Unknown option '{option}'")
        return cmd, args, help_on

    def send_response(self, msg, success):
        status = 0 if success else 1
        response = {"msg": f"{msg}", "status": status}
        self.wfile.write(json.dumps(response).encode(MSG_ENCODING))

    def handle(self):
        data = self.request.recv(BUFFER_SIZE).decode(MSG_ENCODING)
        try:
            cmd_name, args, help_on = self.parse_args(shlex.split(data))
        except Exception as e:
            return self.send_response(e, False)

        if help_on or cmd_name == "help":
            return self.send_response(self.format_help(cmd_name), True)

        cmd = getattr(self.server, cmd_name, None)
        if cmd is None:
            return self.send_response(f"CmdHandler: '{cmd_name}' command not found", False)

        try:
            message = cmd(*args)
            self.send_response(message, True)
        except Exception as e:
            self.send_response(e, False)
