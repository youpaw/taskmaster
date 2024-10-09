import logging

from configuration import Program, Configuration
import subprocess
import time


class TaskError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class Task:

    DONE = ["SUCCEEDED", "FAILED", "KILLED", "STOPPED"]
    BUSY = ["STARTING", "STOPPING", "RUNNING"]

    def __init__(self, program: Program):
        self.program = program
        self.process = None
        self.start_time = None
        self.stop_time = None
        self.restart_count = 0
        self.rebooting = 0
        self.status = "CREATED"

    def __repr__(self):
        return f"<Task {self.program.cmd} in status {self.status} with pid {self.process.pid if self.process else '?'}>"


    def start(self):
        """Start the program. Status becomes STARTING."""
        if self.process and self.process.poll() is None:
            raise TaskError("Task has already started.")
        self.status = "STARTING"
        self.rebooting = False
        self.start_time = time.time()
        self.process = subprocess.Popen(
                args=self.program.args,
                cwd=self.program.cwd,
                stdout=open(self.program.stdout, "a") if self.program.stdout else None,
                stderr=open(self.program.stderr, "a") if self.program.stderr else None,
                env=self.program.env,
                umask=self.program.umask,

        )

    def check_start(self):
        """Check if the program has started."""
        # ToDo validate that it checks properly
        return_code = self.process.poll()
        if return_code is not None:
            if return_code in self.program.exitcodes:
                self.status = "SUCCEEDED"
            else:
                if time.time() - self.start_time < self.program.startsecs and \
                        self.restart_count < self.program.startretries:
                    self.restart_count += 1
                    self.start()
                else:
                    self.status = "FAILED"
        else:
            if time.time() - self.start_time > self.program.startsecs:
                self.status = "RUNNING"

    def stop(self):
        """Stop the program. Status becomes STOPPING."""
        if self.process:
            if self.process.poll():
                raise TaskError("Task is not running.")
        else:
            raise TaskError("Task is not initialized.")
        self.status = "STOPPING"
        self.stop_time = time.time()
        self.process.send_signal(self.program.stopsignal)

    def check_stop(self):
        """Check if the program has stopped."""
        return_code = self.process.poll()
        if return_code is not None:
            self.status = "STOPPED"
            self.process.wait()
        else:
            if not self.program.stopwaitsecs or time.time() - self.stop_time > self.program.stopwaitsecs:
                self.status = "KILLED"
                self.process.kill()
                # ToDo check if we should wait for the process kill

    def check_running(self):
        """Check if the program is running."""
        return_code = self.process.poll()
        if return_code is not None:
            self.process.wait()
            if return_code in self.program.exitcodes:
                if self.program.autorestart == "always" and self.restart_count < self.program.startretries:
                    self.restart_count += 1
                    self.start()
                else:
                    self.status = "SUCCEEDED"
            else:
                if self.program.autorestart == "unexpected" and self.restart_count < self.program.startretries:
                    self.restart_count += 1
                    self.start()
                self.status = "FAILED"

    def restart(self):
        """Restart the program. Status becomes RESTARTING."""
        try:
            self.stop()
            self.rebooting = True
        except TaskError:
            self.start()


    def update_status(self):
        """Update the status of the program based on the status of its processes."""
        if self.status == "STARTING":
            self.check_start()
        elif self.status == "STOPPING":
            self.check_stop()
        elif self.status == "RUNNING":
            self.check_running()
        if self.rebooting and self.is_done():
            self.start()

    def is_busy(self):
        return self.status in self.BUSY

    def is_done(self):
        return self.status in self.DONE

    def is_idle(self):
        return self.status == "CREATED"


class MonitorError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class Monitor:
    def __init__(self, config: Configuration):
        self.config = config
        self.active_tasks = set()
        self.old_tasks = set()
        self.tasks = {}
        self.logger = logging.getLogger("Monitor")
        self.logger.info("Monitor initialized.")

    def start_by_name(self, name: str):
        task = self._get_task_by_name(name)
        if task.is_busy():
            raise MonitorError(f"Task '{name}' is busy.")
        elif task.is_done():
            raise MonitorError(f"Task '{name}' has already finished.")
        try:
            task.start()
        except TaskError as e:
            raise MonitorError(f"{name}: {e}")

    def stop_by_name(self, name: str):
        task = self._get_task_by_name(name)
        if task.is_done():
            raise MonitorError(f"Task '{name}' has already finished.")
        elif task.status == "STOPPING":
            raise MonitorError(f"Task '{name}' is already stopping.")
        elif task.is_idle():
            task.status = "STOPPED"
            self.active_tasks.remove(name)
            return
        try:
            task.stop()
        except TaskError as e:
            raise MonitorError(f"{name}: {e}")


    def restart_by_name(self, name: str):
        task = self._get_task_by_name(name)
        if task.rebooting is True:
            raise MonitorError(f"Task '{name}' is already restarting.")
        try:
            task.restart()
        except TaskError as e:
            raise MonitorError(f"{task}: {e}")
        self.active_tasks.add(name)

    def restart_all(self):
        """Restart all tasks."""
        counter = 0
        for name, task in self.tasks.items():
            if task.rebooting is False:
                task.restart()
                self.active_tasks.add(name)
                counter += 1
        return counter

    def _get_task_by_name(self, name) -> Task:
        if name not in self.tasks:
            raise MonitorError(f"Task '{name}' does not exist.")
        return self.tasks[name]

    def update(self):
        for name in self.active_tasks:
            self.tasks[name].update_status()
        self.active_tasks = set([name for name in self.active_tasks if self._task_is_active(name)])

    def _task_is_active(self, name) -> bool:
        task = self.tasks[name]
        if task.is_done():
            return False
        return True

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
        self.active_tasks.add(name)

    def _retire_task(self, name: str):
        task = self.tasks.pop(name)
        if name in self.active_tasks:
            self.active_tasks.remove(name)
            if task.is_busy():
                if task.status != "STOPPING":
                    task.stop()
                self.old_tasks.add(task)
