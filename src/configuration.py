from dataclasses import dataclass

import yaml

@dataclass
class Program:
    name: str
    cmd: str
    fd: int = None
    umask: int = None
    workingdir: str = None
    numprocs: int = None
    autostart: bool = False
    autorestart: bool = False
    exitcodes: list = None
    startretries: int = None
    stopsignal: str = None
    stdin: str = None
    stdout: str = None
    stderr: str = None

class Configuration:
    program_section = "programs"

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self.from_yaml()

    def reload(self):
        self.config = self.from_yaml()

    def from_yaml(self):
        with open(self.config_path, "r") as f:
            data = yaml.safe_load(f)
        programs = data.get(self.program_section)

        if not programs:
            raise ValueError("No programs section in the configuration.")
        config = []
        for name, attributes in programs.items():
            try:
                config.append(Program(name, **attributes))
            except TypeError as e:
                print(f"Error in program {name}: {e}")
                return None

        return config


if __name__ == "__main__":
    Configuration("/home/kosyan62/PycharmProjects/taskmaster/test/base.yaml")