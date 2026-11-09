"""Client for the IETF "Resumable Uploads for HTTP" protocol.

This is a small, dependency-free (uses ``requests``, already a dependency)
implementation of draft-ietf-httpbis-resumable-upload-11 (interop version 8)

The single public entry point :func:`resumable_upload` uploads a local file to a
server endpoint that speaks the same protocol. The upload resource is identified
by the request URL itself: an interrupted upload can be resumed by simply
re-invoking :func:`resumable_upload` with the same arguments - the client asks
the server (via ``HEAD``) how many bytes it already has and continues from there.
"""

import base64
import hashlib
import logging
from pathlib import Path
from typing import Callable, Mapping, Optional, Tuple, Union

import requests
from requests.auth import AuthBase
from requests.cookies import RequestsCookieJar

logger = logging.getLogger(__name__)

#: The draft interop version this client implements.
INTEROP_VERSION = "8"
INTEROP_HEADER = "Upload-Draft-Interop-Version"
#: Content type used for the body of append (``PATCH``) requests.
PARTIAL_UPLOAD_CONTENT_TYPE = "application/partial-upload"
DIGEST_ALGORITHM = "sha-256"
_HASHLIB_NAME = "sha256"
#: Default size of a single ``PATCH`` chunk (kept below the 10 MB request cap
#: enforced on the ITER network, see ``RemoteAPI.push_simulation``).
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024

#: Maximum number of consecutive failures (connection errors / offset
#: conflicts) tolerated before giving up.
_MAX_RETRIES = 5


class ResumableUploadError(RuntimeError):
    """Raised when a resumable upload cannot be completed."""


def _bool_field(value: bool) -> str:
    """Render a boolean as an HTTP structured-field item (``?1``/``?0``)."""
    return "?1" if value else "?0"


def _parse_bool_field(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    value = value.strip()
    if value == "?1":
        return True
    if value == "?0":
        return False
    return None


def _format_digest(digest: bytes) -> str:
    """Render a raw digest as an RFC 9530 structured-field dictionary value.

    The single member uses :data:`DIGEST_ALGORITHM` as its key and the digest as
    a base64-encoded byte sequence, e.g. ``sha-256=:47DEQpj8HBSa...:``.
    """
    encoded = base64.b64encode(digest).decode("ascii")
    return f"{DIGEST_ALGORITHM}=:{encoded}:"


def _content_digest(data: bytes) -> str:
    """``Content-Digest`` value for the bytes of a single request body."""
    return _format_digest(hashlib.new(_HASHLIB_NAME, data).digest())


def _header_int(resp: "requests.Response", name: str) -> Optional[int]:
    raw = resp.headers.get(name)
    if raw is None:
        return None
    try:
        return int(raw.strip())
    except ValueError:
        return None


def _base_headers(extra: Optional[Mapping[str, str]]) -> dict:
    headers = {INTEROP_HEADER: INTEROP_VERSION}
    if extra:
        headers.update(extra)
    return headers


def _parse_upload_limit(value: Optional[str]) -> dict:
    """Parse an ``Upload-Limit`` structured-field dictionary into a dict.

    Only the integer-valued members this client cares about are kept (e.g.
    ``max-append-size``). Unparseable members are ignored.
    """
    limits: dict = {}
    if not value:
        return limits
    for member in value.split(","):
        member = member.strip()
        if "=" not in member:
            continue
        key, _, raw = member.partition("=")
        try:
            limits[key.strip()] = int(raw.strip())
        except ValueError:
            continue
    return limits


def _clamp_chunk_size(chunk_size: int, limits: dict) -> int:
    """Reduce ``chunk_size`` to the server-advertised ``max-append-size``."""
    max_append = limits.get("max-append-size")
    if max_append and max_append > 0:
        return min(chunk_size, max_append)
    return chunk_size


def resumable_upload(
    url: str,
    path: Union[str, Path],
    *,
    auth: Optional[Union[AuthBase, Tuple[str, str]]] = None,
    cookies: Optional[Union[Mapping[str, str], RequestsCookieJar]] = None,
    headers: Optional[Mapping[str, str]] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    progress: Optional[Callable[[int], None]] = None,
) -> None:
    """Upload ``path`` to ``url`` using the resumable upload protocol.

    :param url: the upload resource URL. The server is expected to treat this
        URL itself as the upload resource (it is both the creation target and
        the resource that is appended to / queried).
    :param path: the local file to upload.
    :param auth: authentication passed through to ``requests``.
    :param cookies: cookies passed through to ``requests`` (e.g. firewall).
    :param headers: extra headers to send with every request.
    :param chunk_size: number of bytes sent per ``PATCH`` request.
    :param progress: optional callback invoked with the absolute number of bytes
        confirmed by the server, after resuming and after each chunk. Useful for
        driving a progress bar.
    """
    path = Path(path)
    total = path.stat().st_size

    offset, complete, limits = _resume_or_create(url, total, auth, cookies, headers)
    if complete:
        if progress:
            progress(total)
        return

    # Reflect any bytes the server already holds (resumed upload).
    if progress:
        progress(offset)

    # The server advertises its append-size limit via Upload-Limit; never send a
    # chunk larger than it will accept.
    chunk_size = _clamp_chunk_size(chunk_size, limits)

    with path.open("rb") as f:
        _send_chunks(
            url,
            f,
            offset,
            total,
            chunk_size,
            auth,
            cookies,
            headers,
            progress,
        )


def _resume_or_create(
    url: str,
    total: int,
    auth,
    cookies,
    headers,
) -> Tuple[int, bool, dict]:
    """Return ``(offset, complete, limits)`` for the upload resource at ``url``.

    Probes the resource with ``HEAD``; if it does not yet exist the resource is
    created with an empty body (``Upload-Complete: ?0``). ``limits`` is the
    parsed ``Upload-Limit`` dictionary advertised by the server.
    """
    resp = requests.head(
        url, headers=_base_headers(headers), auth=auth, cookies=cookies
    )
    if resp.status_code in (200, 204):
        limits = _parse_upload_limit(resp.headers.get("Upload-Limit"))
        if _parse_bool_field(resp.headers.get("Upload-Complete")):
            return total, True, limits
        return _header_int(resp, "Upload-Offset") or 0, False, limits

    create_headers = _base_headers(headers)
    create_headers["Upload-Complete"] = _bool_field(False)
    create_headers["Upload-Length"] = str(total)
    resp = requests.post(
        url, data=b"", headers=create_headers, auth=auth, cookies=cookies
    )
    if resp.status_code not in (200, 201, 204):
        raise ResumableUploadError(
            f"Failed to create upload resource ({resp.status_code}): {resp.text}"
        )
    limits = _parse_upload_limit(resp.headers.get("Upload-Limit"))
    return _header_int(resp, "Upload-Offset") or 0, False, limits


def _send_chunks(
    url: str,
    f,
    offset: int,
    total: int,
    chunk_size: int,
    auth,
    cookies,
    headers,
    progress: Optional[Callable[[int], None]] = None,
) -> None:
    attempts = 0
    while True:
        f.seek(offset)
        chunk = f.read(chunk_size)
        complete = (offset + len(chunk)) >= total

        patch_headers = _base_headers(headers)
        patch_headers["Content-Type"] = PARTIAL_UPLOAD_CONTENT_TYPE
        patch_headers["Upload-Offset"] = str(offset)
        patch_headers["Upload-Complete"] = _bool_field(complete)
        patch_headers["Content-Digest"] = _content_digest(chunk)

        try:
            resp = requests.patch(
                url, data=chunk, headers=patch_headers, auth=auth, cookies=cookies
            )
        except (requests.ConnectionError, requests.Timeout) as err:
            attempts += 1
            if attempts > _MAX_RETRIES:
                raise ResumableUploadError(
                    f"Upload failed after {_MAX_RETRIES} retries: {err}"
                ) from err
            logger.warning("Upload chunk failed (%s), resuming from server offset", err)
            server_offset = _query_offset(url, auth, cookies, headers)
            if server_offset is not None:
                offset = server_offset
            continue

        if resp.status_code == 409:
            # Offset mismatch: resynchronise to the server-reported offset.
            server_offset = _header_int(resp, "Upload-Offset")
            if server_offset is None:
                raise ResumableUploadError(
                    "Server reported an offset conflict without an Upload-Offset header"
                )
            attempts += 1
            if attempts > _MAX_RETRIES:
                raise ResumableUploadError("Too many offset conflicts during upload")
            offset = server_offset
            continue

        if resp.status_code not in (200, 201, 204):
            raise ResumableUploadError(
                f"Unexpected status {resp.status_code} while appending: {resp.text}"
            )

        attempts = 0
        server_offset = _header_int(resp, "Upload-Offset")
        offset = server_offset if server_offset is not None else offset + len(chunk)

        if progress:
            progress(offset)

        if complete:
            return


def _query_offset(url: str, auth, cookies, headers) -> Optional[int]:
    """Return the server's current offset, or ``None`` if it can't be determined.

    A ``None`` result (failed/ambiguous HEAD, or a missing ``Upload-Offset``
    header) means "unknown" - the caller must keep its current offset rather than
    restart the upload.
    """
    try:
        resp = requests.head(
            url, headers=_base_headers(headers), auth=auth, cookies=cookies
        )
    except (requests.ConnectionError, requests.Timeout):
        return None
    if resp.status_code in (200, 204):
        return _header_int(resp, "Upload-Offset")
    return None
