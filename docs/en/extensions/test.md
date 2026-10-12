# Testing

`canary_framework.test` is two test helpers. It depends on the core only — nothing extra to
install — and is not tied to any test framework.

```python
from canary_framework.test import running, unit
```

!!! note "Provisional API"
    Extensions may change in a minor release until they are declared stable — see
    [Versioning & Compatibility](../versioning.md#extensions).

## `running`: start a graph on test doubles

```python
async def test_alerts_fire_after_the_window() -> None:
    clock = ManualClock()
    async with running(TelemetryDaemon, {Clock: clock}) as daemon:
        clock.advance(30)
        ...
```

It constructs a fresh root, registers the doubles in its scope, starts the whole graph and
reclaims it on exit. Every call is a new graph; tests share no instances.

Doubles are registered with [`Scope.provide`](../patterns.md#test-doubles), so:

- the replaced unit is **never constructed**, and nothing starts on its behalf;
- the double takes part in the lifecycle as its own type: it runs its own hooks and enters the
  dependencies it declares;
- a double must be an instance of the type it replaces, or `TypeError` is raised before any
  unit starts.

## `unit`: reach a unit by its type

```python
async with running(TelemetryDaemon) as daemon:
    store = unit(daemon, MetricStore)
```

Everyday code reads a dependency from the unit that declares it (`daemon.collector.store`).
Tests often need a unit they never declared a dependency on — that is what `unit` is for. The
first argument can be any unit of the graph.

The graph is built when the lifecycle first begins; asking for a unit that is not there yet
raises `LookupError`.
