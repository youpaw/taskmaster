import logging.config
import signal
from dataclasses import dataclass, Field, field

import yaml


@dataclass
class Program:
    cmd: str
    autostart: bool = False
    autorestart: str = "never"
    exitcodes: list = field(default_factory=lambda: [0])
    startsecs: int = 0
    startretries: int = 3
    stopsignal: int = signal.SIGTERM
    stopwaitsecs: int = 10
    stdout: str = None
    stderr: str = None
    env: dict = None  # TODO test this
    workingdir: str = None
    umask: int = None

    @property
    def args(self):
        return self.cmd.split()


class Configuration:
    program_section = "programs"

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.logger = logging.getLogger("Configuration")
        self.programs = self.from_yaml()

    def reload_config(self):
        self.logger.info("Reloading configuration.")
        self.programs = self.from_yaml()
        self.logger.info("Configuration reloaded.")

    def from_yaml(self):
        with open(self.config_path, "r") as f:
            data = yaml.safe_load(f)
        program_configs = data.get(self.program_section)

        if not program_configs:
            raise ValueError("No programs section in the configuration.")
        programs = {}
        for name, attributes in program_configs.items():
            try:
                if name in programs:
                    raise ValueError(f"Duplicate program name: {name}")
                num_procs = attributes.pop("numprocs", None)
                if num_procs:
                    if not isinstance(num_procs, int):
                        raise TypeError(f"numprocs must be an integer, not {type(num_procs)}")
                    if num_procs < 2:
                        raise ValueError("numprocs must be greater than 1")
                    for i in range(num_procs):
                        programs[f"{name}_{i + 1}"] = Program(**attributes)
                else:
                    programs[name] = Program(**attributes)
            except TypeError as e:
                print(f"Error in program {name}: {e}")
                return None

        return programs


# if __name__ == "__main__":
#     conf = Configuration("/home/kosyan62/PycharmProjects/taskmaster/test/base.yaml")
#     print(conf.config)
    # pr1 = Program(cmd="ls -l", numprocs=2, autostart=True, autorestart="always", exitcodes=[0, 1], startsecs=1, startretries=3, stopsignal="SIGTERM", stopwaitsecs=10, stdout="stdout.log", stderr="stderr.log", env={"PATH": "/usr/bin"}, workingdir="/tmp", umask=0o022)
    # pr2 = Program(cmd="ls -l", numprocs=1, autostart=True, autorestart="always", exitcodes=[0, 1], startsecs=1, startretries=3, stopsignal="SIGTERM", stopwaitsecs=10, stdout="stdout.log", stderr="stderr.log", env={"PATH": "/usr/bin"}, workingdir="/tmp", umask=0o022)
