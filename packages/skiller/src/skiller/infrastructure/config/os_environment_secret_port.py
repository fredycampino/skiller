import os


class OsEnvironmentSecretPort:
    def get_secret(self, name: str) -> str | None:
        return os.environ.get(name)
