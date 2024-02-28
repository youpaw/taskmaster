#!/usr/bin/env python
import argparse
from multiprocessing import Process, Queue
from daemon import Daemon
from shell import Shell

DEFAULT_CONFIG_FILE_PATH = "taskmaster.yaml"
DEFAULT_LOG_FILE_PATH = "taskmaster.log"


def main(args):
    print("Taskmaster started")
    shell = Shell()
    queue = Queue()
    daemon_obj = Daemon(args.config, queue)
    sh_proc = Process(target=daemon_obj.run(), args=())
    sh_proc.start()
    shell.read(queue)
    sh_proc.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Taskmaster")
    parser.add_argument('-c', '--config', help='Taskmaster config file', required=True,
                        default=DEFAULT_CONFIG_FILE_PATH)

    args = parser.parse_args()
    main(args)
