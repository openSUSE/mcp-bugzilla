import base64
import os
from unittest.mock import AsyncMock

import pytest
from fastmcp.exceptions import ToolError

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
async def test_download_attachment_delivery_save_forces_disk(tmp_path):
    server.download_dir = str(tmp_path)
    att = {
        "id": 11,
        "file_name": "note.txt",
        "content_type": "text/plain",  # would be inline under "auto"
        "data": base64.b64encode(b"hi").decode(),
    }

    result = await server.download_attachment(
        attachment_id=11, delivery="save", bz=_fake_bz(att)
    )

    assert result["mode"] == "saved"
    assert os.path.isfile(result["path"])


@pytest.mark.asyncio
async def test_download_attachment_delivery_inline_binary_base64(tmp_path):
    server.download_dir = str(tmp_path)
    blob = b"\x00\x01\x02\x03"
    b64 = base64.b64encode(blob).decode()
    att = {
        "id": 12,
        "file_name": "blob.bin",
        "content_type": "application/octet-stream",  # would be saved under "auto"
        "data": b64,
    }

    result = await server.download_attachment(
        attachment_id=12, delivery="inline", bz=_fake_bz(att)
    )

    assert result["mode"] == "base64"
    assert result["data_base64"] == b64
    assert base64.b64decode(result["data_base64"]) == blob
    assert os.listdir(tmp_path) == []  # nothing written


@pytest.mark.asyncio
async def test_download_attachment_delivery_inline_too_large_raises(tmp_path):
    server.download_dir = str(tmp_path)
    big = b"x" * (server.MAX_FORCED_INLINE_BYTES + 1)
    att = {
        "id": 13,
        "file_name": "huge.bin",
        "content_type": "application/octet-stream",
        "data": base64.b64encode(big).decode(),
    }

    with pytest.raises(ToolError, match="too large to return inline"):
        await server.download_attachment(
            attachment_id=13, delivery="inline", bz=_fake_bz(att)
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [None, ""])
async def test_download_attachment_missing_data_raises(tmp_path, data):
    server.download_dir = str(tmp_path)
    att = {
        "id": 99,
        "file_name": "secret.txt",
        "content_type": "text/plain",
        "data": data,
    }

    with pytest.raises(ToolError, match="no downloadable data"):
        await server.download_attachment(attachment_id=99, bz=_fake_bz(att))

    # A missing-data attachment must never produce a file on disk.
    assert os.listdir(tmp_path) == []


@pytest.mark.asyncio
async def test_download_attachment_text_invalid_utf8_falls_back_to_base64(tmp_path):
    server.download_dir = str(tmp_path)
    # Latin-1 bytes mislabeled as text/plain; 0xff is not valid UTF-8.
    blob = b"caf\xe9 \xff\xfe"
    att = {
        "id": 55,
        "file_name": "mislabeled.txt",
        "content_type": "text/plain",
        "data": base64.b64encode(blob).decode(),
    }

    result = await server.download_attachment(
        attachment_id=55, delivery="inline", bz=_fake_bz(att)
    )

    # Strict decode fails, so we must return base64 rather than corrupted text.
    assert result["mode"] == "base64"
    assert base64.b64decode(result["data_base64"]) == blob
    assert "content" not in result


@pytest.mark.asyncio
async def test_download_attachment_unwritable_dir_raises(tmp_path):
    # Make output_dir's parent a regular file so os.makedirs fails with OSError.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir")
    att = {
        "id": 21,
        "file_name": "x.bin",
        "content_type": "application/octet-stream",
        "data": base64.b64encode(b"\x00\x01").decode(),
    }

    with pytest.raises(ToolError, match="Cannot create download directory"):
        await server.download_attachment(
            attachment_id=21,
            output_dir=str(blocker / "sub"),
            delivery="save",
            bz=_fake_bz(att),
        )


@pytest.mark.asyncio
async def test_download_attachment_private_refused_by_default(tmp_path):
    server.download_dir = str(tmp_path)
    att = {
        "id": 31,
        "file_name": "secret.txt",
        "content_type": "text/plain",
        "is_private": True,
        "data": base64.b64encode(b"top secret").decode(),
    }

    with pytest.raises(ToolError, match="is private"):
        await server.download_attachment(attachment_id=31, bz=_fake_bz(att))

    assert os.listdir(tmp_path) == []


@pytest.mark.asyncio
async def test_download_attachment_private_allowed_with_flag(tmp_path):
    server.download_dir = str(tmp_path)
    att = {
        "id": 32,
        "file_name": "secret.txt",
        "content_type": "text/plain",
        "is_private": True,
        "data": base64.b64encode(b"top secret").decode(),
    }

    result = await server.download_attachment(
        attachment_id=32, include_private=True, bz=_fake_bz(att)
    )

    assert result["mode"] == "text"
    assert result["content"] == "top secret"
    assert result["is_private"] is True


@pytest.mark.asyncio
@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes only")
async def test_download_attachment_default_dir_is_owner_only(tmp_path):
    import stat

    default_dir = tmp_path / "mcp-bugzilla"
    server.download_dir = str(default_dir)
    att = {
        "id": 71,
        "file_name": "image.png",
        "content_type": "application/octet-stream",
        "data": base64.b64encode(b"\x89PNG").decode(),
    }

    # No output_dir -> default dir, which must be restricted to the owner.
    await server.download_attachment(
        attachment_id=71, delivery="save", bz=_fake_bz(att)
    )

    assert stat.S_IMODE(os.stat(default_dir).st_mode) == 0o700


@pytest.mark.asyncio
async def test_list_attachments_tool_passthrough():
    bz = AsyncMock()
    bz.list_attachments = AsyncMock(
        return_value=[{"id": 1, "file_name": "a.txt"}, {"id": 2, "file_name": "b.txt"}]
    )

    result = await server.list_attachments(bug_id=123, bz=bz)

    assert [a["id"] for a in result] == [1, 2]
    bz.list_attachments.assert_awaited_once_with(123)
