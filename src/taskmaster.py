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


def main(config: str, socket: str, log: str, pid: str):
    try:
        Server.start_in_background(
            config_path=config,
            sock_file=socket,
            log_file=log,
            pid_file=pid
        )
    except ValueError as e:
        print(e)
        exit(1)
    print("Taskmaster started. Welcome...")
    shell = Shell(socket)
    shell.run()


def validate_args(args: argparse.Namespace):
    if not os.path.exists(args.config):
        print(f"Config file {args.config} not found.")
        exit(1)
    config_path = os.path.abspath(args.config)

    if not os.path.exists(args.log_file):
        with open(args.log_file, "a+") as f:
            f.write("")
    log_path = os.path.abspath(args.log_file)

    if os.path.exists(args.pid_file):
        print("Taskmaster is already running.")
        exit(1)
    pid_path = os.path.abspath(args.pid_file)
    if os.path.exists(args.socket_file):
        print("Socket file already exists.")
        exit(1)
    socket_path = os.path.abspath(args.socket_file)
    return config_path, log_path, pid_path, socket_path


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

    arguments = parser.parse_args()
    config, log, pid, socket = validate_args(arguments)
    main(config, socket, log, pid)
