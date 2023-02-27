from typing import List
from configparser import ConfigParser
from rclone.rclone_config.storage_system import StorageSystem


class RcloneConfig(ConfigParser):
    remotes: List[StorageSystem]

    def __init__(self, remotes: List[StorageSystem]) -> None:
        ConfigParser.__init__(self)
        self.remotes = remotes

    @property
    def remotes(self) -> List[StorageSystem]:
        return self._remotes

    @remotes.setter
    def remotes(self, remotes: List[StorageSystem]):
        self.clear()
        self._remotes = remotes
        for remote in self._remotes:
            self.read_dict(remote.to_config_dict())
