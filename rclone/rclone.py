import logging
import subprocess
import tempfile
from typing import List
from rclone.rclone_config.storage_system import StorageSystem
from rclone.rclone_config.rclone_config import RcloneConfig
from configparser import ConfigParser


class RClone:
    """
    Wrapper class for rclone.
    """

    def __init__(self, cfg: str):
        config_string = cfg.replace("\\n", "\n")
        self.cfg = ConfigParser()
        self.cfg.read_string(config_string)

        self.log = logging.getLogger("RClone")

    def __init__(self, remotes: List[StorageSystem]) -> None:
        self.cfg = RcloneConfig(remotes)

    def _execute(self, command_with_args):
        """
        Execute the given `command_with_args` using Popen
        Args:
            - command_with_args (list) : An array with the command to execute,
                                         and its arguments. Each argument is given
                                         as a new element in the list.
        """
        self.log.debug("Invoking : %s", " ".join(command_with_args))
        try:
            with subprocess.Popen(
                command_with_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            ) as proc:
                (out, err) = proc.communicate()

                # out = proc.stdout.read()
                # err = proc.stderr.read()

                self.log.debug(out)
                if err:
                    self.log.warning(err.decode("utf-8").replace("\\n", "\n"))

                return {"code": proc.returncode, "out": out, "error": err}
        except FileNotFoundError as not_found_e:
            self.log.error("Executable not found. %s", not_found_e)
            return {"code": -20, "error": not_found_e}
        except Exception as generic_e:
            self.log.exception("Error running command. Reason: %s", generic_e)
            return {"code": -30, "error": generic_e}

    def run_cmd(self, command, extra_args=None):
        """
        Execute rclone command
        Args:
            - command (string): the rclone command to execute.
            - extra_args (list): extra arguments to be passed to the rclone command
        """
        if extra_args is None:
            extra_args = []
        # save the configuration in a temporary file
        with tempfile.NamedTemporaryFile(mode="wt", delete=True) as cfg_file:
            # cfg_file is automatically cleaned up by python
            self.log.debug(f"rclone config: ~{self.cfg}~")
            self.cfg.write(cfg_file)
            cfg_file.flush()

            command_with_args = ["rclone", command, "--config", cfg_file.name]
            command_with_args += extra_args
            command_result = self._execute(command_with_args)
            cfg_file.close()
            return command_result

    def copy(self, source, dest, flags=None):
        """
        Executes: rclone copy source:path dest:path [flags]
        Args:
        - source (string): A string "source:path"
        - dest (string): A string "dest:path"
        - flags (list): Extra flags as per `rclone copy --help` flags.
        """
        if flags is None:
            flags = []
        return self.run_cmd(command="copy", extra_args=[source] + [dest] + flags)

    def sync(self, source, dest, flags=None):
        """
        Executes: rclone sync source:path dest:path [flags]
        Args:
        - source (string): A string "source:path"
        - dest (string): A string "dest:path"
        - flags (list): Extra flags as per `rclone sync --help` flags.
        """
        if flags is None:
            flags = []
        return self.run_cmd(command="sync", extra_args=[source] + [dest] + flags)

    def listremotes(self, flags=None):
        """
        Executes: rclone listremotes [flags]
        Args:
        - flags (list): Extra flags as per `rclone listremotes --help` flags.
        """
        if flags is None:
            flags = []
        return self.run_cmd(command="listremotes", extra_args=flags)

    def ls(self, dest, flags=None):
        """
        Executes: rclone ls remote:path [flags]
        Args:
        - dest (string): A string "remote:path" representing the location to list.
        """
        if flags is None:
            flags = []
        return self.run_cmd(command="ls", extra_args=[dest] + flags)

    def lsjson(self, dest, flags=None):
        """
        Executes: rclone lsjson remote:path [flags]
        Args:
        - dest (string): A string "remote:path" representing the location to list.
        """
        if flags is None:
            flags = []
        return self.run_cmd(command="lsjson", extra_args=[dest] + flags)

    def delete(self, dest, flags=None):
        """
        Executes: rclone delete remote:path
        Args:
        - dest (string): A string "remote:path" representing the location to delete.
        """
        if flags is None:
            flags = []
        return self.run_cmd(command="delete", extra_args=[dest] + flags)
