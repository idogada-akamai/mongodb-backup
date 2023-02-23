from copy import deepcopy


class StorageSystem:
    name: str
    type: str

    def __init__(self, name: str, type: str) -> None:
        self.name = name
        self.type = type

    def to_config_dict(self):
        config_dict = deepcopy(self.__dict__)
        name = config_dict.pop("name")
        return {self.name: config_dict}


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


class Http(StorageSystem):
    url: str
    type: str = "http"

    def __init__(self, name: str, url: str) -> None:
        self.url = url
        StorageSystem.__init__(self, name=name, type=Http.type)


def print_name(h: Http):
    name = h.name
    print(h.name)


if __name__ == "__main__":
    h = Http("test", "test")
    print_name(h)
