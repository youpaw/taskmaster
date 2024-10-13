#!/usr/bin/env python
import argparse
import os
from server import Server
from shell import Shell
from configuration import Configuration, ConfigurationError
import logging.config


cur_path = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_FILE_PATH = cur_path + "/taskmaster.yaml"
DEFAULT_PID_FILE_PATH = cur_path + "/taskmaster.pid"
DEFAULT_SOCKET_FILE_PATH = cur_path + "/taskmaster.sock"


def main(config_path: str, socket_path: str, log_path: str, pid_path: str, mode: str):
    if mode in ("full", "daemon"):
        if os.path.exists(pid_path):
            print(
                f"Pid file {pid_path} already exists. Taskmaster is already running. Exiting."
            )
            exit(1)
        try:
            Configuration(config_path)
        except ConfigurationError as e:
            print(f"Config error: {e}")
            exit(1)
        except TypeError as e:
            print(f"Config error: {e}")
            exit(1)
        try:
            logging.config.fileConfig(log_path, disable_existing_loggers=True)
        except Exception as e:
            print(f"Logging config error: {e}")
            exit(1)

        try:
            Server.start_in_background(
                config_path=config_path,
                socket_path=socket_path,
                log_path=log_path,
                pid_path=pid_path,
            )
        except Exception as e:
            print(f"Error starting server: {e}")
            exit(1)

    if mode in ("full", "shell"):
        shell = Shell(socket_path)
        shell.run()


def validate_args(args: argparse.Namespace):
    if not os.path.exists(args.config):
        print(f"Config file {args.config} not found.")
        exit(1)
    config_path = os.path.abspath(args.config)

    if args.log_config:
        if not os.path.exists(args.log_config):
            print(f"Log config file {args.log_config} not found.")
            exit(1)
        log_path = os.path.abspath(args.log_config)
    else:
        log_path = None
    if os.path.exists(args.pid):
        print("Taskmaster is already running.")
        exit(1)
    pid_path = os.path.abspath(args.pid)
    if os.path.exists(args.socket):
        print("Socket file already exists.")
        exit(1)
    socket_path = os.path.abspath(args.socket)
    return {
        "config_path": config_path,
        "log_path": log_path,
        "pid_path": pid_path,
        "socket_path": socket_path,
        "mode": args.mode,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Taskmaster")
    parser.add_argument(
        "-c",
        "--config",
        help="Taskmaster config file",
        required=False,
        default=DEFAULT_CONFIG_FILE_PATH,
        type=str,
    )
    parser.add_argument(
        "-l",
        "--log-config",
        help="Taskmaster log config file",
        required=False,
        default=None,
        type=str,
    )
    parser.add_argument(
        "-p",
        "--pid",
        help="Taskmaster pid file",
        required=False,
        default=DEFAULT_PID_FILE_PATH,
        type=str,
    )
    parser.add_argument(
        "-s",
        "--socket",
        help="Taskmaster socket file",
        required=False,
        default=DEFAULT_SOCKET_FILE_PATH,
        type=str,
    )
    parser.add_argument(
        "-m",
        "--mode",
        help="Taskmaster start mode",
        required=False,
        default="full",
        choices=["full", "shell", "daemon"],
    )

    arguments = parser.parse_args()
    arguments = validate_args(arguments)
    main(**arguments)
