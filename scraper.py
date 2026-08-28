import json
import logging
import pandas as pd
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def scrape_oil_price():
    url = "https://oil-price.bangchak.co.th/BcpOilPrice1/th"
    logger.info(f"Connecting to {url}...")
    oil_data = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            )

            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("table tr", timeout=30000)
            page.wait_for_timeout(2000)
            html_content = page.content()

            browser.close()

        soup = BeautifulSoup(html_content, "html.parser")
        rows = soup.find_all("tr")

        for row in rows:
            cols = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cols) >= 3:
                name = cols[0]
                today = cols[1]
                tomorrow = cols[2]

                # กรองส่วนหัวตารางและแถวว่าง
                if name and today and "ชนิดน้ำมัน" not in name:
                    oil_data.append({
                        "name": name,
                        "today": today,
                        "tomorrow": tomorrow
                    })

        if not oil_data:
            raise RuntimeError("ไม่พบตารางข้อมูลราคาน้ำมัน")

        output_file = "oil_price.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(oil_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Successfully saved {output_file} ({len(oil_data)} items)")

    except Exception as e:
        logger.error(f"Oil Scraper failed: {e}")
        raise e


if __name__ == "__main__":
    scrape_oil_price()
