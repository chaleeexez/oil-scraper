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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def get_from_bangchak_api():
  url = "https://oil-price.bangchak.co.th/ApiOilPrice2/th"
  res = requests.get(url, headers=HEADERS, timeout=10)
  logger.info(f"Bangchak API status={res.status_code}, len={len(res.text)}")
  if res.status_code != 200:
    logger.warning(f"Bangchak API non-200 body preview: {res.text[:300]!r}")
    return []
  if res.status_code == 200:
    data = res.json()
    items = []
    if isinstance(data, list):
      for entry in data:
        if isinstance(entry, dict) and "OilList" in entry:
          oil_list_raw = entry.get("OilList")
          if isinstance(oil_list_raw, str):
            try:
              items.extend(json.loads(oil_list_raw))
            except json.JSONDecodeError:
              logger.warning("Failed to parse OilList JSON string")
          elif isinstance(oil_list_raw, list):
            items.extend(oil_list_raw)
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
    if not oil_data:
      logger.warning(f"Bangchak API returned 200 but parsed 0 items. Raw items count: {len(items)}. Sample: {items[:2]}")
    return oil_data
  return []


def get_from_open_api():
  url = "https://api.chnwt.dev/thai-oil-api/latest"
  res = requests.get(url, headers=HEADERS, timeout=10)
  logger.info(f"Open API status={res.status_code}, len={len(res.text)}")
  if res.status_code != 200:
    logger.warning(f"Open API non-200 body preview: {res.text[:300]!r}")
    return []
  if res.status_code == 200:
    data = res.json()
    bcp_data = (
        data.get("response", {}).get("stations", {}).get("bcp", {})
    )
    oil_data = []
    for key, val in bcp_data.items():
      if isinstance(val, dict):
        name = str(val.get("name", "")).strip()
        today = str(val.get("price", "")).strip()
        tomorrow = (
            str(val.get("tomorrow", "")).strip()
            if val.get("tomorrow") is not None
            else ""
        )
        if name and today and re.search(r"\d", today):
          oil_data.append({"name": name, "today": today, "tomorrow": tomorrow})
    if not oil_data:
      logger.warning(f"Open API returned 200 but parsed 0 items. Raw stations: {list(bcp_data.keys())[:5]}")
    return oil_data
  return []


def get_from_playwright():
  url = "https://oil-price.bangchak.co.th/BcpOilPrice1/th"
  oil_data = []
  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(user_agent=HEADERS["User-Agent"])
    response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
    logger.info(f"Playwright page status={response.status if response else 'None'}")
    page.wait_for_timeout(4000)
    html_content = page.content()
    logger.info(f"Playwright page content length={len(html_content)}")
    browser.close()

  soup = BeautifulSoup(html_content, "html.parser")
  rows = soup.find_all("tr")
  logger.info(f"Playwright found {len(rows)} <tr> rows")
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

  # ช่องทางที่ 1: Official Bangchak API
  try:
    oil_data = get_from_bangchak_api()
    if oil_data:
      logger.info(
          f"Successfully fetched via Bangchak API ({len(oil_data)} items)"
      )
  except Exception as e:
    logger.warning(f"Bangchak API failed: {e}", exc_info=True)

  # ช่องทางที่ 2: Public Thai Oil Open API (สำรอง)
  if not oil_data:
    try:
      logger.info("Trying Open Thai Oil API fallback...")
      oil_data = get_from_open_api()
      if oil_data:
        logger.info(
            f"Successfully fetched via Open API ({len(oil_data)} items)"
        )
    except Exception as e:
      logger.warning(f"Open API fallback failed: {e}", exc_info=True)

  # ช่องทางที่ 3: Playwright Web Scraping (สำรองสุดท้าย)
  if not oil_data:
    try:
      logger.info("Trying Playwright Web Scraping fallback...")
      oil_data = get_from_playwright()
      if oil_data:
        logger.info(
            f"Successfully fetched via Playwright ({len(oil_data)} items)"
        )
    except Exception as e:
      logger.error(f"Playwright fallback failed: {e}", exc_info=True)

  if not oil_data:
    raise RuntimeError("ไม่พบรายการราคาน้ำมันจากทุกช่องทาง")

  output_file = "oil_price.json"
  with open(output_file, "w", encoding="utf-8") as f:
    json.dump(oil_data, f, ensure_ascii=False, indent=2)

  logger.info(f"Successfully saved {output_file}")


if __name__ == "__main__":
  scrape_oil_price()
