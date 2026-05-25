# 最小示例：一个服务 + 一个模块，无配置、无 Web
import asyncio

from cf import Canary, Context, module, on_init, on_start, service


@service(name="hello")
class HelloService:
    @on_init
    def init(self, ctx: Context):
        print("hello init")

    @on_start
    def start(self):
        print("hello start")


@module(name="App", services=[HelloService])
class App:
    pass


async def main():
    app = Canary(App)
    await app.init()
    await app.start()


if __name__ == "__main__":
    asyncio.run(main())
