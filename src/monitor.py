from dataclasses import dataclass, field

from configuration import Program, Configuration
import subprocess
import time


class Task:
    def __init__(self, program: Program):
        self.program = program
        self.process = None
        self.start_time = None
        self.stop_time = None
        self.restart_count = 0
        self._status = "CREATED"

    def __repr__(self):
        return f"<Task {self.program.cmd} in status {self._status} with pid {self.process.pid}>"

    @property
    def status(self):
        self.update_status()
        return self._status

    def start(self):
        """Start the program. Status becomes STARTING."""
        if self.status == "RUNNING":
            return
        self._status = "STARTING"
        self.start_time = time.time()
        self.process = subprocess.Popen(
                args=self.program.args,
                cwd=self.program.workingdir,
                stdout=open(self.program.stdout, "a") if self.program.stdout else None,
                stderr=open(self.program.stderr, "a") if self.program.stderr else None,
                env=self.program.env
        )

    def check_start(self):
        """Check if the program has started."""
        return_code = self.process.poll()
        if return_code is not None:
            if return_code in self.program.exitcodes:
                self._status = "SUCCEEDED"
            else:
                if time.time() - self.start_time < self.program.startsecs and \
                        self.restart_count < self.program.startretries:
                    self.restart_count += 1
                    self.start()
                else:
                    self._status = "FAILED"
        else:
            if time.time() - self.start_time > self.program.startsecs:
                self._status = "RUNNING"

    def stop(self):
        """Stop the program. Status becomes STOPPING."""
        if self.status == "STOPPED":
            return
        self._status = "STOPPING"
        pass

    def restart(self):
        """Restart the program. Status becomes RESTARTING."""
        if self.status == "RESTARTING":
            return
        self._status = "RESTARTING"
        pass

    def update_status(self):
        """Update the status of the program based on the status of its processes."""
        if self._status == "STARTING":
            self.check_start()
        elif self._status == "STOPPING":
            # self.check_stop()
            pass

class MonitorError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class Monitor:
    def __init__(self, config: Configuration):
        self.config = config
        self.active_tasks = []
        self.old_tasks = []
        self.tasks = {}

    def start_by_name(self, name: str):
        if name not in self.tasks:
            raise MonitorError(f"Task {name} does not exist.")
        self._start_task(name, self.tasks[name])

    def start(self):
        """Start all tasks."""
        active_ids = set(self.active_tasks)
        all_ids = set(self.tasks.keys())
        start_ids = all_ids - active_ids
        for name in start_ids:
            try:
                self._start_task(name, self.tasks[name])
            except MonitorError as _:
                pass

    def _start_task(self, name: str, task: Task):
        if task in self.active_tasks or task.status == "STOPPING":
            raise MonitorError(f"Task {name} is running.")
        elif task.status == "FAILED" or task.status == "SUCCEEDED":
            raise MonitorError(f"Task {name} is already finished.")
        elif task.status == "RESTARTING":
            raise MonitorError(f"Task {name} is restarting.")
        task.start()
        self.active_tasks.append(name)

    def stop(self):
        """Stop all tasks."""
        pass

    def update(self):
        for name in self.active_tasks:
            self.tasks[name].update_status()

    def reload_config(self):
        """Reload the configuration."""
        old_progs = self.config.programs
        self.config.reload_config()
        new_progs = self.config.programs
        # Initialize tasks
        if not self.tasks:
            for name, program in new_progs.items():
                self._create_task(name, program)
            return

        old_ids = set(old_progs.keys())
        new_ids = set(new_progs.keys())
        # Process added programs
        added_ids = new_ids - old_ids
        for name in added_ids:
            self._create_task(name, new_progs[name])
        # Process removed programs
        removed_ids = old_ids - new_ids
        for name in removed_ids:
            self._retire_task(name)
        # Process same programs
        same_ids = new_ids & old_ids
        for name in same_ids:
            if old_progs[name] == new_progs[name]:
                continue
            self._retire_task(name)
            self._create_task(name, new_progs[name])

    def _create_task(self, name, program: Program):
        self.tasks[name] = task = Task(program)
        if program.autostart:
            task.start()
            self.active_tasks.append(name)

    def _retire_task(self, name: str):
        task = self.tasks.pop(name)
        if name in self.active_tasks:
            self.active_tasks.remove(name)
            task.stop()
            self.old_tasks.append(task)


if __name__ == "__main__":
    conf = Configuration("/home/kosyan62/PycharmProjects/taskmaster/test/base.yaml")
    print(conf.config)
    monitor = Monitor(conf)
    monitor.start()
    print(monitor.tasks)
    time.sleep(15)
    for _task in monitor.tasks.values():
        _task.update_status()
    print(monitor.tasks)