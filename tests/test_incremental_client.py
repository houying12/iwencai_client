import os
import unittest
from unittest.mock import patch

from iwencai_client import IWencaiClient, OpenAPIClient, PaginationLimitError


class FakeResponse:
    def __init__(self, status_code, payload, reason="OK", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.reason = reason
        self.headers = headers or {}
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def page(page_number, total=2):
    return FakeResponse(
        200,
        {
            "status_code": 0,
            "code_count": total,
            "chunks_info": {"page": page_number},
            "datas": [{"股票代码": f"00000{page_number}"}],
        },
    )


class IncrementalClientTests(unittest.TestCase):
    def test_original_package_exports_and_get_signature_remain_available(self):
        client = IWencaiClient()
        self.assertTrue(hasattr(client, "get"))
        self.assertTrue(callable(client.get))

    def test_openapi_client_fetches_pages(self):
        session = FakeSession([page(1), page(2)])
        client = OpenAPIClient("test-key", page_size=1, page_delay=0, session=session)

        result = client.query("今日涨停")

        self.assertTrue(result.complete)
        self.assertEqual(result.code_count, 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(session.calls), 2)

    def test_from_env_query_keeps_legacy_client_type(self):
        session = FakeSession([page(1, total=1)])
        with patch.dict(
            os.environ,
            {"IWENCAI_API_KEY": "test-key", "IWENCAI_BASE_URL": "https://example.test"},
            clear=False,
        ):
            client = IWencaiClient.from_env(session=session, page_size=1, page_delay=0)

        result = client.query("今日涨停")

        self.assertEqual(client.base_url, "https://example.test")
        self.assertTrue(result.complete)

    def test_max_pages_is_explicitly_reported(self):
        client = OpenAPIClient(
            "test-key",
            page_size=1,
            max_pages=1,
            page_delay=0,
            session=FakeSession([page(1, total=2)]),
        )

        with self.assertRaises(PaginationLimitError):
            client.query("今日涨停")


if __name__ == "__main__":
    unittest.main()
