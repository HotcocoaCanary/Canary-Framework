"""Declaration-only router base class."""

from canary_framework.common.routing import RouteSpec
from canary_framework.core.service import ServiceBase


class RouterBase(ServiceBase):
    """Base class for router declarations."""

    __cf_route_specs__: tuple[RouteSpec, ...] = ()

    @property
    def route_specs(self) -> tuple[RouteSpec, ...]:
        """Return route specifications declared on this router class."""
        return self.__cf_route_specs__


__all__ = ["RouterBase"]
