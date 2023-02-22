from rclone.rclone_config.storage_system import StorageSystem


class Http(StorageSystem):
    url: str
    type: str = "http"

    def __init__(self, name: str, url: str) -> None:
        self.url = url
        StorageSystem.__init__(self, name=name, type=Http.type)
