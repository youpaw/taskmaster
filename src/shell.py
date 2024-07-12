import socket


class Shell:
    def __init__(self, sock_file: str):
        self.sock_file = sock_file
        # flush stdout
        print(f"Taskmaster shell initiated on {sock_file}")

    def run(self):
        try:
            while True:
                cmd = input("taskmaster> ")
                if cmd == "exit":
                    break
                else:
                    self.send_command(cmd)
        except (KeyboardInterrupt, EOFError, FileNotFoundError):
            print("Exiting shell.")

    def send_command(self, cmd: str):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(self.sock_file)
            s.sendall(cmd.encode())
            response = s.recv(1024, )
            print(response.decode(), end="")



