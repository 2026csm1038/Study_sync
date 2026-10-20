"""Temporary PDF storage in Supabase Storage (private bucket `pending-uploads`).

Created by supabase/submissions_setup.sql. The bucket is private, so files can only be
reached through this backend (service role key), never by a public URL.
"""
import logging

from .. import supabase_client
from ..exceptions import ServiceUnavailable

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


def delete_file(path: str) -> None:
    """Best effort. Used to undo an upload when saving its row fails, so it never raises."""
    try:
        _bucket().remove([path])
    except Exception:
        log.exception("Could not remove %s from the '%s' bucket", path, BUCKET)
