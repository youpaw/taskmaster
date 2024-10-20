import logging

from configuration import Program, Configuration
import subprocess
import time
import os

UMASK = os.umask(0)
os.umask(UMASK)

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
        self.logger = logging.getLogger("Task")

    def __repr__(self):
        return f"<Task '{self.program.cmd}' in status {self.status} with pid {self.process.pid if self.process else '?'}>"

    def start(self):
        """Start the program. Status becomes STARTING."""
        if self.process and self.process.poll() is None:
            raise TaskError("Task has already started.")
        self.rebooting = False
        self.start_time = time.time()
        stdout, stderr = None, None
        try:
            stdout = open(self.program.stdout, "a") if self.program.stdout else None
            stderr = open(self.program.stderr, "a") if self.program.stderr else None
            self.process = subprocess.Popen(
                    args=self.program.args,
                    cwd=self.program.cwd,
                    stdout=stdout,
                    stderr=stderr,
                    env=self.program.env,
                    umask=self.program.umask,
            )
            self.status = "STARTING"
        except Exception as e:
            self.logger.error(
                f"Failed to create subprocess '{self.program.cmd}' with error: {e}")
            raise TaskError(
                f"Failed to create subprocess '{self.program.cmd}' with error: {e}")
        finally:
            if stdout:
                stdout.close()
            if stderr:
                stderr.close()

    def check_start(self):
        """Check if the program has started."""
        return_code = self.process.poll()
        if return_code is None:
            if time.time() - self.start_time > self.program.startsecs:
                self.logger.info(f"Program '{self.program.cmd}' started successfully.")
                self.status = "RUNNING"
            return
        if return_code in self.program.exitcodes:
            self.logger.info(f"Program '{self.program.cmd}' exited with code {return_code}.")
            self.status = "SUCCEEDED"
        else:
            self.logger.info(f"Program '{self.program.cmd}' failed to start.")
            self.status = "FAILED"

    def stop(self):
        """Stop the program. Status becomes STOPPING."""
        if self.process:
            if self.process.poll() is not None:
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
            self.logger.info(f"Program '{self.program.cmd}' stopped.")
        elif not self.program.stopwaitsecs or time.time() - self.stop_time > self.program.stopwaitsecs:
            self.status = "KILLED"
            self.logger.info(f"Program '{self.program.cmd}' failed to stop, killing process.")
            self.process.kill()
            self.process.wait()
            self.logger.info(f"Program '{self.program.cmd}' process was killed.")

    def check_running(self):
        """Check if the program is running."""
        return_code = self.process.poll()
        if return_code is None:
            return
        self.process.wait()
        if return_code in self.program.exitcodes:
            self.logger.info(f"Program '{self.program.cmd}' exited with code {return_code}.")
            self.status = "SUCCEEDED"
        else:
            self.logger.info(f"Program '{self.program.cmd}' failed with exit code {return_code}.")
            self.status = "FAILED"

    def restart(self):
        """Restart the program. Status becomes RESTARTING."""
        self.logger.info(f"Restarting program '{self.program.cmd}'.")
        try:
            self.stop()
            self.rebooting = True
        except TaskError:
            self.start()

    def check_done(self):
        if self.rebooting:
            self.start()
        elif self.status in ["SUCCEEDED", "FAILED"]:
            prog = self.program
            if ((prog.autorestart == "always" or
                 (prog.autorestart == "unexpected" and self.status == "FAILED"))
                    and self.restart_count < prog.startretries):
                self.restart_count += 1
                self.logger.info(f"Restarting program '{prog.cmd}', restart count {self.restart_count}/{prog.startretries}.")
                self.start()

    def update_status(self):
        """Update the status of the program based on the status of its processes."""
        if self.status == "STARTING":
            self.check_start()
        elif self.status == "STOPPING":
            self.check_stop()
        elif self.status == "RUNNING":
            self.check_running()
        if self.is_done():
            self.check_done()

    def is_busy(self):
        return self.status in self.BUSY

    def is_done(self):
        return self.status in self.DONE

    def is_idle(self):
        return self.status == "CREATED"

    def get_rc(self):
        if self.process:
            rc = self.process.poll()
            if rc is None:
                return "-"
            return rc
        return "N/A"


class MonitorError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class Monitor:
    STATUS_FORMAT = "{:<20} {:<12} {:<8} {:<8} {:<6}\n"
    STATUS_FORMAT_LEN = 57
    STATUS_HEADER = STATUS_FORMAT.format('Name', 'Status', 'RC', 'Retries', 'Umask')

    def __init__(self, config: Configuration):
        self.config = config
        self.active_tasks = set()
        self.old_tasks = set()
        self.tasks = {}
        self.logger = logging.getLogger("Monitor")
        self.logger.info("Monitor initialized.")

    @staticmethod
    def format_tasks_status(tasks):
        status = Monitor.STATUS_HEADER
        status += "-" * Monitor.STATUS_FORMAT_LEN + "\n"
        for name, task in sorted(tasks.items()):
            umask = UMASK if task.program.umask == -1 else task.program.umask
            umask = f"{umask:03o}"
            retries = task.restart_count if task.process else "N/A"
            status += Monitor.STATUS_FORMAT.format(name, task.status, task.get_rc(), retries, umask)
        return status

    def start_by_name(self, name: str):
        task = self.get_task_by_name(name)
        if task.is_busy():
            raise MonitorError(f"Task '{name}' is busy.")
        elif task.is_done():
            raise MonitorError(f"Task '{name}' has already finished.")
        try:
            self.logger.debug(f"Starting task '{name}'.")
            task.start()
        except TaskError as e:
            raise MonitorError(f"{name}: {e}")

    def stop_by_name(self, name: str):
        task = self.get_task_by_name(name)
        if task.is_done():
            raise MonitorError(f"Task '{name}' has already finished.")
        elif task.status == "STOPPING":
            raise MonitorError(f"Task '{name}' is already stopping.")
        elif task.is_idle():
            task.status = "STOPPED"
            self.active_tasks.remove(name)
            return
        try:
            self.logger.debug(f"Stopping task '{name}'.")
            task.stop()
        except TaskError as e:
            raise MonitorError(f"{name}: {e}")


    def restart_by_name(self, name: str):
        task = self.get_task_by_name(name)
        if task.rebooting is True:
            raise MonitorError(f"Task '{name}' is already restarting.")
        try:
            self.logger.debug(f"Restarting task '{name}'.")
            task.restart()
        except TaskError as e:
            raise MonitorError(f"{name}: {e}")
        self.active_tasks.add(name)

    def get_task_by_name(self, name) -> Task:
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
        self.logger.debug("Reloading configuration.")
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
        self.logger.debug(f"Added programs: {added_ids}")
        for name in added_ids:
            self.logger.info(f"Adding program '{name}'.")
            self._create_task(name, new_progs[name])
        # Process removed programs
        removed_ids = old_ids - new_ids
        self.logger.debug(f"Removed programs: {removed_ids or '0'}")
        for name in removed_ids:
            self.logger.info(f"Removing program '{name}'.")
            self._retire_task(name)
        # Process same programs
        same_ids = new_ids & old_ids
        self.logger.debug(f"Same programs: {same_ids}")
        for name in same_ids:
            if old_progs[name] == new_progs[name]:
                self.logger.info(f"Program '{name}' has not changed.")
                continue
            self._retire_task(name)
            self._create_task(name, new_progs[name])

    def _create_task(self, name, program: Program):
        self.tasks[name] = task = Task(program)
        if program.autostart:
            try:
                task.start()
            except TaskError as e:
                self.logger.error(f"Failed to autostart program '{name}': {e}")
        self.active_tasks.add(name)

    def _retire_task(self, name: str):
        task = self.tasks.pop(name)
        if name in self.active_tasks:
            self.active_tasks.remove(name)
            if task.is_busy():
                if task.status != "STOPPING":
                    task.stop()
                self.old_tasks.add(task)
