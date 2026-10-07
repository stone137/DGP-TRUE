"""发HTTP请求, 看看服务端返回的对不对"""

from collections.abc import AsyncGenerator  # 导入异步生成器类型

import pytest  # 测试框架
from httpx2 import ASGITransport, AsyncClient  # 导入httpx2的ASGI传输与异步客户端

from text_service.server import create_app  # 导入另外一个文件的create_app函数

pytestmark = pytest.mark.anyio
# 告诉测试运行器：这个测试是异步的，用异步方式跑


@pytest.fixture  # 测试的“准备工作”工具。需要什么就在这里造好，测试用完自动清理
def anyio_backend() -> str:
    return "asyncio"


# 指定异步测试运行在asyncio上


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:  # 异步产出AsyncClient
    app = create_app()  # 创建被测服务端（被测对象）
    async with (  # 组合多个异步上下文
        app.router.lifespan_context(app),  # 手动启动lifespan
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
        # 用ASGI直驱的HTTP客户端
    ):
        yield client  # 把客户端交给测试函数


# 验证HTTP路由行为
async def test_http_routes(client: AsyncClient) -> None:
    assert (await client.get("/ping")).status_code == 200
    response = await client.post("/users", json={"username": "alice", "password": "password1"})
    assert response.status_code == 201
    response = await client.post("/sessions", json={"username": "alice", "password": "password1"})
    token = response.json()["data"]["token"]
    assert (
        await client.get("/texts", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 200  # 带token访问，状态码200
    assert (await client.get("/texts")).status_code == 401  # 无token访问，状态码401
    assert (
        await client.post(
            "/users",
            content=b"not JSON",
            headers={"Content-Type": "application/json"},
            # b：表示这是一个字节串（bytes字面量前缀）
            # 提交非JSON字节（headers这么设置是为了让服务端按JSON解析路径处理，从而触发校验失败）
        )
    ).status_code == 400
    assert (
        await client.post(
            "/users",
            content=b"x" * 524289,
            headers={"Content-Type": "application/json"},
            # 提交过大字节
        )
    ).status_code == 413


async def test_task3(client: AsyncClient) -> None:
    assert (
        await client.post("/users", json={"username": "alice", "password": "password1"})
    ).status_code == 201
    token = (
        await client.post("/sessions", json={"username": "alice", "password": "password1"})
    ).json()["data"]["token"]

    # 上传后读回原文
    await client.put(
        "/texts/note", json={"text": "alice"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert (
        await client.get("/texts/note", headers={"Authorization": f"Bearer {token}"})
    ).json() == {"data": "alice"}

    # 同名再次上传后读回新内容
    await client.put(
        "/texts/note", json={"text": "alice2"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert (
        await client.get("/texts/note", headers={"Authorization": f"Bearer {token}"})
    ).json() == {"data": "alice2"}

    # 不存在的文本返回 404
    assert (
        await client.get("/texts/note_missing", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 404


async def test_task4(client: AsyncClient) -> None:
    assert (
        await client.post("/users", json={"username": "alice", "password": "password1"})
    ).status_code == 201
    token = (
        await client.post("/sessions", json={"username": "alice", "password": "password1"})
    ).json()["data"]["token"]
    assert (
        await client.post("/users", json={"username": "bob", "password": "password1"})
    ).status_code == 201
    token2 = (
        await client.post("/sessions", json={"username": "bob", "password": "password1"})
    ).json()["data"]["token"]
    await client.put(
        "/texts/note", json={"text": "alice"}, headers={"Authorization": f"Bearer {token}"}
    )
    await client.put("/texts/c", json={"text": "c"}, headers={"Authorization": f"Bearer {token}"})
    await client.put("/texts/a", json={"text": "a"}, headers={"Authorization": f"Bearer {token}"})
    assert (
        await client.get("/texts/note", headers={"Authorization": f"Bearer {token}"})
    ).json() == {"data": "alice"}
    assert (
        await client.put(
            "/texts/note", json={"text": "bob"}, headers={"Authorization": f"Bearer {token2}"}
        )
    ).status_code == 200  # 写互不影响
    assert (
        await client.get("/texts/note", headers={"Authorization": f"Bearer {token2}"})
    ).json() == {"data": "bob"}  # 读互不影响
    await client.delete("/texts/note", headers={"Authorization": f"Bearer {token2}"})
    assert (
        await client.get("/texts/note", headers={"Authorization": f"Bearer {token2}"})
    ).status_code == 404  # 删除互不影响
    assert (await client.get("/texts", headers={"Authorization": f"Bearer {token}"})).json() == {
        "data": ["a", "c", "note"]
    }  # 列出互不影响 + 满足名称升序
    assert (await client.get("/texts", headers={"Authorization": f"Bearer {token2}"})).json() == {
        "data": []
    }  # 删除后列表为空
    assert (
        await client.delete("/texts/note", headers={"Authorization": f"Bearer {token2}"})
    ).status_code == 404


async def test_task5(client: AsyncClient) -> None:
    assert (
        await client.post("/users", json={"username": "alice", "password": "password1"})
    ).status_code == 201
    token = (
        await client.post("/sessions", json={"username": "alice", "password": "password1"})
    ).json()["data"]["token"]
    await client.put(
        "/texts/note", json={"text": "alice"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert (
        await client.delete("/users/me", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 200
    assert (
        await client.get("/texts", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 401  # 旧令牌失效
    assert (
        await client.post("/users", json={"username": "alice", "password": "password1"})
    ).status_code == 201
    token2 = (
        await client.post("/sessions", json={"username": "alice", "password": "password1"})
    ).json()["data"]["token"]
    assert (await client.get("/texts", headers={"Authorization": f"Bearer {token2}"})).json() == {
        "data": []
    }  # 全部文本清理：同名重建后新账号列表为空


# 验证服务器对非法JSON（普通错误，\xff编码错误，NaN非法常量）一律返回400
@pytest.mark.parametrize("body", [b"not JSON", b"\xff", b"NaN"])
# 参数化：分别用这三种字节作body
async def test_invalid_json(client: AsyncClient, body: bytes) -> None:
    # 异步测试，接受客户端与body
    assert (await client.post("/users", content=body)).status_code == 400


# 验证body大小边界，404/405路由与方法处理、以及查询参数不影响响应
async def test_body_limit_and_routing(client: AsyncClient) -> None:
    exact = b"{}" + b" " * (524288 - 2)  # 正好52488字节，但是只含空格
    assert (await client.post("/users", content=exact)).status_code == 400  # 只含空格返回400
    assert (await client.post("/users", content=exact + b" ")).status_code == 413  # 过大返回413
    assert (await client.get("/missing")).status_code == 404  # 路径不存在
    assert (await client.get("/echo")).status_code == 405  # 方法不允许
    assert (await client.patch("/ping")).status_code == 405
    assert (await client.get("/ping?test=1")).json() == {"data": "pong"}  # 查询参数不影响响应


# 验证方法不匹配优先于鉴权
@pytest.mark.parametrize("path", ["/ping", "/users", "/sessions", "/sessions/current", "/texts"])
# 参数化，依次用这五个路径
async def test_wrong_method_precedes_authentication(client: AsyncClient, path: str) -> None:
    assert (
        await client.patch(path)
    ).status_code == 405  # patch（局部更新资源，不存在这个方法）这些路径都应405
