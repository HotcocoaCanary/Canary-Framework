from canary_framework import config


@config
class DBConfig:
    url: str = "postgres://localhost:5432"
    pool_size: int = 10
