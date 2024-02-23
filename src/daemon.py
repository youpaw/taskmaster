import yaml
from multiprocessing import Process, Queue
from shell import Shell
from monitor import Monitor

# def f(q):
#     q.put([42, None, 'hello'])
#
#
# if __name__ == '__main__':
#     q = Queue()
#     p = Process(target=f, args=(q,))
#     p.start()
#     print(q.get())  # prints "[42, None, 'hello']"
#     p.join()


CONFIG_FILE = None


def read_config_file(path: str):
    with open(path, "r") as stream:
        try:
            global CONFIG_FILE
            CONFIG_FILE = yaml.safe_load(stream)
            print(CONFIG_FILE)
        except yaml.YAMLError as exc:
            print(exc)


class Daemon:
    def __init__(self, config_path: str):
        # TODO: Lock config file during init (maybe in main idk)
        self.config_path = config_path
        read_config_file(config_path)
        self.monitor = Monitor(CONFIG_FILE or {})

    def exec_cmd(self, cmd: list):
        pass

    def run(self):
        print("Daemon started")
        shell = Shell()
        sh_queue = Queue()
        sh_proc = Process(target=shell.run(), args=(sh_queue,))
        sh_proc.start()

        while True:
            self.monitor.monitor_active_tasks()
            while sh_queue.empty() is False:
                sh_queue.get()
                self.exec_cmd()
