"""
Unit test suite for Basalam MCP.
Tests endpoints, vendor trust appraisal, product deal analysis, tool execution, and MCP server JSON-RPC.
"""

import unittest
from unittest.mock import MagicMock, patch
from basalam_mcp.client import BasalamClient, BASALAM_CATEGORIES
from basalam_mcp.analytics import appraise_vendor, deal_analysis
from basalam_mcp.tools import execute_tool, TOOLS
from basalam_mcp.server import BasalamMCPServer


class TestBasalamClient(unittest.TestCase):

    def setUp(self):
        self.client = BasalamClient(timeout=2.0)

    def test_list_categories(self):
        cats = self.client.list_categories()
        self.assertIsInstance(cats, list)
        self.assertGreater(len(cats), 5)
        self.assertEqual(cats[0]["name_fa"], "مواد غذایی و خوراکی")

    def test_auth_token_lifecycle(self):
        self.client.set_token("sample-basalam-token-999")
        self.assertEqual(self.client.token, "sample-basalam-token-999")
        headers = self.client._get_headers()
        self.assertEqual(headers["Authorization"], "Bearer sample-basalam-token-999")

        self.assertTrue(self.client.logout())
        self.assertIsNone(self.client.token)

    @patch.object(BasalamClient, "_fetch_json")
    def test_search_products(self, mock_fetch):
        mock_fetch.return_value = {
            "total": 50,
            "products": [
                {
                    "id": "prod-1",
                    "title": "زعفران سرگل ممتاز قائنات",
                    "price": 350000,
                    "vendor": {
                        "id": "v-1",
                        "name": "مزرعه طلای سرخ",
                        "city": "قائنات",
                    },
                    "rating": {"rate": 4.8, "count": 120},
                }
            ],
        }

        res = self.client.search_products(query="زعفران")
        self.assertEqual(res["count"], 50)
        self.assertEqual(len(res["results"]), 1)
        item = res["results"][0]
        self.assertEqual(item["id"], "prod-1")
        self.assertEqual(item["title"], "زعفران سرگل ممتاز قائنات")
        self.assertEqual(item["vendor"]["name"], "مزرعه طلای سرخ")

    @patch.object(BasalamClient, "_fetch_json")
    def test_get_product_details(self, mock_fetch):
        mock_fetch.return_value = {
            "id": "12345",
            "title": "عسل طبیعی سبلان",
            "price": 450000,
            "stock": 10,
            "description": "عسل خالص بهاره سبلان",
            "vendor": {
                "id": "v-2",
                "title": "کندوداران اردبیل",
                "city": "اردبیل",
            },
        }

        res = self.client.get_product_details("12345")
        self.assertEqual(res["id"], "12345")
        self.assertEqual(res["title"], "عسل طبیعی سبلان")
        self.assertEqual(res["price"], 450000)
        self.assertEqual(res["vendor"]["title"], "کندوداران اردبیل")

    @patch.object(BasalamClient, "_fetch_json")
    def test_get_vendor_details(self, mock_fetch):
        mock_fetch.return_value = {
            "id": "v-100",
            "title": "کارگاه قلمزنی اصفهان",
            "identifier": "ghalamzani_esfahan",
            "city": "اصفهان",
            "rating": {"rate": 4.9, "count": 210},
            "products_count": 45,
        }

        res = self.client.get_vendor_details("v-100")
        self.assertEqual(res["id"], "v-100")
        self.assertEqual(res["name"], "کارگاه قلمزنی اصفهان")
        self.assertEqual(res["city"], "اصفهان")
        self.assertEqual(res["rating"], 4.9)


    @patch.object(BasalamClient, "_fetch_json")
    def test_popular_searches(self, mock_fetch):
        mock_fetch.return_value = {"items": ["زعفران", "عسل"]}
        res = self.client.get_popular_searches()
        self.assertIn("searches", res)


class TestBasalamAnalytics(unittest.TestCase):

    def test_appraise_vendor_score(self):
        vendor = {
            "id": "v-top",
            "name": "زعفران ناب مشهد",
            "rating": 4.9,
            "total_reviews": 250,
            "total_products": 30,
        }
        res = appraise_vendor(vendor)
        self.assertGreaterEqual(res["trust_score"], 80.0)
        self.assertIn("Top Rated", res["verdict"])

    def test_deal_analysis(self):
        product = {
            "id": "p-1",
            "title": "کشک خانگی گوسفندی",
            "price": 180000,
            "price_text": "۱۸۰,۰۰۰ تومان",
            "rating": 4.8,
        }
        deal = deal_analysis(product)
        self.assertGreaterEqual(deal["value_score"], 80.0)
        self.assertIn("ارزش خرید بالا", deal["verdict"])


class TestBasalamToolsAndServer(unittest.TestCase):

    def test_tools_count_and_names(self):
        self.assertEqual(len(TOOLS), 18)
        names = [t["name"] for t in TOOLS]
        self.assertIn("basalam_search_products", names)
        self.assertIn("basalam_get_product_details", names)
        self.assertIn("basalam_get_vendor_details", names)
        self.assertIn("basalam_appraise_vendor", names)
        self.assertIn("basalam_deal_analysis", names)
        self.assertIn("basalam_status", names)

    def test_status_and_help(self):
        status = execute_tool("basalam_status", {})
        self.assertEqual(status["service"], "basalam-mcp")
        self.assertEqual(status["status"], "operational")

        help_data = execute_tool("basalam_help", {})
        self.assertIn("tools", help_data)
        self.assertEqual(len(help_data["tools"]), 18)

    def test_mcp_server_protocol(self):
        server = BasalamMCPServer()

        # Init
        init_res = server.handle_request({"id": 1, "method": "initialize"})
        self.assertEqual(init_res["result"]["serverInfo"]["name"], "basalam-mcp")

        # Tools list
        tools_res = server.handle_request({"id": 2, "method": "tools/list"})
        self.assertEqual(len(tools_res["result"]["tools"]), 18)

        # Call
        call_res = server.handle_request({
            "id": 3,
            "method": "tools/call",
            "params": {"name": "basalam_status", "arguments": {}},
        })
        self.assertFalse(call_res["result"]["isError"])
        self.assertIn("operational", call_res["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
