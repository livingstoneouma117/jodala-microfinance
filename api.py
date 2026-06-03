from __future__ import annotations

from contextvars import ContextVar
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.datastructures import QueryParams


_request_state: ContextVar[SimpleNamespace | None] = ContextVar("request_state", default=None)
_g_state: ContextVar[SimpleNamespace] = ContextVar("g_state", default=SimpleNamespace())


class _RequestProxy:
    def _state(self) -> SimpleNamespace:
        state = _request_state.get()
        if state is None:
            raise RuntimeError("request is only available during an active request")
        return state

    def __getattr__(self, name: str) -> Any:
        return getattr(self._state(), name)


class _GProxy:
    def _state(self) -> SimpleNamespace:
        return _g_state.get()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._state(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._state(), name, value)

    def get(self, name: str, default: Any = None) -> Any:
        return getattr(self._state(), name, default)

    def pop(self, name: str, default: Any = None) -> Any:
        state = self._state()
        if hasattr(state, name):
            value = getattr(state, name)
            delattr(state, name)
            return value
        return default


request = _RequestProxy()
g = _GProxy()


def _response_payload(content: Any, status_code: int = 200) -> Response:
    if isinstance(content, tuple) and len(content) == 2 and isinstance(content[1], int):
        return _response_payload(content[0], content[1])
    if isinstance(content, Response):
        content.status_code = status_code if content.status_code == 200 else content.status_code
        return content
    if isinstance(content, (dict, list)):
        return JSONResponse(content, status_code=status_code)
    if isinstance(content, bytes):
        return Response(content, status_code=status_code)
    return Response(str(content or ""), status_code=status_code)


def jsonify(*args, **kwargs) -> JSONResponse:
    if args and kwargs:
        raise TypeError("jsonify() accepts either positional or keyword arguments, not both")
    if kwargs:
        content = kwargs
    elif len(args) == 1:
        content = args[0]
    elif len(args) == 0:
        content = None
    else:
        content = list(args)
    return JSONResponse(content)


def make_response(content: Any = "", status_code: int = 200) -> Response:
    return _response_payload(content, status_code)


def send_file(
    path_or_file: Any,
    mimetype: str | None = None,
    as_attachment: bool = False,
    download_name: str | None = None,
):
    if hasattr(path_or_file, "read"):
        file_obj = path_or_file
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        headers = {}
        if as_attachment and download_name:
            headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
        return StreamingResponse(file_obj, media_type=mimetype or "application/octet-stream", headers=headers)

    path = Path(path_or_file)
    filename = download_name or path.name
    return FileResponse(
        str(path),
        media_type=mimetype or None,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'} if as_attachment or download_name else None,
    )


def send_from_directory(directory: str, filename: str):
    return FileResponse(str(Path(directory) / filename))


class Blueprint:
    def __init__(self, name: str, import_name: str | None = None, url_prefix: str = ""):
        self.name = name
        self.import_name = import_name
        self.router = APIRouter(prefix=url_prefix)

    def route(self, path: str, methods: list[str] | tuple[str, ...] | None = None, **kwargs):
        methods = list(methods or ["GET"])

        def _convert_path(route_path: str) -> str:
            def repl(match: re.Match[str]) -> str:
                raw = match.group(1).strip()
                if ":" in raw:
                    route_type, name = raw.split(":", 1)
                else:
                    route_type, name = "str", raw
                route_type = route_type.strip()
                name = name.strip()
                if route_type == "path":
                    return f"{{{name}:path}}"
                if route_type == "int":
                    return f"{{{name}:int}}"
                if route_type == "float":
                    return f"{{{name}:float}}"
                return f"{{{name}}}"

            return re.sub(r"<([^>]+)>", repl, route_path)

        route_path = _convert_path(path)

        def decorator(func: Callable):
            async def endpoint(request: Request):
                body = None
                if request.method not in {"GET", "HEAD"}:
                    try:
                        body = await request.json()
                    except Exception:
                        body = None
                req_state = SimpleNamespace(
                    method=request.method,
                    path=request.url.path,
                    headers=request.headers,
                    args=request.query_params if isinstance(request.query_params, QueryParams) else QueryParams(str(request.url.query)),
                    json=body,
                    path_params=dict(request.path_params),
                    remote_addr=(request.client.host if request.client else None) or request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or "unknown",
                )
                req_token = _request_state.set(req_state)
                g_token = _g_state.set(SimpleNamespace())
                try:
                    result = func(**req_state.path_params)
                    if hasattr(result, "__await__"):
                        result = await result
                    return _response_payload(result)
                finally:
                    _request_state.reset(req_token)
                    _g_state.reset(g_token)

            endpoint.__name__ = func.__name__
            endpoint.__doc__ = func.__doc__
            self.router.add_api_route(route_path, endpoint, methods=methods, **kwargs)
            return func

        return decorator


__all__ = [
    "Blueprint",
    "Response",
    "Request",
    "g",
    "jsonify",
    "make_response",
    "request",
    "send_file",
    "send_from_directory",
]
