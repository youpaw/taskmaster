from subprocess import Popen


class Task:

    def __init__(self, task_id: str, task_conf: dict):
        self.id = task_id
        self.args = task_conf['cmd'].split()
        self.proc = None
        self.status = "init"
        self.exit_code = None

    def run(self):
        self.proc = Popen(self.args)


class Monitor:
    def __init__(self, config: dict):
        self.tasks = {}
        self.active_tasks = []
        for task_id, task_conf in config['tasks'].items():
            self.tasks[task_id] = Task(task_id, task_conf)
            self.active_tasks.append(task_id)

    def monitor_active_tasks(self):
        for task_id in self.active_tasks:
            task = self.tasks.get(task_id)
            if task.status == "init":
                print("Task {} started!".format(task_id))
                task.run()
                task.status = "run"
            elif task.status == "run":
                ret = task.proc.poll()
                if ret is not None:
                    print("Task {} finished!".format(task_id))
                    task.status = "fini"
                    task.exit_code = ret
                    self.active_tasks.remove(task_id)

    def update_tasks(self, config: dict):
        # TODO handle update (maybe dict for active tasks as well?)
        for task_id, task_conf in config['tasks'].items():
            pass

