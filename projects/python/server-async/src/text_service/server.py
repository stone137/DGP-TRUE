import argparse  # 解析命令行参数
import asyncio  # 异步框架
import json  # json编码，解码
import logging  # 日志记录
from collections.abc import AsyncGenerator  # 异步上下文管理器装饰器
from contextlib import asynccontextmanager  # 异步生成器的类型注释
from time import perf_counter  # 高精度计时器

import uvicorn  # ASGI服务器(支持异步Web接口(ASGI协议)的Web服务器, 用于驱动异步Python Web框架)
from fastapi import FastAPI, Request  # Web框架类与请求对象
from fastapi.responses import JSONResponse, Response  # 返回JSON响应和通用响应
from starlette.middleware.base import RequestResponseEndpoint  # 中间键端点类型

from .service import ROUTES, Service, route_error  # 导入sercive.py里的东西

logger = logging.getLogger("uvicorn.error")  # 作用: 使日志风格统一
# .getlogger(): 按名字获取/创建日志器


@asynccontextmanager
# 让FastAPI知道: 启动时跑上半段, 关停时跑下半段 (yield后是下半段)
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # 定义异步函数lifespan, 参数app, 类型FastAPI, 返回异步生成器, 产出None
    logger.info("Press Ctrl+C to exit. All in-memory data is lost on exit.")
    # 用logger输出INFO级日志
    logger.info("Routes:")
    # 输出路由标题
    for method, path in ROUTES:  # 遍历ROUTES, 解包方法和路径
        logger.info("  %s %s", method, path)
    yield  # 暂停, 交出控制权


def create_app(token_ttl_seconds: int = 300) -> FastAPI:
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None, lifespan=lifespan)
    # FastAPI: 创建一个Web应用对象, 注册路由, 中间件和生命周期钩子, 作为ASGI应用被uvicorn驱动运行
    service = Service(token_ttl_seconds=token_ttl_seconds)  # service是Service的一个实例

    @app.middleware("http")  # 给FastAPI应用注册一个中间件, 用来拦截/处理每个HTTP请求
    # @: 装饰器标记, app: FastAPI应用实例, .middleware(): 注册HTTP中间件的方法, "http": 类型参数,
    async def log_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
        # RequestReponseEndpoint: 调用下一个中间件/路由的回调
        started = perf_counter()  # started为当前的时间（秒）
        status = 500
        try:
            if error := route_error(request.method, request.url.path):
                # route_error(request.method, request.url.path) 返回的是错误码
                response = JSONResponse(
                    {"message": "Not found" if error == 404 else "Method not allowed"},
                    status_code=error,
                )
            else:
                response = await call_next(request)
                # 把请求交给下一个中间件或路由处理，并await等待返回响应对象
            status = response.status_code  # 把status_code弄出来用于日志
            return response
        finally:
            logger.info(
                "%s %s -> %d %.1fms",
                request.method,
                json.dumps(request.url.path, ensure_ascii=False),
                # 把路径字符串转化为JSON字符串，且保留非ASCII字符
                status,
                (perf_counter() - started) * 1000,
            )

    @app.api_route(  # app.api_route: 注册支持多种HTTP方法的路由
        "/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
        # "/{path:path}": 路径模板，捕获全部子路径（含/）
    )  # 把所有路径，所有常见HTTP方法都路由到同一个处理函数
    async def dispatch(request: Request) -> JSONResponse:
        body = None
        if request.method in ("POST", "PUT"):
            raw = bytearray()  # 可变字节数组
            async for chunk in request.stream():  # 异步迭代请求数据流
                raw.extend(chunk)  # 把当前块追加到缓冲区
                if len(raw) > 512 * 1024:  # 超过512KB
                    return JSONResponse({"message": "Request body too large"}, status_code=413)
            try:
                body = json.loads(  # 解析字符串为Python对象
                    raw.decode("utf-8"),  # 字节转UTF-8字符串
                    parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
                    # 解析常量时的回调
                    # 用空生成器立即抛出ValueError结束json,loads函数
                )
            except (ValueError, UnicodeError):
                return JSONResponse({"message": "Expected UTF-8 JSON"}, status_code=400)
        # Password hashing is blocking: keep it off the event loop.
        # 翻译：密码哈希是阻塞操作，请放在事件循环之外执行
        status, result = await asyncio.to_thread(  # 把阻塞调用丢到线程池异步执行
            service.handle,  # 目标函数
            request.method,  # HTTP方法
            request.url.path,  # 路径
            body,  # 解析后的JSON体
            request.headers.get("Authorization", ""),
        )
        return JSONResponse(result, status_code=status)

    return app


def main() -> None:
    parser = argparse.ArgumentParser()  # 创建命令行参数解析器
    parser.add_argument("--host", default="127.0.0.1")  # 添加--host参数，默认本地回环
    parser.add_argument("--port", type=int, default=7878)  # 添加--post参数（整型），默认7878
    parser.add_argument("--token-ttl-seconds", type=int, default=300)
    args = parser.parse_args()  # 解析命令行得到参数对象
    if not 1 <= args.port <= 65535:  # 如果端口超出合法范围
        parser.error("port must be 1..65535")
    uvicorn.run(
        create_app(token_ttl_seconds=args.token_ttl_seconds),
        host=args.host,
        port=args.port,
        workers=1,
        access_log=False,
    )
    # 运行creat_app()返回的ASGI应用，绑定主机，绑定端口，单进程关闭uvicorn内置访问日志
