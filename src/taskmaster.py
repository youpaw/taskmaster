#!/usr/bin/env python
import argparse
import os
from multiprocessing import Process
from server import Server
from shell import Shell

DEFAULT_CONFIG_FILE_PATH = "taskmaster.yaml"
DEFAULT_LOG_FILE_PATH = "taskmaster.log"
DEFAULT_PID_FILE_PATH = "taskmaster.pid"
DEFAULT_SOCKET_FILE_PATH = "taskmaster.sock"


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
        with open(log_file, "w+") as f:
            f.write("")
    if check_pid_file(pid_file):
        print("Taskmaster is already running.")
        return
    else:
        Process(target=Server.start_daemon, args=(config_file, socket_file, log_file, pid_file), daemon=True).start()
        # Server.start_daemon(config_file, socket_file, log_file, pid_file)
        print("Taskmaster started.")
    shell = Shell(DEFAULT_SOCKET_FILE_PATH)
    shell.run()


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
