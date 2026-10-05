import httpx

from text_service.client import exchange


def test_request() -> None:
    # “->”表示函数返回值类型
    def respond(request: httpx.Request) -> httpx.Response:
        # respond函数相当于剧本：模拟服务端处理并返回数据
        # request: httpx.Request：参数request的类型是httpx.Request
        # httpx.Response是httpx的响应对象，包含状态码，响应头，响应体等（门卫给的回执单，里面写明处理结果和返回内容）
        assert request.url.path == "/texts"
        assert request.headers["Authorization"] == "Bearer example"
        return httpx.Response(200, json={"data": []})
        # 是用exchange里面传入的参数，去跑这个respond函数。弄清这个逻辑顺序

    with httpx.Client(
        base_url="http://localhost",
        # 设置客户端的基础地址为http://localhost（指向本机自身的地址）
        transport=httpx.MockTransport(respond),
        # MockTransport按照剧本直接处理请求并返回结果，不会真的发送请求（用于模拟测试）(mock单词本身就是模拟义)
        # NockTransport这里会自动给respond传入参数，不需要手动加
    ) as client:
        assert exchange(client, "GET", "/texts", "example") == (200, {"data": []})
        # 上下都是“example”，保持一致


def test_echo() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/echo"
        return httpx.Response(200, json={"data": []})

    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(respond)
    ) as client:
        assert exchange(client, "POST", "/echo", "") == (200, {"data": []})


def test_401_response() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return httpx.Response(401, json={"message": "Please log in again."})

    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(respond)
    ) as client:
        assert exchange(client, "GET", "/texts", "") == (401, {"message": "Please log in again."})


def test_error_or_nonjson() -> None:
    # 错误体缺失或不是 JSON 时仍能显示 HTTP 状态（就是404这类数字）
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(respond)
    ) as client:
        assert exchange(client, "GET", "/texts", "") == (404, {"message": "Not Found"})
