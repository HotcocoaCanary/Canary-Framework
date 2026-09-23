# What's New in 1.0

1.0 is the first stable release. The API introduced in 0.10 is now covered by
[Semantic Versioning](versioning.md): no breaking changes until 2.0, and anything removed is
deprecated for at least one minor release first.

Coming from 0.9.x? Start with [Upgrading from 0.9.x](upgrading-from-0.9.md).

## Replacing a dependency across the graph

`Scope.provide()` makes one instance stand in for a dependency everywhere in the graph — the
supported way to use test doubles:

```python
service = UserService()
scope_of(service).provide(Database, FakeDatabase())

async with service:
    assert service.repository.database is service.database     # both the fake
```

The provided unit runs its own hooks and enters the dependencies its own class declares.

Assigning to a dependency attribute now raises `AttributeError` pointing to `provide()`. In
0.10 it silently replaced that one attribute while the rest of the graph, and the lifecycle,
kept the original.

## Starting again

`stop()` undoes `start`, so the same graph can start again. `@init` is not rerun:

```python
async with service:     # init, start, stop
    ...
async with service:     # start, stop
    ...
```

In 0.10 the second `start()` returned without running anything.

## Retrying a failure

A failed or cancelled advance no longer leaves a record, so calling it again runs it again. In
0.10 every later call re-raised the first exception. Relatedly, `start()` after a failed
`init()` now raises `LifecycleError` instead of proceeding.

## Upgrading from 0.10

| 0.10 | 1.0 |
|---|---|
| `service.database = FakeDatabase()` | `scope_of(service).provide(Database, FakeDatabase())` before the lifecycle begins |
| `for unit in scope.entered["start"]` | `for unit in scope.entered["start"].values()` — keyed by type |
| Build a new root to restart | Call `start()` again on the same root |
