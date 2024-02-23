#!/usr/bin/env python
import argparse
from daemon import Daemon


def main(args):
    print("Taskmaster started")
    daemon_obj = Daemon(args.config)
    daemon_obj.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Taskmaster")
    parser.add_argument('-c', '--config', help='Taskmaster config file', required=True, default=DEFAULT_CONFIG_FILE_PATH)

    args = parser.parse_args()
    main(args)
