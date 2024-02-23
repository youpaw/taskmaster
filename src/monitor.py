import subprocess


class Task:

    def __init__(self, task_name: str, task_conf: dict):
        self.name = task_name
        self.args = task_conf['cmd'].split()
        self.proc = None

    def run(self) -> int:
        self.proc = subprocess.run(self.args)
        return self.proc.returncode


class Monitor:
    def __init__(self, config: dict):
        self.all_tasks = self.get_task_list(config)
        self.active_tasks = self.all_tasks

    def monitor_active_tasks(self):
        pass

    def update_task_list(self):
        pass

    @staticmethod
    def get_task_list(config: dict) -> list[Task]:
        tasks = []
        for task_name, task_conf in config['tasks']:
            tasks.append(Task(task_name, task_conf))
        return tasks
