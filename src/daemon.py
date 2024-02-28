from time import sleep
import signal
import yaml
from multiprocessing import Queue
from monitor import Monitor


class Daemon:
    def __init__(self, config_path: str, queue: Queue):
        # TODO: Lock config file during init (maybe in main idk)
        self.config_path = config_path
        self.config = {}
        self.reload_config()
        self.monitor = Monitor(self.config)
        self.monitor_sync = True
        self.queue = queue
        signal.signal(signal.SIGHUP, self.sighup_handler)

    def sighup_handler(self, signum, _):
        print(f"Received SIGHUP signal ({signum}). Reloading file...")
        self.reload_config()

    def reload_config(self):
        try:
            with open(self.config_path, 'r') as stream:
                self.config = yaml.safe_load(stream)
                self.monitor_sync = False
                print('Config file reloaded successfully!')
                print(self.config)
        except yaml.YAMLError as exc:
            print('Config file reload failed: {}'.format(exc))

    def exec_cmd(self, cmd: list):
        print(cmd)

    def run(self):
        print("Daemon started")
        while True:
            if self.monitor_sync is not True:
                self.monitor.update_tasks(self.config)
                self.monitor_sync = True
            self.monitor.monitor_active_tasks()
            while self.queue.empty() is False:
                cmd = self.queue.get()
                self.exec_cmd(cmd)
            # TODO: optimise sleep smhw
            sleep(1)
