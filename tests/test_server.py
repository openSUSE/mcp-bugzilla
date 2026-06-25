import base64
import os
from unittest.mock import AsyncMock

import pytest

from mcp_bugzilla import server


def _fake_bz(attachment):
    """A stand-in Bugzilla client exposing only get_attachment/list_attachments.

    The @mcp.tool decorator returns the function unchanged and Depends(get_bz) is
    NOT resolved on a direct call, so tests must pass bz= explicitly.
    """
    bz = AsyncMock()
    bz.get_attachment = AsyncMock(return_value=attachment)
    return bz


@pytest.mark.asyncio
async def test_download_attachment_text_inline(tmp_path):
    server.download_dir = str(tmp_path)
    att = {
        "id": 42,
        "file_name": "log.txt",
        "content_type": "text/plain",
        "size": 5,
        "is_private": False,
        "is_obsolete": False,
        "data": base64.b64encode(b"hello").decode(),
    }

    result = await server.download_attachment(attachment_id=42, bz=_fake_bz(att))

    assert result["mode"] == "text"
    assert result["content"] == "hello"
    assert result["file_name"] == "log.txt"
    # Inline delivery must not touch the disk.
    assert os.listdir(tmp_path) == []


@pytest.mark.asyncio
async def test_download_attachment_binary_saved(tmp_path):
    server.download_dir = str(tmp_path)
    blob = b"\x89PNG\r\n\x1a\n\x00\x01\x02\x03"
    att = {
        "id": 7,
        "file_name": "image.png",
        "content_type": "application/octet-stream",
        "size": len(blob),
        "is_private": False,
        "is_obsolete": False,
        "data": base64.b64encode(blob).decode(),
    }

    result = await server.download_attachment(attachment_id=7, bz=_fake_bz(att))

    assert result["mode"] == "saved"
    assert result["size"] == len(blob)
    saved = result["path"]
    assert os.path.isfile(saved)
    with open(saved, "rb") as f:
        assert f.read() == blob


@pytest.mark.asyncio
async def test_download_attachment_oversized_text_saved(tmp_path):
    server.download_dir = str(tmp_path)
    big = b"a" * (server.MAX_INLINE_BYTES + 1)
    att = {
        "id": 8,
        "file_name": "huge.log",
        "content_type": "text/plain",
        "data": base64.b64encode(big).decode(),
    }

    result = await server.download_attachment(attachment_id=8, bz=_fake_bz(att))

    assert result["mode"] == "saved"
    assert os.path.isfile(result["path"])


@pytest.mark.asyncio
async def test_download_attachment_filename_traversal_neutralized(tmp_path):
    server.download_dir = str(tmp_path)
    att = {
        "id": 9,
        "file_name": "../../../etc/evil.bin",
        "content_type": "application/octet-stream",
        "data": base64.b64encode(b"x").decode(),
    }

    result = await server.download_attachment(attachment_id=9, bz=_fake_bz(att))

    saved = os.path.realpath(result["path"])
    # The sanitized file must stay inside the target directory.
    assert saved.startswith(os.path.realpath(str(tmp_path)) + os.sep)
    assert ".." not in os.path.basename(saved)


@pytest.mark.asyncio
async def test_download_attachment_explicit_output_dir(tmp_path):
    server.download_dir = "/nonexistent-default-should-not-be-used"
    out = tmp_path / "custom"
    blob = b"\x00\x01"
    att = {
        "id": 10,
        "file_name": "data.bin",
        "content_type": "application/octet-stream",
        "data": base64.b64encode(blob).decode(),
    }

    result = await server.download_attachment(
        attachment_id=10, output_dir=str(out), bz=_fake_bz(att)
    )

    assert os.path.dirname(result["path"]) == str(out)
    assert os.path.isfile(result["path"])


@pytest.mark.asyncio
async def test_list_attachments_tool_passthrough():
    bz = AsyncMock()
    bz.list_attachments = AsyncMock(
        return_value=[{"id": 1, "file_name": "a.txt"}, {"id": 2, "file_name": "b.txt"}]
    )

    result = await server.list_attachments(bug_id=123, bz=bz)

    assert [a["id"] for a in result] == [1, 2]
    bz.list_attachments.assert_awaited_once_with(123)
