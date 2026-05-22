from __future__ import annotations


class ServiceContext:
    def __init__(self, config_instance: object | None = None) -> None:
        self._config = config_instance

    @property
    def config(self) -> object:
        if self._config is None:
            raise RuntimeError("No config bound to this service.")
        return self._config
