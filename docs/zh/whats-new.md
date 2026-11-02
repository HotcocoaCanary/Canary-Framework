# 1.3 新特性

1.3 给应用单元加上了 WebSocket 接口。已有代码不需要改动。

更早版本的变化见 [1.2 新特性](whats-new-1.2.md)、[1.1 新特性](whats-new-1.1.md) 与
[1.0 新特性](whats-new-1.0.md)。

## WebSocket 接口

`@websocket` 把方法标记为 WebSocket 接口，和 HTTP 接口写在同一个路由单元里：

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
            raise HTTPError(403, "bad name")        # 握手之前：客户端收到 403
        async for message in socket:                # 对端离开时正常结束
            self.rooms.log.setdefault(room, []).append(f"{name}: {message}")
            await socket.send(f"{name}: {message}")


class ChatApi(App):
    rooms = dep(RoomApi)


class Gateway(Server):
    api = dep(ChatApi)
    port = 8010
```

- 路径参数、查询参数和 HTTP 接口一样绑定、校验；注解为 `WebSocket` 的形参是连接本身。
- 第一次收发时自动接受握手。握手之前出错（路径不匹配、校验失败、`HTTPError`）应答和 HTTP
  接口一样的错误响应；之后出错，`HTTPError` 以 1008 关闭，其余以 1011 关闭并记日志。
- 同一路径可以同时有 HTTP 接口和 WebSocket 接口。

细节见 [Web 应用 › WebSocket](extensions/app.md#websocket)。

## 需要留意

这些变化只在用到 WebSocket 时才看得到：

- `App.endpoints` 里会出现 WebSocket 接口，`method` 是 `"WEBSOCKET"`。照着这张表生成 OpenAPI
  的代码要跳过它们，[接口表](extensions/app.md#endpoints)里的示例已经加上了这一行。
- 发给应用单元、却没有对应 WebSocket 接口的连接，此前一律以 1008 关闭（客户端看到 403）；
  现在服务器支持时应答 404。
- `canary-framework[server]` 一并装上 `wsproto`，服务器单元默认用它实现 WebSocket。原因见
  [Web 服务器](extensions/server.md)。

## 1.3 还有

- [为什么选 Canary](why-canary.md) 用 1.2.0 重新实测，Canary 一列结果不变。
- 完整清单见
  [变更日志](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CHANGELOG.md)。
