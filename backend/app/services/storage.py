"""Temporary PDF storage in Supabase Storage (private bucket `pending-uploads`).

Created by supabase/submissions_setup.sql. The bucket is private, so files can only be
reached through this backend (service role key), never by a public URL.
"""
import logging

from .. import supabase_client
from ..exceptions import NotFound, ServiceUnavailable

log = logging.getLogger("studysync.storage")

BUCKET = "pending-uploads"


def _bucket():
    return supabase_client.admin().storage.from_(BUCKET)


def upload_pdf(path: str, content: bytes) -> None:
    try:
        _bucket().upload(path, content, {"content-type": "application/pdf", "upsert": "false"})
    except ServiceUnavailable:
        raise
    except Exception:
        # most common cause: the bucket does not exist yet (run supabase/submissions_setup.sql)
        log.exception("Could not upload %s to the '%s' bucket", path, BUCKET)
        raise ServiceUnavailable("File storage is not available right now. Please try again later.")



def delete_file(path: str) -> bool:
    """Delete a temporary PDF from Supabase Storage.

    Returns True when the Storage API accepts the deletion.
    Returns False and logs the error if deletion fails.
    """
    if not path or not path.strip():
        log.error("Cannot delete Supabase Storage file: empty path")
        return False

    try:
        result = _bucket().remove([path])

        # Supabase Storage raises an exception on API errors.
        # Do not clear the database path if the request fails.
        log.info(
            "Supabase Storage deletion accepted for bucket=%s path=%s result=%r",
            BUCKET,
            path,
            result,
        )
        return True

    except Exception:
        log.exception(
            "Failed to delete Supabase Storage file: bucket=%s path=%s",
            BUCKET,
            path,
        )
        return False



def download_pdf(path: str) -> bytes:
    """The temporary PDF, for the admin preview and for copying it to Google Drive."""
    try:
        return _bucket().download(path)
    except ServiceUnavailable:
        raise
    except Exception as exc:
        log.exception("Could not download %s from the '%s' bucket", path, BUCKET)
        if "not found" in str(exc).lower() or "404" in str(exc):
            raise NotFound("The uploaded file could not be found in temporary storage.")
        raise ServiceUnavailable("File storage is not available right now. Please try again later.")
