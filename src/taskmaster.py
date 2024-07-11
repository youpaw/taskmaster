#!/usr/bin/env python
import argparse
import os
from multiprocessing import Process
from server import Server
from shell import Shell

cur_path = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_FILE_PATH = cur_path + "/taskmaster.yaml"
DEFAULT_LOG_FILE_PATH = cur_path + "/taskmaster.log"
DEFAULT_PID_FILE_PATH = cur_path + "/taskmaster.pid"
DEFAULT_SOCKET_FILE_PATH = cur_path + "/taskmaster.sock"


def main(arguments: argparse.Namespace):
    # Check pid file.
    # If it exists, check if the process is running and start the shell.
    # If the process is not running, show a message and exit.
    # If the pid file does not exist, start the server in the separate process,
    # daemonize it, and start the shell in this process.
    config_file = arguments.config
    log_file = arguments.log_file
    pid_file = arguments.pid_file
    socket_file = arguments.socket_file
    if not os.path.exists(log_file):
        with open(log_file, "a+") as f:
            f.write("")
        log_file = os.path.abspath(log_file)
    if check_pid_file(pid_file):
        print("Taskmaster is already running.")
        return
    else:
        server = Server(config_file, socket_file, log_file, pid_file)
        server.run()
        inp = input("Taskmaster started. You can type some command\n")
        print(f"You typed {inp}. Cool shell, ah?")


def check_pid_file(pid_file: str):
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Taskmaster")
    parser.add_argument('-c', '--config', help='Taskmaster config file', required=False,
                        default=DEFAULT_CONFIG_FILE_PATH, type=str)
    parser.add_argument('-l', '--log-file', help='Taskmaster log file', required=False,
                        default=DEFAULT_LOG_FILE_PATH, type=str)
    parser.add_argument('-p', '--pid-file', help='Taskmaster pid file', required=False,
                        default=DEFAULT_PID_FILE_PATH, type=str)
    parser.add_argument('-s', '--socket-file', help='Taskmaster socket file', required=False,
                        default=DEFAULT_SOCKET_FILE_PATH, type=str)

    args = parser.parse_args()
    main(args)
