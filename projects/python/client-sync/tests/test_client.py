import httpx

from text_service.client import exchange


def test_request() -> None:
    # “->”表示函数返回值类型
    def respond(request: httpx.Request) -> httpx.Response:
        # request: httpx.Request：参数request的类型是httpx.Request
        assert request.url.path == "/texts"
        assert request.headers["Authorization"] == "Bearer example"
        return httpx.Response(200, json={"data": []})

    with httpx.Client(
        base_url="http://localhost",
        transport=httpx.MockTransport(respond),
        # MockTransport按照剧本直接处理请求并返回结果，不会真的发送请求（用于模拟测试）(mock单词本身就是模拟义)
        # NockTransport这里会自动给respond传入参数，不需要手动加
    ) as client:
        assert exchange(client, "GET", "/texts", "example") == (200, {"data": []})


def test_echo() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/echo"
        return httpx.Response(200, json={"data": []})

    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(respond)
    ) as client:
        assert exchange(client, "POST", "/echo", "") == (200, {"data": []})
