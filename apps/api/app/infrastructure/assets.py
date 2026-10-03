from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found
from app.infrastructure.models import FileAsset, FileLink


def require_files(
    s: Session, ids: list[UUID], case_id: UUID, purpose: str, task_id: UUID | None = None
) -> list[FileAsset]:
    if len(set(ids)) != len(ids):
        raise conflict("DUPLICATE_FILE")
    rows = list(s.scalars(select(FileAsset).where(FileAsset.id.in_(ids)).with_for_update()))
    if len(rows) != len(ids) or any(
        row.case_id != case_id
        or row.purpose != purpose
        or (task_id is not None and row.task_id != task_id)
        for row in rows
    ):
        raise not_found()
    if any(row.state != "ready" for row in rows):
        raise conflict("FILE_NOT_READY")
    return rows


def link_files(s: Session, ids: list[UUID], case_id: UUID, kind: str, owner_id: UUID) -> None:
    for asset_id in ids:
        if (
            s.scalar(
                select(FileLink.id).where(
                    FileLink.asset_id == asset_id,
                    FileLink.owner_kind == kind,
                    FileLink.owner_id == owner_id,
                )
            )
            is None
        ):
            s.add(FileLink(asset_id=asset_id, case_id=case_id, owner_kind=kind, owner_id=owner_id))
