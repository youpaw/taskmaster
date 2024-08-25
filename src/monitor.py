from dataclasses import dataclass, field

from configuration import Program, Configuration
import subprocess
import time


@dataclass
class Process:
    start_time: field(default_factory=lambda: time.time())
    restart_count: int = 0


class Task:
    def __init__(self, program: Program):
        self.program = program
        self.processes = []
        self.start_time = None
        self.stop_time = None
        self.restart_count = 0
        self._status = "CREATED"

    @property
    def status(self):
        self.update_status()
        return self._status

    def start(self):
        """Start the program. Status becomes STARTING."""
        if self.status == "RUNNING":
            return
        self._status = "STARTING"
        for _ in range(self.program.numprocs):
            process = subprocess.Popen(
                    args=self.program.args,
                    cwd=self.program.workingdir,
                    stdout=open(self.program.stdout, "a") if self.program.stdout else None,
                    stderr=open(self.program.stderr, "a") if self.program.stderr else None,
                    env=self.program.env,
                )
            self.processes.append({"process": process, "start_time": time.time(), "restart_count": 0, "last_status": "STARTING"})

    def check_start(self):
        """Check if the program has started."""
        for process in self.processes:
            exit_code = process["process"].poll()
            if exit_code is None:
                if self.program.startsecs:
                    if time.time() - process["start_time"] > self.program.startsecs:
                        process["last_status"] = "RUNNING"
                    else:
                        process["last_status"] = "STARTING"
                else:
                    process["last_status"] = "RUNNING"
            else:
                if exit_code in self.program.exitcodes:
                    process["last_status"] = "SUCCEEDED"
                else:
                    if process["restart_count"] < self.program.startretries:
                        process["last_status"] = "STARTING"
                        process["restart_count"] += 1
                        process["start_time"] = time.time()
                        process["process"] = subprocess.Popen(
                            args=self.program.args,
                            cwd=self.program.workingdir,
                            stdout=open(self.program.stdout, "a") if self.program.stdout else None,
                            stderr=open(self.program.stderr, "a") if self.program.stderr else None,
                            env=self.program.env,
                        )
                    else:
                        process["last_status"] = "FAILED"


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
            check_processes_start()
        elif self._status == "STOPPING":
            check_processes_stop()


class Monitor:
    def __init__(self, config: Configuration):
        self.config = config
        self.tasks = {}

    def start(self):
        """Start all programs."""
        pass

    def stop(self):
        """Stop all programs."""
        pass

    def reload_config(self):
        """Reload the configuration."""
        old_config = self.config
        self.config.reload_config()
        new_config = self.config
        # compare old and new config and restart changed programs
        pass

