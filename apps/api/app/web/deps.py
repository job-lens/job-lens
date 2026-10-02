from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session

from app.core.errors import unauthenticated
from app.core.types import Actor
from app.infrastructure.db import Database, utcnow
from app.modules.identity.queries import resolve_actor
from app.modules.identity.service import touch_session

# Name and scheme id must match contracts/openapi.yaml; the contract is the source of truth.
SESSION_COOKIE = APIKeyCookie(name="__Host-jl_session", scheme_name="WebSession", auto_error=False)


def authenticated(
    request: Request, token: Annotated[str | None, Security(SESSION_COOKIE)]
) -> Iterator[tuple[Session, Actor]]:
    """Open one transaction per request and resolve the caller inside it."""
    # A missing cookie costs no connection: reject before reaching the pool.
    if not token:
        raise unauthenticated()
    database: Database = request.app.state.database
    with database.transaction() as session:
        now = utcnow()
        actor = resolve_actor(session, token, now)
        touch_session(session, token, now)
        yield session, actor


Authenticated = Annotated[tuple[Session, Actor], Depends(authenticated)]


def transaction(request: Request) -> Iterator[Session]:
    database: Database = request.app.state.database
    with database.transaction() as session:
        yield session


Transaction = Annotated[Session, Depends(transaction)]
