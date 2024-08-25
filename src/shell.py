import socket
import readline
import shlex
import json
import sys

from server import BUFFER_SIZE, MSG_ENCODING

class SocketError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(f"socket error: {self.message}")

class Shell:
    def __init__(self, sock_file: str):
        self.sock_file = sock_file
        # flush stdout
        print(f"Taskmaster shell initiated on {sock_file}")

    def run(self):
        while True:
            tokens = self._token_input("tm> ")
            cmd = tokens[0].lower()
            if cmd == "exit":
                print("\nExiting shell...")
                break
            args = tokens[1:] if len(tokens) > 1 else []
            try:
                response = self._send_command({"cmd": cmd, "args": args})
                if response["status"]:
                    print(f'daemon: {response["msg"]}: {cmd}', file=sys.stderr)
                elif response["msg"]:
                    print(response["msg"])
                else:
                    print(f"{cmd} success", file=sys.stderr)
            except SocketError as e:
                print(e, file=sys.stderr)

    def _send_command(self, cmd_data: dict) -> dict:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(self.sock_file)
                json_cmd = json.dumps(cmd_data)
                s.sendall(json_cmd.encode(MSG_ENCODING))
                data = s.recv(BUFFER_SIZE, )
                return json.loads(data.decode(MSG_ENCODING))
        except (FileNotFoundError, ConnectionError, socket.timeout, socket.gaierror) as e:
            raise SocketError(e)

    @staticmethod
    def _token_input(prompt):
        try:
            while True:
                line = input(prompt)
                if not line.strip():
                    continue
                return shlex.split(line)
        except (KeyboardInterrupt, EOFError):
            return ["exit"]
