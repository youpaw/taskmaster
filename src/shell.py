import socket
import readline
import json
import sys

from server import BUFFER_SIZE, MSG_ENCODING

class SocketError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(f"Socket error: {self.message}")

class Shell:
    def __init__(self, sock_file: str):
        self.sock_file = sock_file
        # flush stdout
        print(f"Taskmaster shell initiated on {sock_file}")

    def run(self):
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
                cmd = response.get("cmd", None)
                assert status is not int, "Status format unknown"

                if status == 0:
                    if msg:
                        print(msg)
                    if cmd == "stop_server":
                        break
                elif status == 1:
                    print(f"Daemon: {msg}", file=sys.stderr)
                elif status == 2:
                    print(msg, file=sys.stderr)
                else:
                    assert "Unknown status number"

            except SocketError as e:
                print(f"Shell: {e}", file=sys.stderr)
            except (AssertionError, UnicodeDecodeError, json.JSONDecodeError) as e:
                print(f"Shell: Response error: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Shell: Unknown error: {e}", file=sys.stderr)


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

