import json
import logging
import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def get_oil_from_api():
  url = "https://oil-price.bangchak.co.th/ApiOilPrice2/th"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }
  res = requests.get(url, headers=headers, timeout=10)
  if res.status_code == 200:
    data = res.json()
    items = []
    if isinstance(data, list) and len(data) > 0:
      items = data[0].get("oil", [])
    elif isinstance(data, dict):
      items = (
          data.get("oil", [])
          or data.get("responseData", {}).get("oil", [])
          or data.get("data", {}).get("oil", [])
      )

    oil_data = []
    for item in items:
      name = str(item.get("OilName", "") or item.get("name", "")).strip()
      today = str(item.get("PriceToday", "") or item.get("today", "")).strip()
      tomorrow = str(
          item.get("PriceTomorrow", "") or item.get("tomorrow", "")
      ).strip()
      if name and today and re.search(r"\d", today):
        oil_data.append({"name": name, "today": today, "tomorrow": tomorrow})
    if oil_data:
      return oil_data
  return []


def get_oil_from_playwright():
  url = "https://oil-price.bangchak.co.th/BcpOilPrice1/th"
  oil_data = []
  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    )
    page.goto(url, wait_until="load", timeout=60000)

    page.wait_for_selector("table", timeout=30000)
    page.wait_for_timeout(3000)
    html_content = page.content()
    browser.close()

  soup = BeautifulSoup(html_content, "html.parser")
  rows = soup.find_all("tr")
  for row in rows:
    cols = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
    if len(cols) >= 2:
      name = cols[0]
      today = cols[1]
      tomorrow = cols[2] if len(cols) >= 3 else ""

      if name and today and re.search(r"\d", today):
        if not any(k in name for k in ["ชนิดน้ำมัน", "ราคาน้ำมัน", "วันที่"]):
          oil_data.append({"name": name, "today": today, "tomorrow": tomorrow})
  return oil_data


def scrape_oil_price():
  logger.info("Fetching Bangchak oil price...")
  oil_data = []

  # 1. ลองดึงจาก Official API โดยตรงก่อน
  try:
    oil_data = get_oil_from_api()
    if oil_data:
      logger.info(f"Successfully fetched via API ({len(oil_data)} items)")
  except Exception as e:
    logger.warning(f"API fetch failed: {e}")

  # 2. ถ้า API ไม่ผ่าน ให้สลับไปใช้ Playwright เปิดแกะตาราง HTML
  if not oil_data:
    try:
      logger.info("Falling back to Playwright...")
      oil_data = get_oil_from_playwright()
      if oil_data:
        logger.info(
            f"Successfully fetched via Playwright ({len(oil_data)} items)"
        )
    except Exception as e:
      logger.error(f"Playwright fetch failed: {e}")

  if not oil_data:
    raise RuntimeError("ไม่พบรายการราคาน้ำมันจากทุกช่องทาง")

  output_file = "oil_price.json"
  with open(output_file, "w", encoding="utf-8") as f:
    json.dump(oil_data, f, ensure_ascii=False, indent=2)

  logger.info(f"Successfully saved {output_file}")


if __name__ == "__main__":
  scrape_oil_price()
