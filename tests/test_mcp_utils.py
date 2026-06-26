import pytest
import pytest_asyncio
import respx
from httpx import Response
from mcp_bugzilla.mcp_utils import Bugzilla, is_textual, safe_filename
from datetime import datetime

MOCK_URL = "https://bugzilla.example.com"
MOCK_API_KEY = "secret_key"


@pytest_asyncio.fixture
async def bz_client():
    client = Bugzilla(MOCK_URL, MOCK_API_KEY)
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_bugzilla_info(bz_client):
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        respx_mock.get("/rest/version").mock(
            return_value=Response(200, json={"version": "5.0.4"})
        )
        respx_mock.get("/rest/extensions").mock(
            return_value=Response(200, json={"extensions": {"MockExtension": {}}})
        )
        respx_mock.get("/rest/time").mock(
            return_value=Response(
                200, json={"tz_name": "UTC", "web_time": "2026-03-18T10:00:00Z"}
            )
        )
        respx_mock.get("/rest/parameters").mock(
            return_value=Response(200, json={"parameters": {"urlbase": "http://mock"}})
        )

        info = await bz_client.bugzilla_info()
        assert info["url"] == MOCK_URL.rstrip("/rest")
        assert info["version"] == "5.0.4"
        assert "MockExtension" in info["extensions"]
        assert info["timezone"] == "UTC"
        assert info["time"] == "2026-03-18T10:00:00Z"
        assert info["parameters"]["urlbase"] == "http://mock"


@pytest.mark.asyncio
async def test_bug_info_single(bz_client):
    """Test fetching info for a single bug ID"""
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        route_bug = respx_mock.get("/rest/bug/123").mock(
            return_value=Response(
                200, json={"bugs": [{"id": 123, "summary": "Single Test Bug"}]}
            )
        )

        bug_env = await bz_client.bug_info({123})
        assert len(bug_env["bugs"]) == 1
        assert bug_env["bugs"][0]["id"] == 123
        assert bug_env["bugs"][0]["summary"] == "Single Test Bug"
        assert route_bug.called


@pytest.mark.asyncio
async def test_bug_info_multiple(bz_client):
    """Test fetching info for multiple bug IDs"""
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        route_bug = respx_mock.get("/rest/bug").mock(
            return_value=Response(
                200,
                json={
                    "bugs": [
                        {"id": 123, "summary": "Test Bug"},
                        {"id": 456, "summary": "Another Bug"},
                    ]
                },
            )
        )

        bug_env = await bz_client.bug_info({123, 456})
        assert any(b["id"] == 123 for b in bug_env["bugs"])
        assert any(b["id"] == 456 for b in bug_env["bugs"])

        assert route_bug.called
        id_param = route_bug.calls.last.request.url.params["id"]
        assert set(id_param.split(",")) == {"123", "456"}


@pytest.mark.asyncio
async def test_bug_history(bz_client):
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        route = respx_mock.get("/rest/bug/123/history").mock(
            return_value=Response(
                200,
                json={
                    "bugs": [
                        {
                            "id": 123,
                            "history": [
                                {
                                    "when": "2026-03-09T10:00:00Z",
                                    "who": "user@example.com",
                                }
                            ],
                        }
                    ]
                },
            )
        )

        history = await bz_client.bug_history(123)
        assert len(history) == 1
        assert history[0]["when"] == "2026-03-09T10:00:00Z"
        assert route.called
        assert "new_since" not in route.calls.last.request.url.params

        test_dt = datetime(2026, 3, 9, 0, 0, 0)
        history_with_since = await bz_client.bug_history(123, new_since=test_dt)
        assert len(history_with_since) == 1
        assert (
            route.calls.last.request.url.params["new_since"] == "2026-03-09T00:00:00Z"
        )


@pytest.mark.asyncio
async def test_bug_comments(bz_client):
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        route = respx_mock.get("/rest/bug/123/comment").mock(
            return_value=Response(
                200,
                json={
                    "bugs": {
                        "123": {
                            "comments": [
                                {"id": 1, "text": "Comment 1"},
                                {"id": 2, "text": "Comment 2"},
                            ]
                        }
                    }
                },
            )
        )

        comments = await bz_client.bug_comments(123)
        assert len(comments) == 2
        assert comments[0]["text"] == "Comment 1"
        assert route.called
        assert "new_since" not in route.calls.last.request.url.params

        test_dt = datetime(2000, 1, 1, 0, 0, 0)
        comments_with_since = await bz_client.bug_comments(123, new_since=test_dt)
        assert len(comments_with_since) == 2
        assert (
            route.calls.last.request.url.params["new_since"] == "2000-01-01T00:00:00Z"
        )


@pytest.mark.asyncio
async def test_add_comment(bz_client):
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        fake_response = {"id": 101}
        route = respx_mock.post("/rest/bug/123/comment").mock(
            return_value=Response(201, json=fake_response)
        )

        resp = await bz_client.add_comment(123, "New comment", is_private=False)
        assert resp == fake_response

        # Verify call arguments
        assert route.called
        assert bz_client.api_key in str(route.calls.last.request.url)


@pytest.mark.asyncio
async def test_create_bug(bz_client):
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        route = respx_mock.post("/rest/bug").mock(
            return_value=Response(200, json={"id": 777})
        )

        fields = {
            "product": "TestProduct",
            "component": "TestComponent",
            "summary": "A new bug",
            "version": "unspecified",
            "description": "Steps to reproduce ...",
        }
        resp = await bz_client.create_bug(fields)

        assert resp == {"id": 777}
        assert route.called
        # API key is forwarded and the fields are in the POST body.
        assert bz_client.api_key in str(route.calls.last.request.url)
        body = route.calls.last.request.content
        assert b'"product"' in body
        assert b"TestComponent" in body


@pytest.mark.asyncio
async def test_create_bug_missing_required_field_surfaces_error(bz_client):
    """A Bugzilla validation error (missing field) propagates to the caller."""
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        respx_mock.post("/rest/bug").mock(
            return_value=Response(
                400,
                json={
                    "error": True,
                    "message": "You must select/enter a component.",
                    "code": 106,
                },
            )
        )

        with pytest.raises(Exception) as exc_info:
            await bz_client.create_bug({"product": "P", "summary": "S"})

        assert (
            "400" in str(exc_info.value) or "component" in str(exc_info.value).lower()
        )


@pytest.mark.asyncio
async def test_add_attachment(bz_client):
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        route = respx_mock.post("/rest/bug/123/attachment").mock(
            return_value=Response(201, json={"ids": [42]})
        )

        payload = {
            "ids": [123],
            "file_name": "log.txt",
            "summary": "failing testsuite output",
            "data": "aGVsbG8=",  # base64("hello")
            "content_type": "text/plain",
        }
        resp = await bz_client.add_attachment(123, payload)

        assert resp == {"ids": [42]}
        assert route.called
        body = route.calls.last.request.content
        assert b"aGVsbG8=" in body
        assert b"log.txt" in body


@pytest.mark.asyncio
async def test_list_attachments(bz_client):
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        route = respx_mock.get("/rest/bug/123/attachment").mock(
            return_value=Response(
                200,
                json={
                    "bugs": {
                        "123": [
                            {
                                "id": 42,
                                "file_name": "log.txt",
                                "content_type": "text/plain",
                                "size": 5,
                            },
                            {
                                "id": 43,
                                "file_name": "patch.diff",
                                "content_type": "text/x-patch",
                                "size": 10,
                            },
                        ]
                    },
                    "attachments": {},
                },
            )
        )

        attachments = await bz_client.list_attachments(123)

        assert [a["id"] for a in attachments] == [42, 43]
        assert all("data" not in a for a in attachments)
        assert route.called
        # exclude_fields=data must be sent (alongside the client's api_key param)
        assert route.calls.last.request.url.params["exclude_fields"] == "data"
        assert route.calls.last.request.url.params["api_key"] == MOCK_API_KEY


@pytest.mark.asyncio
async def test_get_attachment(bz_client):
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        route = respx_mock.get("/rest/bug/attachment/42").mock(
            return_value=Response(
                200,
                json={
                    "attachments": {
                        "42": {
                            "id": 42,
                            "file_name": "log.txt",
                            "content_type": "text/plain",
                            "size": 5,
                            "data": "aGVsbG8=",  # base64("hello")
                        }
                    },
                    "bugs": {},
                },
            )
        )

        att = await bz_client.get_attachment(42)

        assert att["id"] == 42
        assert att["data"] == "aGVsbG8="
        assert route.called


@pytest.mark.asyncio
async def test_get_attachment_missing_raises(bz_client):
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        respx_mock.get("/rest/bug/attachment/999").mock(
            return_value=Response(200, json={"attachments": {}, "bugs": {}})
        )

        with pytest.raises(ValueError, match="999 not found"):
            await bz_client.get_attachment(999)


@pytest.mark.asyncio
async def test_quicksearch(bz_client):
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        route = respx_mock.get("/rest/bug").mock(
            return_value=Response(200, json={"bugs": [{"id": 1}, {"id": 2}]})
        )

        # Test with explicit arguments (mandatory in mcp_utils)
        search_env = await bz_client.quicksearch(
            "product:Foo", status="ALL", include_fields="id,product", limit=50, offset=0
        )
        assert len(search_env["bugs"]) == 2

        # Verify call arguments
        assert route.called
        params = route.calls.last.request.url.params
        assert params["quicksearch"] == "ALL product:Foo"
        assert params["limit"] == "50"
        assert params["offset"] == "0"
        assert "include_fields" in params
        assert params["include_fields"] == "id,product"


@pytest.mark.asyncio
async def test_update_bug_single_field(bz_client):
    """Test updating a single field"""
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        respx_mock.put("/rest/bug/123").mock(
            return_value=Response(
                200,
                json={
                    "bugs": [
                        {
                            "id": 123,
                            "changes": {
                                "priority": {"removed": "low", "added": "high"}
                            },
                            "last_change_time": "2026-03-09T10:00:00Z",
                        }
                    ]
                },
            )
        )

        result = await bz_client.update_bug(bug_id=123, updates={"priority": "high"})

        assert result["bugs"][0]["id"] == 123
        assert "priority" in result["bugs"][0]["changes"]
        assert result["bugs"][0]["changes"]["priority"]["added"] == "high"


@pytest.mark.asyncio
async def test_update_bug_multiple_fields(bz_client):
    """Test updating multiple fields simultaneously"""
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        respx_mock.put("/rest/bug/123").mock(
            return_value=Response(
                200,
                json={
                    "bugs": [
                        {
                            "id": 123,
                            "changes": {
                                "priority": {"removed": "low", "added": "high"},
                                "severity": {"removed": "medium", "added": "urgent"},
                                "status": {"removed": "NEW", "added": "ASSIGNED"},
                            },
                        }
                    ]
                },
            )
        )

        result = await bz_client.update_bug(
            bug_id=123,
            updates={"priority": "high", "severity": "urgent", "status": "ASSIGNED"},
        )

        changes = result["bugs"][0]["changes"]
        assert len(changes) == 3
        assert changes["priority"]["added"] == "high"
        assert changes["severity"]["added"] == "urgent"
        assert changes["status"]["added"] == "ASSIGNED"


@pytest.mark.asyncio
async def test_update_bug_with_comment(bz_client):
    """Test bug update with optional comment"""
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        route = respx_mock.put("/rest/bug/123").mock(
            return_value=Response(
                200,
                json={
                    "bugs": [
                        {
                            "id": 123,
                            "changes": {
                                "status": {"removed": "NEW", "added": "CLOSED"},
                                "resolution": {"removed": "", "added": "FIXED"},
                            },
                        }
                    ]
                },
            )
        )

        result = await bz_client.update_bug(
            bug_id=123,
            updates={"status": "CLOSED", "resolution": "FIXED"},
            comment="Fixed in commit abc123",
        )

        assert result["bugs"][0]["id"] == 123
        # Verify comment was included in request
        assert route.called
        request_body = route.calls.last.request.content
        assert b"Fixed in commit abc123" in request_body


@pytest.mark.asyncio
async def test_update_bug_close_with_resolution(bz_client):
    """Test closing a bug with required resolution"""
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        respx_mock.put("/rest/bug/123").mock(
            return_value=Response(
                200,
                json={
                    "bugs": [
                        {
                            "id": 123,
                            "changes": {
                                "status": {"removed": "ASSIGNED", "added": "CLOSED"},
                                "resolution": {"removed": "", "added": "FIXED"},
                            },
                        }
                    ]
                },
            )
        )

        result = await bz_client.update_bug(
            bug_id=123, updates={"status": "CLOSED", "resolution": "FIXED"}
        )

        changes = result["bugs"][0]["changes"]
        assert changes["status"]["added"] == "CLOSED"
        assert changes["resolution"]["added"] == "FIXED"


@pytest.mark.asyncio
async def test_update_bug_duplicate_fields(bz_client):
    """Test marking bug as duplicate"""
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        respx_mock.put("/rest/bug/123").mock(
            return_value=Response(
                200,
                json={
                    "bugs": [
                        {
                            "id": 123,
                            "changes": {
                                "status": {"removed": "NEW", "added": "CLOSED"},
                                "resolution": {"removed": "", "added": "DUPLICATE"},
                                "dupe_of": {"removed": "", "added": "456"},
                            },
                        }
                    ]
                },
            )
        )

        result = await bz_client.update_bug(
            bug_id=123,
            updates={"status": "CLOSED", "resolution": "DUPLICATE", "dupe_of": 456},
        )

        changes = result["bugs"][0]["changes"]
        assert changes["resolution"]["added"] == "DUPLICATE"
        assert changes["dupe_of"]["added"] == "456"


@pytest.mark.asyncio
async def test_update_bug_not_found(bz_client):
    """Test error handling for non-existent bug"""
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        respx_mock.put("/rest/bug/999999").mock(
            return_value=Response(
                404,
                json={
                    "error": True,
                    "message": "Bug #999999 does not exist.",
                    "code": 101,
                },
            )
        )

        with pytest.raises(Exception) as exc_info:
            await bz_client.update_bug(bug_id=999999, updates={"priority": "high"})

        assert (
            "404" in str(exc_info.value)
            or "does not exist" in str(exc_info.value).lower()
        )


@pytest.mark.asyncio
async def test_update_bug_permission_denied(bz_client):
    """Test error handling for insufficient permissions"""
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        respx_mock.put("/rest/bug/123").mock(
            return_value=Response(
                401,
                json={
                    "error": True,
                    "message": "You are not authorized to edit this bug",
                    "code": 102,
                },
            )
        )

        with pytest.raises(Exception) as exc_info:
            await bz_client.update_bug(
                bug_id=123, updates={"assigned_to": "other@example.com"}
            )

        assert (
            "401" in str(exc_info.value)
            or "not authorized" in str(exc_info.value).lower()
        )


@pytest.mark.asyncio
async def test_update_bug_validation_error(bz_client):
    """Test validation error for invalid field combinations"""
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        respx_mock.put("/rest/bug/123").mock(
            return_value=Response(
                400,
                json={
                    "error": True,
                    "message": "You must provide a resolution when status is CLOSED",
                    "code": 121,
                },
            )
        )

        with pytest.raises(Exception) as exc_info:
            await bz_client.update_bug(
                bug_id=123,
                updates={"status": "CLOSED"},  # Missing required resolution
            )

        assert (
            "400" in str(exc_info.value) or "resolution" in str(exc_info.value).lower()
        )


@pytest.mark.asyncio
async def test_update_bug_empty_updates(bz_client):
    """Test behavior with empty updates dictionary"""
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        respx_mock.put("/rest/bug/123").mock(
            return_value=Response(200, json={"bugs": [{"id": 123, "changes": {}}]})
        )

        result = await bz_client.update_bug(bug_id=123, updates={})

        assert result["bugs"][0]["changes"] == {}


@pytest.mark.asyncio
async def test_update_bug_comment_only(bz_client):
    """Test adding comment without field updates"""
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        route = respx_mock.put("/rest/bug/123").mock(
            return_value=Response(200, json={"bugs": [{"id": 123, "changes": {}}]})
        )

        result = await bz_client.update_bug(
            bug_id=123, updates={}, comment="Just adding a comment"
        )

        assert result["bugs"][0]["id"] == 123
        assert route.called
        request_body = route.calls.last.request.content
        assert b"Just adding a comment" in request_body


@pytest.mark.parametrize(
    "content_type,expected",
    [
        ("text/plain", True),
        ("text/x-log", True),
        ("text/plain; charset=utf-8", True),
        ("TEXT/PLAIN", True),
        ("application/json", True),
        ("application/xml", True),
        ("application/x-yaml", True),
        ("image/svg+xml", True),
        ("application/foo+xml", True),
        ("application/vnd.api+json", True),
        ("text/x-patch", True),
        ("application/x-diff", True),
        ("application/octet-stream", False),
        ("image/png", False),
        ("application/pdf", False),
        ("", False),
        (None, False),
    ],
)
def test_is_textual(content_type, expected):
    assert is_textual(content_type) is expected


@pytest.mark.parametrize(
    "name,expected",
    [
        ("report.txt", "report.txt"),
        ("../../etc/passwd", "passwd"),
        ("/abs/path/file.log", "file.log"),
        ("weird name!@#.txt", "weird_name___.txt"),
        ("café.txt", "caf_.txt"),
        (None, "attachment-7"),
        ("", "attachment-7"),
        ("...", "attachment-7"),
        ("///", "attachment-7"),
    ],
)
def test_safe_filename(name, expected):
    assert safe_filename(name, 7) == expected
