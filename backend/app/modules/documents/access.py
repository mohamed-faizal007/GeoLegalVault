"""The one place that decides whether a user may see a document (SEC-02, D-051).

Every route that takes a document or version id resolves it through here, so the check cannot
be forgotten per endpoint (a test enumerates the routes). It runs after JWT, RBAC and the
geofence dependencies and before the action and its audit row (Guardrail #5).

A document above the caller's clearance is reported exactly like one that does not exist (404,
same body), so its existence is not revealed. The refused attempt on a document that *does*
exist is audited (`ACCESS_DENIED`); an id that does not exist leaves no row, so the log cannot
be flooded with made-up ids and the caller cannot tell the two apart.
"""

from typing import Any

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.clearance import LEVELS, can_see, rank_of, user_rank
from app.core.errors import AppError
from app.modules.audit import service as audit
from app.modules.documents import service as documents_service
from app.modules.versions import service as versions_service


class InvalidClassification(AppError):
    status_code = 422

    def __init__(self) -> None:
        super().__init__(
            "INVALID_CLASSIFICATION", f"classification must be one of: {', '.join(LEVELS)}"
        )


class ClassificationNotAllowed(AppError):
    status_code = 403

    def __init__(self) -> None:
        super().__init__(
            "CLASSIFICATION_NOT_ALLOWED",
            "your clearance does not allow a document at this classification",
        )


class ClassificationImmutable(AppError):
    status_code = 422

    def __init__(self) -> None:
        super().__init__(
            "CLASSIFICATION_IMMUTABLE",
            "the classification of an existing document cannot be changed",
        )


def validate_classification(value: str) -> str:
    """Exact level names only: no free text, no case folding, no trimming."""
    if rank_of(value) is None:
        raise InvalidClassification()
    return value


def require_clearance_for_upload(user: dict[str, Any], classification: str) -> None:
    """Nobody creates a document they could not then read."""
    if not can_see(user, classification):
        raise ClassificationNotAllowed()


def can_view(user: dict[str, Any], document: dict[str, Any]) -> bool:
    return can_see(user, document.get("classification"))


def user_clearance_rank(user: dict[str, Any]) -> int:
    return user_rank(user)


async def audit_denied(
    user: dict[str, Any], document: dict[str, Any], *, endpoint: str, **meta: Any
) -> None:
    await audit.record(
        actor_id=user["_id"],
        action="ACCESS_DENIED",
        target_type="document",
        target_id=document["_id"],
        result="DENIED",
        meta={"endpoint": endpoint, **meta},
    )


def document_not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")


async def load_visible_document(
    db: AsyncIOMotorDatabase, user: dict[str, Any], document_id: str, *, endpoint: str
) -> dict[str, Any]:
    """The document, or the same 404 whether it is missing or above the caller's clearance."""
    document = await documents_service.get_document_by_id(db, document_id)
    if document is None:
        raise document_not_found()
    if not can_view(user, document):
        await audit_denied(user, document, endpoint=endpoint)
        raise document_not_found()
    return document


async def resolve_visible_version(
    db: AsyncIOMotorDatabase, user: dict[str, Any], version_id: str, *, endpoint: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """(version, document) if the caller may see it; None if it is missing *or* hidden.

    The caller turns None into its own 404, identical for both cases."""
    version = await versions_service.get_version_by_id(db, version_id)
    if version is None:
        return None
    document = await documents_service.get_document_by_id(db, str(version["document_id"]))
    if document is None:
        return None
    if not can_view(user, document):
        await audit_denied(user, document, endpoint=endpoint, version_id=version_id)
        return None
    return version, document
