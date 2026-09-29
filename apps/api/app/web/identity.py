from fastapi import APIRouter

from app.modules.identity.queries import load_user
from app.web.deps import Authenticated
from app.web.schemas import AUTHENTICATED_ERRORS, User

router = APIRouter()


@router.get("/me", operation_id="identity_me", response_model=User, responses=AUTHENTICATED_ERRORS)
def identity_me(context: Authenticated) -> User:
    session, actor = context
    view = load_user(session, actor)
    return User(id=view.id, display_name=view.display_name, roles=list(view.roles))
