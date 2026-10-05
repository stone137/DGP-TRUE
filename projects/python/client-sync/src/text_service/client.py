import argparse
import getpass
from typing import Any

import httpx


def exchange(  # object是类型注释，表示body可以是任何类型
    client: httpx.Client, method: str, path: str, token: str = "", body: object = None
) -> tuple[int, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    # 压行写法，三元表达式。headers在此处是个字典
    # header像是快递包裹（HTTP请求）上的标签，门卫（服务端）据此决定如何处理包裹（HTTP请求）
    # Bearer像是通行证上的“持证人”三个字，让门卫（服务端）一看就知道这是通行令牌格式，然后再核对后面的token

    response = client.request(method, path, json=body, headers=headers)
    # response是门卫（服务端）给的回执单（httpx中返回的httpx响应对象）
    # client.request把参数组装成HTTP请求发送给服务器，并返回响应对象
    # json=body把body自动序列化为json字符串（它就是按照JSON格式序列化后的文本。e.g.{"name": "Tom"}作为请求体发送
    # headers=header是用来把构造好的headers作为请求头加上去（请求头包含通行证，但它不只是通行证。但是在这段代码中，它只放了通行证）

    try:  # 发送请求，尝试解析json（把json字符串转化为Python的字典、列表等对象）
        result = response.json()
    except ValueError:  # 如果解析失败，把原始文本包装成{"message": ...}
        result = {"message": response.text}
    return response.status_code, result  # 最后返回元组！


def main() -> None:
    parser = argparse.ArgumentParser()
    # parser是一个参数解析器的变量名，可以读取并解析命令行输入
    parser.add_argument("--url", default="http://127.0.0.1:7878")
    # 向参数解析器注册一个命令行参数（像是点外卖时的备注栏）“--url”，默认值是http://127.0.0.1:7878
    args = parser.parse_args()
    # 解析命令行输入（使用parser），把--url等参数提取到args对象中
    token = ""
    with httpx.Client(
        base_url=args.url,
        timeout=12,
        follow_redirects=False,
        trust_env=False,
        # with的()里面初始化了一个httpx客户端实例
        # httpx.Client时httpx提供的同步HTTP客户端类，用来发送请求和管理链接
        # 用args.url作为基础地址创建httpx客户端，12秒超时，不跟随重定向，不读取环境代理
    ) as client:  # 给刚刚创建的httpx客户端实例临时取名取名为client
        try:
            while True:
                command = input(
                    "ping / register / login / logout / list / echo / "
                    "delete-user / put / get / delete / q > "
                ).strip()
                # .strip()去除字符串首尾的空白字符（空格，换行等）
                body = None
                if command == "q":
                    break
                if command in ("register", "login"):
                    body = {
                        "username": input("username: "),
                        "password": getpass.getpass("password: "),
                    }
                    method, path = "POST", "/users" if command == "register" else "/sessions"
                elif command in ("ping", "logout", "list"):
                    method, path = {
                        "ping": ("GET", "/ping"),
                        "logout": ("DELETE", "/sessions/current"),
                        "list": ("GET", "/texts"),
                    }[command]
                elif command == "echo":
                    print("Please enter the text (end with a ':' on its own line): ")
                    text = ""
                    while True:
                        line = input()
                        if line == ":":
                            break
                        text += line + "\n"
                    body = {"text": text}
                    method, path = "POST", "/echo"
                elif command == "put":
                    name = input("name: ")
                    print("Please enter the text (end with a ':' on its own line): ")
                    text = ""
                    while True:
                        line = input()
                        if line == ":":
                            break
                        text += line + "\n"
                    body = {"text": text}
                    method, path = "PUT", f"/texts/{name}"
                elif command == "get":
                    name = input("name: ")
                    body = None
                    method, path = "GET", f"/texts/{name}"
                elif command == "delete":
                    name = input("name: ")
                    body = None
                    method, path = "DELETE", f"/texts/{name}"
                elif command == "delete-user":
                    body = None
                    method, path = "DELETE", "/users/me"
                else:
                    print("Unknown command.")
                    continue
                try:
                    status, result = exchange(client, method, path, token, body)
                    print(status, result)
                    if command == "login" and status == 200:
                        token = result["data"]["token"]
                    if status == 401:
                        print("Please log in again.")
                    if status == 401 or (command == "logout" and status == 200):
                        token = ""
                    if command == "delete-user" and status == 200:
                        token = ""
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    print(f"Request failed: {exc}")
        except (EOFError, KeyboardInterrupt):
            print()
