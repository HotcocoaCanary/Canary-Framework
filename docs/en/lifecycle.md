# Lifecycle

A Canary's lifecycle builds on Python's native object and context-manager protocols.

## The two user hooks

| User declaration | Python protocol | Meaning |
|---|---|---|
| `__init__` | object construction | construct the instance and inject dependencies |
| `@start` | `__aenter__` | enter the running state |
| `@stop` | `__aexit__` | leave the running state |

`@start` and `@stop` are optional. The framework maps `@start` onto `__aenter__` and `@stop` onto `__aexit__`, so a Canary is an async context manager.

## State machine

Each Canary instance tracks its state:

```
NEW ──▶ INITIALIZED ──▶ STARTING ──▶ RUNNING ──▶ STOPPING ──▶ STOPPED
                            │                     │
                            └───────▶ FAILED ◀───────┘
```

The state machine guarantees that lifecycle operations run in a legal order. For example, a Canary already `RUNNING` cannot be started again:

```python
await database.__aenter__()
await database.__aenter__()  # LifecycleError: must be initialized before entering
```

## Hook ordering under a Flock

A `Flock` drives the graph in topological order. For `APIService → UserService → Database`:

- **Construction** (dependency-first): `Database.__init__` → `UserService.__init__` → `APIService.__init__`.
- **Startup** (dependency-first): `Database.__aenter__` → `UserService.__aenter__` → `APIService.__aenter__`.
- **Shutdown** (reverse): `APIService.__aexit__` → `UserService.__aexit__` → `Database.__aexit__`.

Any Canary starts only after all of its dependencies are running; any Canary stops before its dependencies do.

## Startup rollback

If a Canary fails to start, the `Flock` stops every already-running Canary in reverse order and raises `StartupError`:

```
Database started → UserService started → APIService starting (fails)
APIService FAILED → UserService.__aexit__ → Database.__aexit__
```

Canaries that never reached `RUNNING` are marked `FAILED`; those that did are cleanly stopped.
