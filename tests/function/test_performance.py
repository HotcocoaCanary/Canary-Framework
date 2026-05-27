"""Performance and scalability tests for Canary Framework.

Tests cover:
    - Chain topology (a -> b -> c -> ... -> n) — linear dependency chains
    - Diamond topology — shared dependency
    - Wide tree topology — many services under one module
    - Deep tree topology — deeply nested modules
    - Recursion depth safety
    - Startup order correctness at scale
"""

from __future__ import annotations

import time

import pytest

from canary_framework import Canary, module, on_config, on_init, service


def _make_chain(n: int) -> type:
    """Build a linear chain: s0 <- s1 <- s2 <- ... <- s(n-1)."""
    svc_classes: list[type] = []

    @service("s0")
    class S0:
        def __init__(self) -> None:
            self.called = False

        @on_init
        def init(self) -> None:
            self.called = True

    svc_classes.append(S0)

    for i in range(1, n):
        prev = svc_classes[i - 1]

        @service(f"s{i}", deps=[prev])
        class Si:
            def __init__(self) -> None:
                self.called = False

            @on_init
            def init(self) -> None:
                self.called = True

        Si.__name__ = f"S{i}"
        Si.__qualname__ = f"S{i}"
        svc_classes.append(Si)

    @module("ChainRoot", services=svc_classes)
    class ChainRoot:
        pass

    ChainRoot.__name__ = "ChainRoot"
    return ChainRoot


def _make_diamond(depth: int) -> type:
    r"""Build a diamond DAG: one root, depth layers of 2 nodes each feeding into next layer.

         r
        / \
       a1  b1
        \ /
         m1
        / \
       a2  b2
        \ /
         m2 ...
    """
    all_services: list[type] = []

    @service("r")
    class R:
        @on_init
        def init(self) -> None:
            pass

    all_services.append(R)
    prev_merge: type = R

    for d in range(1, depth + 1):

        @service(f"a{d}", deps=[prev_merge])
        class A:
            @on_init
            def init(self) -> None:
                pass

        @service(f"b{d}", deps=[prev_merge])
        class B:
            @on_init
            def init(self) -> None:
                pass

        A.__name__ = f"A{d}"
        B.__name__ = f"B{d}"
        all_services.extend([A, B])

        @service(f"m{d}", deps=[A, B])
        class M:
            @on_init
            def init(self) -> None:
                pass

        M.__name__ = f"M{d}"
        all_services.append(M)
        prev_merge = M

    @module("DiamondRoot", services=all_services)
    class DiamondRoot:
        pass

    return DiamondRoot


def _make_wide_tree(children: int) -> type:
    """One module with children direct child services (no deps between them)."""
    svc_classes: list[type] = []

    for i in range(children):

        @service(f"leaf-{i}")
        class Leaf:
            @on_init
            def init(self) -> None:
                pass

        Leaf.__name__ = f"Leaf{i}"
        svc_classes.append(Leaf)

    @module("WideRoot", services=svc_classes)
    class WideRoot:
        pass

    return WideRoot


def _make_deep_modules(depth: int) -> type:
    """Build a deeply nested module tree: M0 -> M1 -> M2 -> ... -> Md -> Leaf."""
    prev_module: type | None = None

    for d in range(depth):
        services: list[type] = []
        if prev_module is not None:
            services.append(prev_module)

        @module(f"m{d}", services=services)
        class M:
            pass

        M.__name__ = f"M{d}"
        prev_module = M

    @service("leaf")
    class Leaf:
        @on_init
        def init(self) -> None:
            pass

    @module("DeepRoot", services=[prev_module, Leaf] if prev_module else [Leaf])
    class DeepRoot:
        pass

    return DeepRoot


@pytest.mark.functional
class TestChainTopology:
    """Performance and correctness for linear dependency chains."""

    async def test_chain_50_correctness(self) -> None:
        root = _make_chain(50)
        app = Canary(root)
        await app.config()
        await app.init()

        order = app.startup_order
        # ChainRoot module (no deps) comes first, then s0..s49 in order
        assert len(order) == 51
        assert order[0] == "ChainRoot"
        for i in range(49):
            assert order.index(f"s{i}") < order.index(f"s{i + 1}")

    async def test_chain_200_correctness(self) -> None:
        root = _make_chain(200)
        app = Canary(root)
        await app.config()
        await app.init()

        order = app.startup_order
        assert len(order) == 201
        for i in range(199):
            assert order.index(f"s{i}") < order.index(f"s{i + 1}")

    @pytest.mark.slow
    async def test_chain_500_correctness(self) -> None:
        root = _make_chain(500)
        app = Canary(root)
        t0 = time.monotonic()
        await app.config()
        t_config = time.monotonic() - t0
        await app.init()
        t_total = time.monotonic() - t0

        order = app.startup_order
        assert len(order) == 501
        assert t_total < 5.0, f"500-chain lifecycle took {t_total:.2f}s (limit 5s)"


@pytest.mark.functional
class TestDiamondTopology:
    """Performance and correctness for diamond dependency graphs."""

    async def test_diamond_depth_20(self) -> None:
        root = _make_diamond(20)
        app = Canary(root)
        await app.config()
        await app.init()

        order = app.startup_order
        # 1 root + 20*(2 branches + 1 merge) + 1 module = 63
        assert len(order) == 62  # 1 DiamondRoot + 1 r + 20*(a+b+m)

        # r must start before a1 and b1
        assert order.index("r") < order.index("a1")
        assert order.index("r") < order.index("b1")
        # a1 and b1 must start before m1
        assert order.index("a1") < order.index("m1")
        assert order.index("b1") < order.index("m1")

    async def test_diamond_depth_50(self) -> None:
        root = _make_diamond(50)
        app = Canary(root)
        await app.config()
        await app.init()

        order = app.startup_order
        assert len(order) == 152  # 1 DiamondRoot + 1 r + 50*(a+b+m)

        for d in range(1, 51):
            pred = f"m{d - 1}" if d > 1 else "r"
            assert order.index(pred) < order.index(f"a{d}")
            assert order.index(pred) < order.index(f"b{d}")
            assert order.index(f"a{d}") < order.index(f"m{d}")
            assert order.index(f"b{d}") < order.index(f"m{d}")


@pytest.mark.functional
class TestWideTree:
    """Performance for many independent services under one module."""

    async def test_wide_100_services(self) -> None:
        root = _make_wide_tree(100)
        app = Canary(root)
        t0 = time.monotonic()
        await app.config()
        t_config = time.monotonic() - t0
        await app.init()
        t_total = time.monotonic() - t0

        assert len(app.registry) == 101  # 100 services + 1 module
        assert t_total < 1.0, f"100-wide lifecycle took {t_total:.2f}s (limit 1s)"

    @pytest.mark.slow
    async def test_wide_500_services(self) -> None:
        root = _make_wide_tree(500)
        app = Canary(root)
        t0 = time.monotonic()
        await app.config()
        t_config = time.monotonic() - t0
        await app.init()
        t_total = time.monotonic() - t0

        assert len(app.registry) == 501
        assert t_total < 3.0, f"500-wide lifecycle took {t_total:.2f}s (limit 3s)"


@pytest.mark.functional
class TestDeepModules:
    """Recursion safety for deeply nested module trees."""

    async def test_module_depth_100(self) -> None:
        root = _make_deep_modules(100)
        app = Canary(root)
        t0 = time.monotonic()
        await app.config()
        t_config = time.monotonic() - t0
        await app.init()
        t_total = time.monotonic() - t0

        # DeepRoot + 100 M modules + 1 leaf = 102
        assert len(app.registry) == 102
        assert t_total < 2.0, f"100-module lifecycle took {t_total:.2f}s (limit 2s)"

    async def test_module_depth_200(self) -> None:
        """Deeper nesting -- test against recursion limit."""
        root = _make_deep_modules(200)
        app = Canary(root)
        t0 = time.monotonic()
        await app.config()
        t_total = time.monotonic() - t0
        await app.init()

        assert len(app.registry) == 202
        assert t_total < 3.0, f"200-module lifecycle took {t_total:.2f}s (limit 3s)"

    @pytest.mark.slow
    async def test_module_depth_500(self) -> None:
        """Stress test: 500-level nested modules."""
        root = _make_deep_modules(500)
        app = Canary(root)
        await app.config()
        await app.init()

        assert len(app.registry) == 502


def _make_service_with_value(expect: int) -> tuple[type, type]:
    """Factory to avoid Python closure capture of loop variable."""
    from pydantic import BaseModel

    class SvcCfg(BaseModel):
        value: int = 42

    @service(f"svc-{expect}")
    class Svc:
        @on_config
        def setup(self) -> None:
            assert self.value == expect, f"Expected value={expect}, got {self.value}"  # type: ignore[attr-defined]

    Svc.__name__ = f"Svc{expect}"
    return Svc, SvcCfg


@pytest.mark.functional
class TestConfigAtScale:
    """Config injection at scale."""

    async def test_config_injection_on_wide_graph(self) -> None:
        from pydantic import BaseModel

        svcs: list[type] = []
        AppConfig = type("AppConfig", (BaseModel,), {})

        for i in range(100):
            svc_cls: type
            cfg_cls: type
            svc_cls, cfg_cls = _make_service_with_value(i)
            setattr(AppConfig, f"svc-{i}", cfg_cls(value=i))
            svcs.append(svc_cls)

        @module("Root", services=svcs)
        class Root:
            pass

        Root.__name__ = "Root"
        app = Canary(Root)
        await app.config(config=AppConfig())
        # All 100 on_config hooks passed assertions — no LifecycleHookError raised


@pytest.mark.functional
class TestStartupOrder:
    """Verify startup order is correct across topologies."""

    async def test_wide_tree_module_comes_first(self) -> None:
        """Module (no deps) has 0 in-degree so it enters BFS queue first."""
        root = _make_wide_tree(50)
        app = Canary(root)
        await app.config()

        order = app.startup_order
        assert order[0] == "WideRoot"
        assert set(order[1:]) == {f"leaf-{i}" for i in range(50)}

    async def test_chain_strict_ordering(self) -> None:
        """In a chain, each si must precede s(i+1)."""
        root = _make_chain(100)
        app = Canary(root)
        await app.config()

        order = app.startup_order
        for i in range(99):
            assert order.index(f"s{i}") < order.index(f"s{i + 1}")
