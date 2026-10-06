"""In-memory baseline. Implement the task routes in handle()."""
# 一个最小可运行版本，数据只存储在内存里，请在handle()中补全各路由的处理逻辑

import hashlib  # 哈希算法
import hmac  # 基于哈希的消息认证码
import re  # 正则表达式（从字符串里按规则查找/替换内容）
import secrets  # 生成随机安全token, salt
import threading  # 线程同步与锁（让程序并发执行任务，并提供锁避免竞态）
from dataclasses import dataclass, field

# 用装饰器自动生成类的__init__, __repr__等样板方法（示例的两个，分别用于初始化实例和定义打印输出格式）
from typing import Any  # 类型提示工具

ROUTES = (
    ("GET", "/ping"),
    ("POST", "/users"),
    ("POST", "/sessions"),
    ("DELETE", "/sessions/current"),
    ("GET", "/texts"),
    ("POST", "/echo"),
)


def route_error(method: str, path: str) -> int | None:  # 类型是int或None
    if path.startswith("/texts/") and len(path) > len("/texts/"):
        return None if method in ("PUT", "GET") else 405
    allowed = next((verb for verb, route in ROUTES if route == path), None)
    # next(): 取迭代器下一个元素，无则返回默认值
    # verb: 方法动词
    # verb / for verb, route in ROUTES / if route == path: 如果route为path, 返回route所在元组的verb
    if allowed is None:
        return 404
    return None if method == allowed else 405
    # 405: 已知路径使用不支持的方法


@dataclass
# 标记下面的类是数据类，自动生成初始化和打印等方法，省去手写样板代码
# 类是对象的模板，定义了一类事物的属性和行为; 对象是按类造出来的实例，拥有具体数据和行为
# 类是一张设计图, 对象是按图造出来的实物
class User:  # 自己创建一个类(数据类型)
    salt: bytes  # bytes: 不可变的二进制字节序列
    digest: bytes
    token: str | None = None  # token默认值是None(如果未传参就使用默认值)
    texts: dict[str, str] = field(default_factory=dict)
    # text是个键和值都时字符串的字典, 默认值是一个空字典
    # 字段: 类中声明的变量, 对应实例的一个属性
    # field是dataclass给字段的消息, 告诉它默认值要怎么来, 要怎么用
    # default_factory=dict: 指定dict(可调用对象: 可用()调动的东西, 如函数, 类, dict等)每次创建时调用生成独立默认值, 避免可变默认值共享
    # 这样就让texts在每次实例化时调用dict()生成新的空字典


class Service:
    def __init__(self) -> None:
        # 自定义初始化逻辑, @dataclass中生成的默认配置无法满足(self开始出现的地方!!!)
        self.users: dict[str, User] = {}
        # 保存用户信息的字典, 初始为空
        self.lock = threading.Lock()
        # 线程锁, 保护users的并发访问

    def handle(
        self,
        method: str,
        path: str,
        body: Any,
        authorization: str,
        # self是实例自身, 调用方法时python自动传入, 允许访问该实例的属性和其他方法
    ) -> tuple[int, dict[str, Any]]:
        if status := route_error(method, path):  # ":=": 海象运算符, 同时赋值并使用
            # 调用route_error函数, 把值赋予给status, 再判断status是否为真
            return status, {"message": "Not found" if status == 404 else "Method not allowed"}
        if method == "GET" and path == "/ping":
            return 200, {"data": "pong"}
        if path in ("/users", "/sessions") and method == "POST":
            if not isinstance(body, dict) or set(body) != {"username", "password"}:
                # isinstance(obj, type): 检查obj是否为指定类型实例, 是则返回True
                # set(body): 把body的键转为集合
                return 400, {"message": "Expected username and password"}
            name, password = body["username"], body["password"]
            if (
                not isinstance(name, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name)
                # re.fullmatch(pattern, string): 判断字符串是否满足pattern
                # r"...": 原始字符串, 转义字符不再有效
                # [A-Za-z0-9_-]: 表示任一大小写字母, 数字, 下划线, 连字符
                # {1,32}: 长度为1~32
                or not isinstance(password, str)
                or not 8 <= len(password) <= 128
            ):
                return 400, {"message": "Invalid username or password length"}
            try:
                password.encode("utf-8")
                # .encode(): 字符串编码方法, 转为bytes
                # "utf-8": 编码格式参数
            except UnicodeError:
                return 400, {"message": "Password must be valid Unicode"}
            # Hashing is outside the state lock; commit/check against current state under lock.
            # 翻译: 哈希计算在锁外执行, 提交说检查状态时再进入锁内
            if path == "/users":
                salt = secrets.token_bytes(16)  # 生成16字节密码学安全的随机字节序列
                # 盐值: 哈希前与密码拼接的随机数据, 使相同密码产生不同摘要(哈希算法生成的结果)
                digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
                # digest中存的是哈希结果
                # hashlib.pbkdf2_hmac(): 调用pbkdf2 HMAC算法
                # "sha256": 哈希算法名
                # 100_000: 迭代次数 (pbkdf2内部哈希的次数) (下划线仅为可读性, 无实际含义)
                with self.lock:  # 打开单人间，进去独占，出来开门
                    if name in self.users:
                        return 409, {"message": "Username exists"}
                    self.users[name] = User(salt, digest)  # 创建一个新的User实例
                return 201, {"data": {"username": name}}
            with self.lock:
                user = self.users.get(name)
                # user是self.users字典中键name的值---这一步把User实例取出
                if user is None:
                    return 401, {"message": "Invalid username or password"}
                salt, expected = user.salt, user.digest  # 调用User实例/user
            digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
            with self.lock:
                if self.users.get(name) is not user or not hmac.compare_digest(digest, expected):
                    # 比较名字和密码
                    # hmac.compare_digest: 用恒定时间比较两个bytes
                    return 401, {"message": "Invalid username or password"}
                user.token = secrets.token_urlsafe(32)
                # 生成32字节的URL安全随机字符串, 赋值给user.token
                # Later server task: record a deadline and return expires_in.
                # 翻译: 后续服务端任务: 记录过期时间并返回expires_in
                return 200, {"data": {"token": user.token}}
        if method == "POST" and path == "/echo":
            if set(body) != {"text"}:  # 检查多余或缺失
                return 400, {"message": "expect only the text"}
            text = body["text"]
            if not isinstance(text, str):
                return 400, {"message": "the text must be a string"}
            if len(text.encode("utf-8")) > 65536:
                return 413, {"message": "the text is too long"}
            return 200, {"data": text}
        protected = (
            path == "/texts"
            or path == "/sessions/current"
            or path.startswith("/texts/")
            and len(path) > len("/texts/")
        )
        if protected:
            token = (
                authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
            )  # removeprefix("Bearer "): 去掉前缀Bearer
            # 如果前缀是"Bearer ", 去掉之后赋值给token, 否则token为空 (其实就是获取token的一步)
            with self.lock:
                user = next((u for u in self.users.values() if token and u.token == token), None)
                # 如果有token, 查找self.users.values()里面有没有刚刚的token, 如果有的话就把user赋值为token, 否则为None
                if user is None:
                    return 401, {"message": "Login required"}
                # Later server task: check token expiry here, before reading or modifying state.
                # 翻译: 后续服务端任务: 在读写或修改状态前, 先检查token是否过期
                if path == "/sessions/current" and method == "DELETE":
                    user.token = None
                    return 200, {"data": None}
                if path == "/texts" and method == "GET":
                    return 200, {"data": sorted(user.texts)}
                if path.startswith("/texts/") and len(path) > len("/texts/"):
                    name = path[len("/texts/") :]
                    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
                        return 400, {"message": "Invalid text name!"}
                    if method == "PUT":
                        if set(body) != {"text"}:
                            return 400, {"message": "expect only the text"}
                        text = body["text"]
                        if not isinstance(text, str):
                            return 400, {"message": "the text must be a string"}
                        if len(text.encode("utf-8")) > 65536:
                            return 413, {"message": "the text is too long"}
                        user.texts[name] = text
                        return 200, {"data": None}
                    if method == "GET":
                        if name not in user.texts:
                            return 404, {"Message": "text not found"}
                        return 200, {"data": user.texts[name]}
        return 404, {"message": "Not found"}


"""
几个最抽象的点:

User: 类
user: 类的一个实例
users: 存放多个User实例的字典

self: 是python给实例方法留的形参名, 指向调用方法的那个对象, 不是关键字也不是数据类型
"""
