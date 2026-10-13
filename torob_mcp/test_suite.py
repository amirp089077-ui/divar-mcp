"""
Unit test suite for Torob MCP.
Tests client endpoints, analytics algorithms, tool dispatcher, and server JSON-RPC protocol.
"""

import unittest
from unittest.mock import MagicMock, patch
from torob_mcp.client import TorobClient, TOROB_CATEGORIES
from torob_mcp.analytics import compare_stores, appraise_deal, analyze_price_trend
from torob_mcp.tools import execute_tool, TOOLS
from torob_mcp.server import TorobMCPServer


class TestTorobClient(unittest.TestCase):

    def setUp(self):
        self.client = TorobClient(timeout=2.0)

    def test_list_categories(self):
        cats = self.client.list_categories()
        self.assertIsInstance(cats, list)
        self.assertGreater(len(cats), 5)
        self.assertEqual(cats[0]["name_fa"], "موبایل و تبلت")

    def test_auth_token_management(self):
        self.client.set_token("test-secret-token-12345")
        self.assertEqual(self.client.token, "test-secret-token-12345")
        headers = self.client._get_headers()
        self.assertIn("Authorization", headers)
        self.assertEqual(headers["Authorization"], "Token test-secret-token-12345")

        success = self.client.logout()
        self.assertTrue(success)
        self.assertIsNone(self.client.token)

    @patch.object(TorobClient, "_fetch_json")
    def test_search_products(self, mock_fetch):
        mock_fetch.return_value = {
            "count": 100,
            "results": [
                {
                    "random_key": "prk-test-1",
                    "name1": "گوشی سامسونگ گلکسی S24",
                    "name2": "Samsung Galaxy S24",
                    "price": 50000000,
                    "num_shops": 12,
                    "image_url": "https://img.torob.com/s24.jpg",
                }
            ],
        }

        res = self.client.search_products(query="سامسونگ S24")
        self.assertEqual(res["count"], 100)
        self.assertEqual(len(res["results"]), 1)
        item = res["results"][0]
        self.assertEqual(item["prk"], "prk-test-1")
        self.assertEqual(item["title"], "گوشی سامسونگ گلکسی S24")
        self.assertEqual(item["price"], 50000000)
        self.assertEqual(item["shops_count"], 12)

    @patch.object(TorobClient, "_fetch_json")
    def test_get_product_details(self, mock_fetch):
        mock_fetch.return_value = {
            "name1": "لپ‌تاپ لنوو LOQ",
            "name2": "Lenovo LOQ",
            "price": 45000000,
            "products_info": [
                {
                    "shop_name": "فروشگاه روژان",
                    "price": 44000000,
                    "city_name": "تهران",
                    "score": 90,
                },
                {
                    "shop_name": "دیجی‌تک",
                    "price": 46000000,
                    "city_name": "شیراز",
                    "score": 95,
                },
            ],
        }

        res = self.client.get_product_details("loq-prk")
        self.assertEqual(res["title"], "لپ‌تاپ لنوو LOQ")
        self.assertEqual(len(res["sellers"]), 2)
        self.assertEqual(res["min_price"], 44000000)
        self.assertEqual(res["max_price"], 46000000)

    @patch.object(TorobClient, "_fetch_json")
    def test_get_price_chart(self, mock_fetch):
        mock_fetch.return_value = {
            "chart": [
                {"date": "2026-01-01", "price": 40000000},
                {"date": "2026-02-01", "price": 42000000},
            ],
            "min_price": 40000000,
            "max_price": 42000000,
        }

        res = self.client.get_price_chart("chart-prk")
        self.assertEqual(res["chart_points_count"], 2)
        self.assertEqual(res["min_price_seen"], 40000000)

    @patch.object(TorobClient, "_fetch_json")
    def test_special_offers(self, mock_fetch):
        mock_fetch.return_value = {
            "count": 50,
            "results": [
                {
                    "random_key": "offer-1",
                    "name1": "هدفون انکر",
                    "price": 1200000,
                    "discount_percent": 25,
                }
            ],
        }

        res = self.client.get_special_offers(page=1)
        self.assertEqual(res["count"], 50)
        self.assertEqual(len(res["results"]), 1)


class TestTorobAnalytics(unittest.TestCase):

    def test_compare_stores(self):
        details = {
            "prk": "test-prk",
            "title": "گوشی آیفون 13",
            "sellers": [
                {
                    "shop_name": "دیجی سنتر",
                    "price": 40000000,
                    "price_text": "۴۰,۰۰۰,۰۰۰ تومان",
                    "shop_score": 4.5,
                },
                {
                    "shop_name": "اپل استور پایتخت",
                    "price": 45000000,
                    "price_text": "۴۵,۰۰۰,۰۰۰ تومان",
                    "shop_score": 4.9,
                },
            ],
        }

        comp = compare_stores(details)
        self.assertEqual(comp["total_stores"], 2)
        self.assertEqual(comp["cheapest_store"]["shop_name"], "دیجی سنتر")
        self.assertEqual(comp["best_rated_store"]["shop_name"], "اپل استور پایتخت")
        self.assertIn("12.5%", comp["price_summary"]["savings_potential"])

    def test_appraise_deal(self):
        details = {
            "prk": "deal-prk",
            "title": "تلویزیون سونی",
            "shops_count": 15,
            "sellers": [
                {"price": 30000000, "shop_score": 4.8},
                {"price": 36000000, "shop_score": 4.2},
            ],
        }

        deal = appraise_deal(details)
        self.assertGreaterEqual(deal["deal_score"], 70.0)
        self.assertIn("Good Deal", deal["verdict"])

    def test_analyze_price_trend(self):
        chart_data = {
            "prk": "trend-prk",
            "history": [
                {"price": 10000000},
                {"price": 9500000},
                {"price": 9000000},
            ],
        }

        analysis = analyze_price_trend(chart_data)
        self.assertIn("Downward Trend", analysis["trend_assessment"])


class TestTorobToolsAndServer(unittest.TestCase):

    def test_tools_definitions(self):
        self.assertEqual(len(TOOLS), 17)
        names = [t["name"] for t in TOOLS]
        self.assertIn("torob_search_products", names)
        self.assertIn("torob_get_product_details", names)
        self.assertIn("torob_compare_stores", names)
        self.assertIn("torob_appraise_deal", names)
        self.assertIn("torob_status", names)

    def test_execute_status_and_help(self):
        status = execute_tool("torob_status", {})
        self.assertEqual(status["service"], "torob-mcp")
        self.assertEqual(status["status"], "operational")

        help_res = execute_tool("torob_help", {})
        self.assertIn("tools", help_res)
        self.assertEqual(len(help_res["tools"]), 17)

    def test_mcp_server_protocol(self):
        server = TorobMCPServer()

        # Initialize
        init_resp = server.handle_request({"id": 1, "method": "initialize"})
        self.assertEqual(init_resp["result"]["serverInfo"]["name"], "torob-mcp")

        # Tools list
        tools_resp = server.handle_request({"id": 2, "method": "tools/list"})
        self.assertEqual(len(tools_resp["result"]["tools"]), 17)

        # Tool call
        call_resp = server.handle_request({
            "id": 3,
            "method": "tools/call",
            "params": {"name": "torob_status", "arguments": {}},
        })
        self.assertFalse(call_resp["result"]["isError"])
        self.assertIn("operational", call_resp["result"]["content"][0]["text"])

        # Unknown method
        unknown_resp = server.handle_request({"id": 4, "method": "unknown_action"})
        self.assertEqual(unknown_resp["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
