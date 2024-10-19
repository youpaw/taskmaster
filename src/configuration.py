import logging.config
import os.path
import signal
from dataclasses import dataclass, field

import yaml


class ConfigurationError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


@dataclass
class Program:
    cmd: str
    autostart: bool = False
    autorestart: str = field(default="never")  # TODO complete in monitor.py
    exitcodes: list = field(default_factory=lambda: [0])
    startsecs: int = 0
    startretries: int = 3
    stopsignal: int = signal.SIGTERM
    stopwaitsecs: int = 10
    stdout: str = None
    stderr: str = None
    env: dict = None
    cwd: str = None
    umask: int = -1

    @property
    def args(self):
        return self.cmd.split()

    def __post_init__(self):
        # Validate the program
        if not self.cmd:
            raise ConfigurationError("Program cmd is required.")
        if self.autorestart not in ("never", "always", "unexpected"):
            raise ConfigurationError(f"Invalid autorestart value: {self.autorestart}")
        for code in self.exitcodes:
            if 0 < code > 255:
                raise ConfigurationError(f"Invalid exit code: {code}")
        if self.startsecs < 0:
            raise ConfigurationError("startsecs must be greater than or equal to 0")
        if self.startretries < 0:
            raise ConfigurationError("startretries must be greater than or equal to 0")
        if self.stopsignal < 0:
            raise ConfigurationError("stopsignal must be greater than or equal to 0")
        if self.stopwaitsecs < 0:
            raise ConfigurationError("stopwaitsecs must be greater than or equal to 0")
        if -1 < self.umask > int('777', 8):
            raise ConfigurationError("umask value must be in range of 000 to 777 oct or -1")
        if self.cwd and not os.path.exists(self.cwd):
            raise ConfigurationError(
                f"Error opening cwd file {self.cwd}. Argument must be a valid file path."
            )


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
            raise ConfigurationError("No programs section in the configuration.")
        programs = {}
        for name, attributes in program_configs.items():
            try:
                if name in programs:
                    raise ConfigurationError(f"Duplicate program name: {name}")
                num_procs = attributes.pop("numprocs", None)
                if num_procs:
                    if not isinstance(num_procs, int):
                        raise ConfigurationError(
                            f"numprocs must be an integer, not {type(num_procs)}"
                        )
                    if num_procs < 1:
                        raise ConfigurationError("numprocs must be greater than 0")
                    if num_procs == 1:
                        programs[name] = Program(**attributes)
                    else:
                        for i in range(num_procs):
                            programs[f"{name}_{i + 1}"] = Program(**attributes)
                else:
                    programs[name] = Program(**attributes)
            except TypeError as e:
                if "unexpected keyword argument" in str(e):
                    argument = str(e).split(" ")[-1]
                    self.logger.error(
                        f"Unexpected argument {argument} in program '{name}'"
                    )
                else:
                    self.logger.error(f"Undefined error parsing program {name} - {e}")
            except ConfigurationError as e:
                self.logger.error(f"Error parsing program '{name}' - {e}")

            except Exception as e:
                self.logger.error(f"Undefined error parsing program {name} - {e}")

        return programs
