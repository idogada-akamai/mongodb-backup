class StorageSystem:
    name: str
    type: str

    def __init__(self, name: str, type: str) -> None:
        self.name = name
        self.type = type

    def to_config_dict(self):
        config_dict = self.__dict__
        name = config_dict.pop("name")
        return {name: config_dict}
