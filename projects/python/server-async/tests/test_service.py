from text_service.service import Service  # 从另外一个文件中导入Service类


def test_account_lifecycle() -> None:
    service = Service()
    account = {"username": "alice", "password": "password1"}
    assert service.handle("GET", "/ping", None, "") == (200, {"data": "pong"})
    assert service.handle("POST", "/users", account, "")[0] == 201  # 注册返回201
    assert service.handle("POST", "/users", account, "")[0] == 409  # 重复注册返回409
    assert service.handle("POST", "/sessions", {**account, "password": "incorrect"}, "")[0] == 401  # 密码错误返回401
    token = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]  # 取登录返回的token
    next_token = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]  # 再登录拿一个新的token
    assert token != next_token  # 确认两个token不一样
    assert service.handle("GET", "/texts", None, f"Bearer {token}")[0] == 401  # 旧token访问返回401
    assert service.handle("GET", "/texts", None, f"Bearer {next_token}") == (200, {"data": []})  # 新token正常访问
    assert service.handle("DELETE", "/sessions/current", None, f"Bearer {next_token}")[0] == 200  # 退出登录
    assert service.handle("GET", "/texts", None, f"Bearer {next_token}")[0] == 401  # 退出登录后无法再次访问


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


def test_concurrent_registration() -> None:  # 验证同名并发注册下，业务层能正确保证只有一个201，其余409
    from concurrent.futures import ThreadPoolExecutor
    # 导入线程池

    service = Service()
    body = {"username": "alice", "password": "password1"}
    with ThreadPoolExecutor(max_workers=4) as pool:  # 4个线程
        statuses = list(pool.map(lambda _: service.handle("POST", "/users", body, "")[0], range(4)))
        # 并发调4次注册，取状态码
        # list()：转列表，pool.map()：线程池并发执行，lambda _：忽略参数，[0]：返回元组的状态码，range(4)：执行4次
    assert sorted(statuses) == [201, 409, 409, 409]
