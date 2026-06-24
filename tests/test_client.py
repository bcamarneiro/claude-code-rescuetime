import io
import unittest
import urllib.parse
import urllib.request


class TestClient(unittest.TestCase):
    def test_posts_correct_params(self):
        from rt_claude.client import post_highlight

        captured = {}

        class MockResponse:
            status = 201
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        def mock_opener(req, timeout=None):
            captured["url"] = req.full_url
            captured["method"] = req.method
            captured["body"] = req.data
            return MockResponse()

        post_highlight(
            api_key="testkey",
            description="myproject · main",
            source="claude-code",
            today="2026-06-24",
            opener=mock_opener,
        )

        self.assertEqual(captured["method"], "POST")
        params = dict(urllib.parse.parse_qsl(captured["body"].decode()))
        self.assertEqual(params["key"], "testkey")
        self.assertEqual(params["description"], "myproject · main")
        self.assertEqual(params["source"], "claude-code")
        self.assertEqual(params["highlight_date"], "2026-06-24")

    def test_truncates_description_to_255(self):
        from rt_claude.client import post_highlight

        captured = {}

        class MockResponse:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        def mock_opener(req, timeout=None):
            captured["body"] = req.data
            return MockResponse()

        long_desc = "x" * 300
        post_highlight(
            api_key="k",
            description=long_desc,
            source="claude-code",
            today="2026-06-24",
            opener=mock_opener,
        )

        params = dict(urllib.parse.parse_qsl(captured["body"].decode()))
        self.assertEqual(len(params["description"]), 255)


if __name__ == "__main__":
    unittest.main()
