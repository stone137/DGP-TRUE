"""看看业务本身对不对"""

from text_service.service import Service  # 从另外一个文件中导入Service类


def test_account_lifecycle() -> None:
    service = Service()
    account = {"username": "alice", "password": "password1"}
    assert service.handle("GET", "/ping", None, "") == (200, {"data": "pong"})
    assert service.handle("POST", "/users", account, "")[0] == 201  # 注册返回201
    assert service.handle("POST", "/users", account, "")[0] == 409  # 重复注册返回409
    assert (
        service.handle("POST", "/sessions", {**account, "password": "incorrect"}, "")[0] == 401
    )  # 密码错误返回401
    token = service.handle("POST", "/sessions", account, "")[1]["data"][
        "token"
    ]  # 取登录返回的token
    next_token = service.handle("POST", "/sessions", account, "")[1]["data"][
        "token"
    ]  # 再登录拿一个新的token
    assert token != next_token  # 确认两个token不一样
    assert service.handle("GET", "/texts", None, f"Bearer {token}")[0] == 401  # 旧token访问返回401
    assert service.handle("GET", "/texts", None, f"Bearer {next_token}") == (
        200,
        {"data": []},
    )  # 新token正常访问
    assert (
        service.handle("DELETE", "/sessions/current", None, f"Bearer {next_token}")[0] == 200
    )  # 退出登录
    assert (
        service.handle("GET", "/texts", None, f"Bearer {next_token}")[0] == 401
    )  # 退出登录后无法再次访问


def test_validation() -> None:  # 验证注册接口对各种非法输入都返回400
    service = Service()
    for body in (
        None,
        [],  # 不是字典
        {},  # 缺字段
        {"username": True, "password": "password1"},  # 类型错
        {"username": "a/b", "password": "password1"},  # 含非法字符
    ):
        assert service.handle("POST", "/users", body, "")[0] == 400


def test_concurrent_registration() -> (
    None
):  # 验证同名并发注册下，业务层能正确保证只有一个201，其余409
    from concurrent.futures import ThreadPoolExecutor
    # 导入线程池

    service = Service()
    body = {"username": "alice", "password": "password1"}
    with ThreadPoolExecutor(max_workers=4) as pool:  # 4个线程
        statuses = list(pool.map(lambda _: service.handle("POST", "/users", body, "")[0], range(4)))
        # 并发调4次注册，取状态码
        # list()：转列表，pool.map()：线程池并发执行，lambda _：忽略参数，[0]：返回元组的状态码，range(4)：执行4次
    assert sorted(statuses) == [201, 409, 409, 409]


def test_echo() -> None:
    service = Service()
    for body in (
        {},  # 缺字段
        {"text": "你好\nRM", "extra": "this is a test"},  # 多余字段
        {"text": 123},
    ):
        assert service.handle("POST", "/echo", body, "")[0] == 400


def test_task5() -> None:
    from concurrent.futures import ThreadPoolExecutor

    service = Service()
    account = {"username": "alice", "password": "password1"}
    assert service.handle("POST", "/users", account, "")[0] == 201
    token = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        delete = pool.submit(service.handle, "DELETE", "/users/me", None, f"Bearer {token}")
        write = pool.submit(service.handle, "PUT", "/texts/note", {"text": "x"}, f"Bearer {token}")
        assert delete.result()[0] == 200
        assert write.result()[0] == 401

    with ThreadPoolExecutor(max_workers=3) as pool:
        old_login = pool.submit(service.handle, "POST", "/sessions", account, "")
        pool.submit(service.handle, "DELETE", "/users/me", None, f"Bearer {token}")
        pool.submit(service.handle, "POST", "/users", account, "")
        assert old_login.result()[0] == 401


def test_task6() -> None:
    from time import sleep

    service = Service(token_ttl_seconds=1)
    account = {"username": "alice", "password": "password1"}
    assert service.handle("POST", "/users", account, "")[0] == 201
    token = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]

    sleep(1.1)
    assert service.handle("GET", "/texts", None, f"Bearer {token}")[0] == 401
    assert service.handle("GET", "/texts", None, f"Bearer {token}")[0] == 401  # 操作不续期
    new_token = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]
    assert new_token != token  # 重新登录替换令牌

    assert service.handle("DELETE", "/sessions/current", None, f"Bearer {new_token}")[0] == 200
    assert (
        service.handle("GET", "/texts", None, f"Bearer {new_token}")[0] == 401
    )  # 退出能够撤销令牌

    token3 = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]
    assert service.handle("DELETE", "/users/me", None, f"Bearer {token3}")[0] == 200
    assert service.handle("GET", "/texts", None, f"Bearer {token3}")[0] == 401  # 注销能够撤销令牌


def test_task7() -> None:
    from concurrent.futures import ThreadPoolExecutor

    service = Service()
    account = {"username": "alice", "password": "password1"}
    service.handle("POST", "/users", account, "")

    # 文本操作与登录替换竞争时的状态一致性
    token = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.submit(service.handle, "PUT", "/texts/note", {"text": "x"}, f"Bearer {token}")
        pool.submit(service.handle, "POST", "/sessions", account, "")

    new_token = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]
    assert service.handle("GET", "/texts/note", None, f"Bearer {new_token}") in (
        (200, {"data": "x"}),
        (404, {"message": "text not found"}),
    )

    # 文本操作与注销竞争时的状态一致性
    token2 = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.submit(service.handle, "PUT", "/texts/note", {"text": "x"}, f"Bearer {token2}")
        pool.submit(service.handle, "DELETE", "/users/me", None, f"Bearer {token2}")

    assert service.handle("GET", "/texts/note", None, f"Bearer {token2}")[0] == 401
    assert service.handle("POST", "/sessions", account, "")[0] == 401

    # 单个请求失败后，业务仍能正常进行
    service.handle("POST", "/users", account, "")
    token3 = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]
    service.handle("PATCH", "/ping", None, "")
    service.handle("GET", "/nope", None, "")
    service.handle("PUT", "/texts/note", {"wrong": "field"}, f"Bearer {token3}")
    service.handle("PUT", "/texts/bad/name", {"text": "x"}, f"Bearer {token3}")
    assert service.handle("PUT", "/texts/note", {"text": "hi"}, f"Bearer {token3}")[0] == 200
    assert service.handle("GET", "/texts/note", None, f"Bearer {token3}") == (200, {"data": "hi"})
