# What's New in 1.3

1.3 adds WebSocket endpoints to application units. Existing code needs no changes.

For earlier releases, see [What's New in 1.2](whats-new-1.2.md),
[What's New in 1.1](whats-new-1.1.md) and [What's New in 1.0](whats-new-1.0.md).

## WebSocket endpoints

`@websocket` marks a method as a WebSocket endpoint, written in the same router as HTTP
endpoints:

```python
from canary_framework import Canary, dep, init
from canary_framework.web.asgi.app import App, HTTPError, Router, WebSocket, get, websocket
from canary_framework.web.asgi.server import Server


class Rooms(Canary):
    @init
    def open(self) -> None:
        self.log: dict[str, list[str]] = {}


class RoomApi(Router, prefix="/rooms"):
    rooms = dep(Rooms)

    @get("/{room}")
    async def history(self, room: str) -> list[str]:
        return self.rooms.log.get(room, [])

    @websocket("/{room}")
    async def chat(self, socket: WebSocket, room: str, name: str) -> None:
        if not name.isidentifier():
            raise HTTPError(403, "bad name")        # before the handshake: the client gets 403
        async for message in socket:                # ends normally when the client leaves
            self.rooms.log.setdefault(room, []).append(f"{name}: {message}")
            await socket.send(f"{name}: {message}")


class ChatApi(App):
    rooms = dep(RoomApi)


class Gateway(Server):
    api = dep(ChatApi)
    port = 8010
```

- Path and query parameters are bound and validated as for HTTP endpoints; a parameter
  annotated `WebSocket` is the connection itself.
- The handshake is accepted on the first receive or send. A failure before it — no matching
  path, a failed validation, an `HTTPError` — is answered with the same error response as over
  HTTP; after it, an `HTTPError` closes with 1008 and anything else closes with 1011 and is
  logged.
- One path may have both an HTTP endpoint and a WebSocket endpoint.

See [Web application › WebSocket](extensions/app.md#websocket) for the details.

## Worth knowing

These show only once you use WebSocket:

- WebSocket endpoints appear in `App.endpoints` with the method `"WEBSOCKET"`. Code that writes
  OpenAPI from that table should skip them; the example under
  [the endpoint table](extensions/app.md#endpoints) now does.
- A WebSocket connection to an application unit with no matching WebSocket endpoint used to be
  closed with 1008 (the client saw 403); it is now answered with 404 where the server supports
  it.
- `canary-framework[server]` now installs `wsproto`, and the server unit uses it for WebSocket
  by default. [Web server](extensions/server.md) says why.

## Also in 1.3

- [Why Canary](why-canary.md) is re-measured with 1.2.0; the Canary column is unchanged.
- The full list is in the
  [changelog](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CHANGELOG.md).
