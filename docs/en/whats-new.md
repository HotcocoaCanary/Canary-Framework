# What's New in 1.1

1.1 rebuilds the engine on an explicit dependency graph. `init()`, `start()`, `stop()` and
`async with` work as before; two changes break code that drove the engine directly, and both
are listed first. Everything else is behaviour you get for free.

Coming from 1.0? Read the two breaking changes. Coming from 0.9.x? Start with
[Upgrading from 0.9.x](upgrading-from-0.9.md); the [1.0 notes](whats-new-1.0.md) cover the
release in between.

## Breaking: the engine functions are renamed

`Canary`'s methods are thin wrappers over two functions, which phases of your own call
directly. They are now named for what they do:

| 1.0 | 1.1 |
|---|---|
| `advance(unit, phase)` | `enter(unit, phase)` |
| `unwind(scope_of(unit), rollback, undoing=migrate)` | `leave(unit, migrate)` |
| — | `Phase("migrate", after=init, leave=rollback)` |

`leave()` follows the same rules as `stop()` — the unit first, then its dependencies — and
raises an `ExceptionGroup` when leave hooks fail, where `unwind()` returned a list. A phase now
names the phase that runs when it is left with `leave=`; `start`'s is `stop`.

```python
rollback = Phase("rollback")
migrate = Phase("migrate", after=init, leave=rollback)

await enter(unit, migrate)      # runs @migrate, dependencies first
await leave(unit, migrate)      # runs @rollback, the unit first
```

## Breaking: `stop()` on a unit still in use does nothing

`stop()` is a unit action: it stops the unit it is called on, then tries each of its
dependencies the same way. A unit that something still uses — a dependent that is starting,
running or stopping — is skipped, without an error. In 1.0 `stop()` on *any* unit reclaimed the
whole graph.

```python
async with service:
    await service.database.stop()   # 1.0: stopped everything. 1.1: nothing — service uses it.
```

To stop everything, stop the root: `await service.stop()`. That is what `async with` does.

## A failed `start()` cleans up after itself

A unit whose `@start` raises runs its own `@stop` at once. Units that depend on it do not
start, and release the dependencies they were waiting on. `start()` raises only after
everything it brought up has been released:

```
C.start → A.start → B.start ✗ → B.stop → A.stop → C.stop → start() raises B's error
```

Retrying is now just calling `start()` again — no `stop()` in between. Units starting alongside
the failed one are not cancelled: they finish, then are released if nothing else uses them.

## Cycles are caught before anything runs

The dependency graph is built when a unit is first entered, so a cycle — or a unit that has not
entered its predecessor phase — is reported before any hook runs. In 1.0, hooks on unrelated
branches could run before the error surfaced.

## Shared dependencies stay up until their last user stops

```python
await root.left.start()
await root.right.start()    # both use Shared
await root.left.stop()      # left stops; Shared stays — right still needs it
await root.right.stop()     # right, then Shared
```

## Also in 1.1

- Python 3.15 is tested in CI and listed in the classifiers.
- `Scope.key_of(unit)`, `Scope.entered(phase)`, and `Scope.graph` / `Scope.dependents` /
  `Scope.tracks` for inspecting the graph and each unit's state.
- Three engine bugs found by the new randomised lifecycle tests are fixed; see the
  [changelog](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CHANGELOG.md).
- [Why Canary](why-canary.md): where the framework fits, where it does not, and a measured
  comparison with dishka, dependency-injector, injector and FastAPI `Depends`.
