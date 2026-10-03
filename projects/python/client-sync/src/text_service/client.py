import argparse
import getpass
from typing import Any

import httpx


def exchange(
    client: httpx.Client, method: str, path: str, token: str = "", body: object = None
) -> tuple[int, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}  # 压行写法，三元表达式
    response = client.request(method, path, json=body, headers=headers)
    try:
        result = response.json()
    except ValueError:
        result = {"message": response.text}
    return response.status_code, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:7878")
    args = parser.parse_args()
    token = ""
    with httpx.Client(
        base_url=args.url, timeout=12, follow_redirects=False, trust_env=False
    ) as client:
        try:
            while True:
                command = input(
                    "ping / register / login / logout / list / echo / "
                    "delete-user / put / get / delete / q > "
                ).strip()
                body = None
                if command == "q":
                    break
                if command in ("register", "login"):
                    body = {
                        "username": input("username: "),
                        "password": getpass.getpass("password: "),
                    }
                    method, path = "POST", "/users" if command == "register" else "/sessions"
                elif command in (
                    "ping",
                    "logout",
                    "list",
                ):  # 检查command里的字符串存不存在这个元组里
                    method, path = {
                        "ping": ("GET", "/ping"),
                        "logout": ("DELETE", "/sessions/current"),
                        "list": ("GET", "/texts"),
                    }[command]  # `{...}[command]` 表示"从字典里取command这个键对应的值"。
                elif command == "echo":  # 任务一：补全POST /echo
                    print("Please enter the text (end with a ':' on its own line): ")
                    text = ""
                    while True:
                        line = input()
                        if line == ":":
                            break
                        text += line + "\n"  # 这个换行别忘加了
                    body = {"text": text}
                    method, path = "POST", "/echo"
                elif command in ("delete-user", "put", "get", "delete"):  # 我应该增加的部分
                    print("This task is not implemented in the starting code yet.")
                    continue
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
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    print(f"Request failed: {exc}")
        except (EOFError, KeyboardInterrupt):
            print()
