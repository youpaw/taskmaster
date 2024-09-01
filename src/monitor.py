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


class Monitor:
    def __init__(self, config: Configuration):
        self.config = config
        self.active_tasks = []
        self.old_tasks = []
        self.tasks = {}

    def start(self):
        """Start all programs."""
        for name, program in self.config.config.items():
            task = Task(program)
            task.start()
            self.tasks[name] = task

    def stop(self):
        """Stop all tasks."""
        pass

    def reload_config(self):
        """Reload the configuration."""
        old_config = self.config
        self.config.reload_config()
        new_config = self.config
        old_ids = set(old_config.programs.keys())
        new_ids = set(new_config.programs.keys())
        added_ids = new_ids - old_ids
        for name in added_ids:
            self.tasks[name] = task = Task(new_config.programs[name])
            if new_config.programs[name].autostart:
                task.start()
                self.active_tasks.append(name)
        removed_ids = old_ids - new_ids
        for name in removed_ids:
            task = self.tasks.pop(name)
            if name in self.active_tasks:
                self.active_tasks.remove(name)
                task.stop()
            self.old_tasks.append(task)
        intersect_ids = new_ids & old_ids
        for name in intersect_ids:
            if old_config.programs[name] == new_config.programs[name]:
                continue
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
    for task in monitor.tasks.values():
        task.update_status()
    print(monitor.tasks)