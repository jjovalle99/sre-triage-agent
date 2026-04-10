from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, Request


@dataclass(frozen=True)
class AppDeps:
    http_client: httpx.AsyncClient


async def get_app_deps(request: Request) -> AppDeps:
    return request.app.state.deps  # type: ignore[no-any-return]


AppDepsDep = Annotated[AppDeps, Depends(get_app_deps)]
