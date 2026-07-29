"""Declaration-only module base class."""

from canary_framework.core.service import ServiceBase


class ModuleBase(ServiceBase):
    """Declaration base; Task 6 adds composition behavior."""


__all__ = ["ModuleBase"]
