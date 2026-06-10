"""Unit tests for KancmasterXMLClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.integrations.kancmaster.client import KancmasterXMLClient

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<root>
  <item>
    <id>101</id>
    <name>\u0420\u0443\u0447\u043a\u0430 \u043a\u0443\u043b\u044c\u043a\u043e\u0432\u0430</name>
    <price>12,50</price>
    <quantity>100</quantity>
    <category>\u0420\u0443\u0447\u043a\u0438</category>
    <vendor>Pilot</vendor>
    <article>SKU-101</article>
    <description>\u0421\u0438\u043d\u044f \u043a\u0443\u043b\u044c\u043a\u043e\u0432\u0430 \u0440\u0443\u0447\u043a\u0430</description>
    <picture>https://cdn.example.com/img1.jpg</picture>
    <picture>https://cdn.example.com/img2.jpg</picture>
  </item>
  <item>
    <id>102</id>
    <name>\u041e\u043b\u0456\u0432\u0435\u0446\u044c</name>
    <price>5.00</price>
    <quantity>0</quantity>
    <category>\u041e\u043b\u0456\u0432\u0446\u0456</category>
    <vendor></vendor>
    <article></article>
    <description></description>
    <picture>https://cdn.example.com/pencil.jpg</picture>
  </item>
</root>
""".encode("utf-8")

BROKEN_XML = b"<root><item><id>1</id><name>Bad</name><price>NOT_A_NUMBER</price>"  # intentionally truncated

SAMPLE_YML = """<?xml version="1.0" encoding="UTF-8"?>
<yml_catalog date="2026-05-22">
  <shop>
    <categories>
      <category id="10">Ручки</category>
      <category id="20">Олівці</category>
    </categories>
    <offers>
      <offer id="201" available="true">
        <name>Ручка YML</name>
        <price>15.00</price>
        <categoryId>10</categoryId>
        <vendor>Pilot</vendor>
        <barcode>BC-201</barcode>
        <description><![CDATA[<p>Опис YML</p>]]></description>
        <picture>https://cdn.example.com/yml1.jpg</picture>
        <picture>https://cdn.example.com/yml2.jpg</picture>
      </offer>
      <offer id="202" available="false">
        <name>Олівець YML</name>
        <price>3.00</price>
        <categoryId>20</categoryId>
      </offer>
    </offers>
  </shop>
</yml_catalog>
""".encode("utf-8")


@pytest.fixture()
def client(settings):
    settings.KANCMASTER_XML_URL = "https://kancmaster.com.ua/xml_export_request"
    settings.KANCMASTER_LOGIN = "testlogin"
    settings.KANCMASTER_PASSWORD = "testpass"
    return KancmasterXMLClient()


class TestFetchXml:
    def test_returns_bytes_on_success(self, client):
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_XML
        mock_resp.raise_for_status = MagicMock()
        with patch("apps.integrations.kancmaster.client.httpx.get", return_value=mock_resp) as mock_get:
            result = client.fetch_xml()
        assert result == SAMPLE_XML
        mock_get.assert_called_once_with(
            "https://kancmaster.com.ua/xml_export_request",
            params={"login": "testlogin", "password": "testpass"},
            timeout=300,
            follow_redirects=True,
        )

    def test_no_params_when_credentials_empty(self, settings):
        settings.KANCMASTER_XML_URL = "https://kancmaster.com.ua/unique-token-url/"
        settings.KANCMASTER_LOGIN = ""
        settings.KANCMASTER_PASSWORD = ""
        client_no_creds = KancmasterXMLClient()
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_XML
        mock_resp.raise_for_status = MagicMock()
        with patch("apps.integrations.kancmaster.client.httpx.get", return_value=mock_resp) as mock_get:
            client_no_creds.fetch_xml()
        mock_get.assert_called_once_with(
            "https://kancmaster.com.ua/unique-token-url/",
            params=None,
            timeout=300,
            follow_redirects=True,
        )

    def test_returns_none_on_http_error(self, client):
        with patch("apps.integrations.kancmaster.client.httpx.get", side_effect=Exception("timeout")):
            result = client.fetch_xml()
        assert result is None


class TestParseProducts:
    def test_parses_two_items(self, client):
        products = client.parse_products(SAMPLE_XML)
        assert len(products) == 2

    def test_first_item_fields(self, client):
        p = client.parse_products(SAMPLE_XML)[0]
        assert p["id"] == "101"
        assert p["name"] == "Ручка кулькова"
        assert p["price"] == "12,50"
        assert p["quantity"] == "100"
        assert p["category"] == "Ручки"
        assert p["brand"] == "Pilot"
        assert p["sku"] == "SKU-101"
        assert p["description"] == "Синя кулькова ручка"

    def test_multiple_pictures_collected(self, client):
        p = client.parse_products(SAMPLE_XML)[0]
        assert p["image_url"] == "https://cdn.example.com/img1.jpg"
        assert p["image_urls"] == [
            "https://cdn.example.com/img1.jpg",
            "https://cdn.example.com/img2.jpg",
        ]

    def test_single_picture(self, client):
        p = client.parse_products(SAMPLE_XML)[1]
        assert p["image_url"] == "https://cdn.example.com/pencil.jpg"
        assert p["image_urls"] == ["https://cdn.example.com/pencil.jpg"]

    def test_zero_quantity_item(self, client):
        p = client.parse_products(SAMPLE_XML)[1]
        assert p["quantity"] == "0"

    def test_returns_empty_list_on_broken_xml(self, client):
        products = client.parse_products(b"not xml at all <<<")
        assert products == []

    def test_parses_yml_offers(self, client):
        products = client.parse_products(SAMPLE_YML)
        assert len(products) == 2

    def test_yml_category_id_resolved(self, client):
        p = client.parse_products(SAMPLE_YML)[0]
        assert p["category"] == "Ручки"
        assert p["id"] == "201"

    def test_yml_barcode_as_sku(self, client):
        p = client.parse_products(SAMPLE_YML)[0]
        assert p["sku"] == "BC-201"

    def test_yml_available_false_zero_quantity(self, client):
        p = client.parse_products(SAMPLE_YML)[1]
        assert p["quantity"] == "0"

    def test_yml_available_true_default_quantity(self, client):
        p = client.parse_products(SAMPLE_YML)[0]
        assert p["quantity"] == "1"

    def test_yml_description_from_cdata(self, client):
        p = client.parse_products(SAMPLE_YML)[0]
        assert "Опис YML" in p["description"]

    def test_legacy_item_format_still_supported(self, client):
        """item and offer must not be mixed when items are present."""
        products = client.parse_products(SAMPLE_XML)
        assert len(products) == 2
        assert products[0]["id"] == "101"
