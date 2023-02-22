from rclone.rclone_config.storage_system import StorageSystem


class S3(StorageSystem):
    provider: str
    access_key_id: str
    secret_access_key: str
    region: str
    endpoint: str
    type: str = "s3"

    def __init__(
        self,
        provider: str,
        access_key_id: str,
        secret_access_key: str,
        region: str,
        endpoint: str,
        name: str,
    ) -> None:
        self.provider = provider
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.region = region
        self.endpoint = endpoint
        StorageSystem.__init__(self, name=name, type=S3.type)
