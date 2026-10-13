"""Map case domain errors to HTTP responses (shared by cases and documents routes)."""

from fastapi import HTTPException


def case_error_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    code = str(exc)
    if code == "unknown_case":
        return HTTPException(status_code=400, detail="Unknown case_id")
    if code == "case_deleting":
        return HTTPException(status_code=409, detail="Case is being deleted")
    if code == "delete_mode_conflict":
        return HTTPException(
            status_code=409,
            detail="Case is already being deleted with a different cascade setting",
        )
    if code == "document_not_found":
        return HTTPException(status_code=404, detail="Document not found")
    return HTTPException(status_code=400, detail=code)
