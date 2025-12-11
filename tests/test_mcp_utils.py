
import pytest
import pytest_asyncio
import respx
from httpx import Response
from mcp_bugzilla.mcp_utils import Bugzilla

MOCK_URL = "https://bugzilla.example.com"
MOCK_API_KEY = "secret_key"

@pytest_asyncio.fixture
async def bz_client():
    client = Bugzilla(MOCK_URL, MOCK_API_KEY)
    yield client
    await client.close()

@pytest.mark.asyncio
async def test_bug_info(bz_client):
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        # Note: Bugzilla client appends /rest to the base url passed in constructor
        # and then requests /bug/{id} relative to that.
        # But the bugzilla client sets base_url of httpx client to .../rest
        # So we should match against the full URL or careful with defaults.
        # Given the implementation: self.client = httpx.AsyncClient(base_url=self.api_url, ...)
        # where self.api_url = url + "/rest"
        # The request is client.get(f"/bug/{bug_id}") which resolves to {url}/rest/bug/{bug_id}
        
        # respx mocks verify the full URL usually.
        
        respx_mock.get("/rest/bug/123").mock(
            return_value=Response(200, json={"bugs": [{"id": 123, "summary": "Test Bug"}]})
        )
        
        bug = await bz_client.bug_info(123)
        assert bug["id"] == 123
        assert bug["summary"] == "Test Bug"

@pytest.mark.asyncio
async def test_bug_comments(bz_client):
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        respx_mock.get("/rest/bug/123/comment").mock(
            return_value=Response(
                200, 
                json={
                    "bugs": {
                        "123": {
                            "comments": [
                                {"id": 1, "text": "Comment 1"},
                                {"id": 2, "text": "Comment 2"}
                            ]
                        }
                    }
                }
            )
        )
        
        comments = await bz_client.bug_comments(123)
        assert len(comments) == 2
        assert comments[0]["text"] == "Comment 1"

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
async def test_quicksearch(bz_client):
    async with respx.mock(base_url=MOCK_URL) as respx_mock:
        respx_mock.get("/rest/bug").mock(
            return_value=Response(200, json={"bugs": [{"id": 1}, {"id": 2}]})
        )
        
        bugs = await bz_client.quicksearch("product:Foo")
        assert len(bugs) == 2
