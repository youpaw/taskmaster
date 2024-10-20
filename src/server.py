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
from monitor import Monitor, MonitorError
from configuration import ConfigurationError

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

    service_api = [
        "_service_get_tasks",
    ]

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

    def __init__(self, config_path: str, socket_path: str, log_path: str, pid_path: str):
        """Initialize the server."""
        super().__init__(socket_path, CmdHandler)
        self.config_path = config_path
        self.socket_path = socket_path
        self.log_path = log_path
        self.pid_path = pid_path

        self.logger = None
        self.configuration = None
        self.monitor = None

    def startup(self):
        """Load the configuration and monitor."""
        # Register cleanup functions and signal handlers
        atexit.register(clean_up, self.pid_path, self.socket_path)
        signal.signal(signal.SIGTERM, self.stop_server)
        signal.signal(signal.SIGHUP, self.reload)

        # setup logging
        try:
            logging.config.fileConfig(self.log_path, disable_existing_loggers=True)
        except Exception:
            # Something went wrong with the log config,
            # either the file is missing or the config is invalid.
            # Fallback to the default log config.
            # Loggers are disabled by default due to the epsense of stdout/stderr.
            logging.config.dictConfig(self.default_log_config)
        self.logger = logging.getLogger("Server")

        # Setup configuration and monitor
        try:
            self.configuration = Configuration(self.config_path)
        except ConfigurationError as e:
            self.logger.error(f"Configuration error: {e}")
            raise
        self.monitor = Monitor(self.configuration)
        self.monitor.reload_config()

        self.logger.info("Server startup succeeded.")

    def service_actions(self):
        """Update the status of programs."""
        self.monitor.update()

    @classmethod
    def start_in_background(cls, *args, **kwargs):
        """Start the server in the background."""
        # Child process.
        with DaemonContext(working_directory=os.path.curdir):
            with cls(*args, **kwargs) as server:
                server.startup()
                server.serve_forever()

    # Server commands which can be sent via the socket

    def start(self, tasks: list[str], all_tasks=False):
        """Start tasks."""
        msg = ""
        fail_cnt = 0
        if all_tasks:
            tasks = [name for name in self.monitor.active_tasks if self.monitor.tasks[name].is_idle()]
        self.logger.debug(f"Starting tasks: {tasks}")
        for name in tasks:
            try:
                self.monitor.start_by_name(name)
            except MonitorError as e:
                msg += f"  {e}\n"
                fail_cnt += 1
        if fail_cnt:
            msg = f"Failed to start {fail_cnt} out of {len(tasks)} tasks:\n" + msg
            return 2, msg
        msg = f"All {len(tasks)} tasks started successfully"
        return 0, msg

    def stop(self, tasks: list[str], all_tasks=False):
        """Stop tasks."""
        msg = ""
        fail_cnt = 0
        if all_tasks:
            tasks = [name for name in self.monitor.active_tasks if self.monitor.tasks[name].status != "STOPPING"]
        self.logger.debug(f"Stopping tasks: {tasks}")
        for name in tasks:
            try:
                self.monitor.stop_by_name(name)
            except MonitorError as e:
                msg += f"  {e}\n"
                fail_cnt += 1
        if fail_cnt:
            msg = f"Failed to stop {fail_cnt} out of {len(tasks)} tasks:\n" + msg
            return 2, msg
        msg = f"All {len(tasks)} tasks stopped successfully"
        return 0, msg

    def restart(self, tasks: list[str], all_tasks=False):
        """Restart tasks."""
        msg = ""
        fail_cnt = 0
        if all_tasks:
            tasks = [name for name, task in self.monitor.tasks.items() if task.rebooting is False]
        self.logger.debug(f"Restarting tasks: {tasks}")
        for name in tasks:
            try:
                self.monitor.restart_by_name(name)
            except MonitorError as e:
                msg += f"  {e}\n"
                fail_cnt += 1
        if fail_cnt:
            msg = f"Failed to restart {fail_cnt} out of {len(tasks)} tasks:\n" + msg
            return 2, msg
        msg = f"All {len(tasks)} tasks restarted successfully"
        return 0, msg

    def stop_server(self, signum=None, frame=None):
        """Stop the server."""
        self.logger.debug("Stopping server.")
        def _stop():
            """Actually stop the server."""
            self.shutdown()  # look shutdown method in parent server class

        threading.Thread(target=_stop).start()  # Check shutdown method in base class
        return 0, "Server has been stopped"

    def reload(self, signum=None, frame=None):
        """Reload the configuration."""
        self.logger.debug("Reloading configuration.")
        try:
            self.monitor.reload_config()
        except ConfigurationError as e:
            return 1, f"Configuration error: {e}"
        except Exception as e:
            return 1, f"Some error {e}"
        return 0, "Configuration has been reloaded"

    def status(self, tasks=()):
        """Show the status of programs."""
        fail_cnt = 0
        err_msg = ""
        if tasks:
            tasks_dict = {}
            for name in tasks:
                try:
                    tasks_dict[name] = self.monitor.get_task_by_name(name)
                except MonitorError as e:
                    err_msg += f"{e}\n"
                    fail_cnt += 1
            tasks = tasks_dict
        else:
            tasks = self.monitor.tasks
        self.logger.debug(f"Getting status for tasks: {tasks}")
        status_msg = Monitor.format_tasks_status(tasks) if tasks else "No tasks found\n"
        if fail_cnt:
            return 2, status_msg + f"\n{err_msg}"
        return 0, status_msg

    def _service_get_tasks(self):
        return {"tasks": list(self.monitor.tasks.keys())}


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

    def send_response(self, msg, status: int, cmd=None):
        response = {"msg": f"{msg}", "status": status, "command": f"{cmd}"}
        self.wfile.write(json.dumps(response).encode(MSG_ENCODING))

    def _handle_service(self, service_name):
        self.logger.debug(f"CmdHandler: Service action '{service_name}' requested")
        cmd = getattr(self.server, service_name, None)
        if cmd is None:
            self.logger.debug(f"CmdHandler: Service {service_name} does not exist")
            return
        try:
            self.wfile.write(json.dumps(cmd()).encode(MSG_ENCODING))
        except Exception as e:
            self.logger.debug(f"CmdHandler: Service {service_name} error: {e}")

    def handle(self):
        data = self.request.recv(BUFFER_SIZE).decode(MSG_ENCODING)
        if data in Server.service_api:
            return self._handle_service(data)
        try:
            cmd_name, args, help_on = self.parse_args(shlex.split(data))
            self.logger.debug(f"CmdHandler: received command '{cmd_name}' with args: {args} help: '{help_on}'")
        except ValueError as e:
            return self.send_response(e, 1)
        except Exception as e:
            return self.send_response(f"CmdHandler: Unknown exception: {e}", 1)

        if help_on or cmd_name == "help":
            return self.send_response(self.format_help(cmd_name), 0)

        cmd = getattr(self.server, cmd_name, None)
        if cmd is None:
            return self.send_response(f"CmdHandler: '{cmd_name}' command not found", 1)

        try:
            status, message = cmd(*args)
            self.send_response(message.rstrip(), status, cmd_name)
        except Exception as e:
            self.send_response(f"CmdHandler: {cmd_name}: Unknown exception: {e}", 1, cmd_name)
