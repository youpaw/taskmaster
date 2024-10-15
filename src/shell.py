import time
import socket
import readline
import json
import sys

from server import BUFFER_SIZE, MSG_ENCODING
from server import Server

RED_COLOR = "\033[31m"
RESET_COLOR = "\033[0m"

def print_err(s):
    print(f"{RED_COLOR}{s}{RESET_COLOR}", file=sys.stderr)

class Completer:
    def __init__(self):
        self.commands = Server.commands_info
        self.tasks = []

    def update_tasks(self, tasks: list):
        self.tasks = tasks

    def complete(self, text, state):
        tokens = readline.get_line_buffer().split()
        options = []
        if len(tokens) == 1 and text:
            options = [cmd for cmd in self.commands.keys() if cmd.startswith(text)]
        elif len(tokens) > 1 and tokens[0] in self.commands:
            cmd = self.commands[tokens[0]]
            if cmd.get("args"):
                options = [task for task in self.tasks if task.startswith(text)]
        try:
            return options[state]
        except IndexError:
            return None

class SocketError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(f"Socket error: {self.message}")

class Shell:

    def __init__(self, sock_file: str):
        self.sock_file = sock_file
        self.completer = Completer()
        readline.parse_and_bind("tab: complete")
        readline.set_completer(self.completer.complete)
        # flush stdout
        print(f"Taskmaster shell initiated on {sock_file}")


    def _update_tasks(self):
        try:
            data = self._send_request("_service_get_tasks")
            response = json.loads(data.decode(MSG_ENCODING))
            self.completer.update_tasks(response.get("tasks", []))
        except Exception as e:
            print_err(f"Shell: update_tasks service error: {e}")

    def run(self):
        time.sleep(1) # Wait for the server to init
        self._update_tasks()
        while True:
            cmd_input = self._input("tm> ")
            if cmd_input == "exit":
                print("\nExiting shell...")
                break
            try:
                data = self._send_request(cmd_input)
                response = json.loads(data.decode(MSG_ENCODING))
                status = response.get("status", None)
                msg = response.get("msg", None)
                cmd = response.get("command", None)
                assert status is not int, "Status format unknown"

                if status == 0:
                    if msg:
                        print(msg)
                    if cmd == "stop_server":
                        break
                    elif cmd == "reload":
                        self._update_tasks()
                elif status == 1:
                    print_err(f"Daemon: {msg}")
                elif status == 2:
                    print(msg, file=sys.stderr)
                else:
                    assert "Unknown status number"

            except SocketError as e:
                print_err(f"Shell: {e}")
            except (AssertionError, UnicodeDecodeError, json.JSONDecodeError) as e:
                print_err(f"Shell: Response error: {e}")
            except Exception as e:
                print_err(f"Shell: Unknown error: {e}")


    def _send_request(self, request: str):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(self.sock_file)
                s.sendall(request.encode(MSG_ENCODING))
                return s.recv(BUFFER_SIZE, )
        except (FileNotFoundError, ConnectionError, socket.timeout, socket.gaierror) as e:
            raise SocketError(e)

    @staticmethod
    def _input(prompt):
        while True:
            try:
                line = input(prompt)
            except (KeyboardInterrupt, EOFError):
                return "exit"
            if not line.strip():
                continue
            return line

