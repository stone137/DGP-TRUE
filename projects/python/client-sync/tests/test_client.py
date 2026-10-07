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
        return httpx.Response(200, json={"data": "what i want to echo"})

    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(respond)
    ) as client:
        assert exchange(client, "POST", "/echo", "") == (200, {"data": "what i want to echo"})


def test_task3() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/texts/note"
        assert request.headers["Authorization"] == "Bearer example"
        return (
            httpx.Response(200, json={"data": None})
            if request.method == "PUT"
            else httpx.Response(200, json={"data": "y = x"})
        )

    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(respond)
    ) as client:
        assert exchange(client, "PUT", "/texts/note", "example", {"text": "y = x"}) == (
            200,
            {"data": None},
        )
        assert exchange(client, "GET", "/texts/note", "example") == (200, {"data": "y = x"})


def test_task4() -> None:
    texts: dict[str, str] = {"b": "y", "a": "x", "c": "z"}

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer example"
        if request.method == "GET" and request.url.path == "/texts":
            return httpx.Response(200, json={"data": sorted(texts)})
        name = request.url.path.removeprefix("/texts/")
        if name not in texts:
            return httpx.Response(404, json={"message": "text not found"})
        if request.method == "DELETE":
            del texts[name]
            return httpx.Response(200, json={"data": None})
        if request.method == "GET":
            return httpx.Response(200, json={"data": texts[name]})
        return httpx.Response(404, json={"message": "Not found"})

    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(respond)
    ) as client:
        assert exchange(client, "GET", "/texts", "example") == (200, {"data": ["a", "b", "c"]})
        assert exchange(client, "DELETE", "/texts/b", "example") == (200, {"data": None})
        assert exchange(client, "GET", "/texts", "example") == (200, {"data": ["a", "c"]})
        assert exchange(client, "DELETE", "/texts/missing", "example") == (
            404,
            {"message": "text not found"},
        )
        assert exchange(client, "GET", "/texts/missing", "example") == (
            404,
            {"message": "text not found"},
        )


def test_task5() -> None:
    texts: dict[str, str] = {"b": "y", "a": "x", "c": "z"}
    valid_token: dict[str, str] = {"token": "example"}

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE" and request.url.path == "/users/me":
            assert request.headers["Authorization"] == "Bearer example"
            texts.clear()
            valid_token.clear()
            return httpx.Response(200, json={"data": None})
        if request.method == "POST" and request.url.path == "/sessions":
            valid_token["token"] = "example2"
            return httpx.Response(200, json={"data": "example2"})
        if request.method == "GET" and request.url.path == "/texts":
            if valid_token:
                if valid_token["token"] == "example":
                    return httpx.Response(200, json={"data": ["a", "b", "c"]})
                if valid_token["token"] == "example2":
                    return httpx.Response(200, json={"data": []})
            return httpx.Response(401, json={"message": "Please log in again"})
        return httpx.Response(404, json={"message": "Not found"})

    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(respond)
    ) as client:
        assert exchange(client, "DELETE", "/users/me", "example") == (200, {"data": None})
        assert exchange(client, "GET", "/texts", "example") == (
            401,
            {"message": "Please log in again"},
        )
        assert exchange(client, "POST", "/sessions", "") == (200, {"data": "example2"})
        assert exchange(client, "GET", "/texts", "example2") == (200, {"data": []})


def test_task6() -> None:
    # 错误体确实或不是json仍能显示 HTTP 状态
    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/texts":
            return httpx.Response(404, json="I'm not json hahahahahaha")
        return httpx.Response(404, json="")

    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(respond)
    ) as client:
        assert exchange(client, "PUT", "/texts/notes", "example") == (404, "")
        assert exchange(client, "GET", "/texts", "") == (404, "I'm not json hahahahahaha")
