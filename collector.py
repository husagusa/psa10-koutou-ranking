
import csv
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
CARDS_CSV = ROOT / "cards.csv"
HISTORY_CSV = ROOT / "data" / "history.csv"
DATE_PRICE_RE = re.compile(r"(\d{4}/\d{2}/\d{2})\s*¥\s*([\d,]+)")

def parse_date_prices(section_text):
    dedup = {}
    for d, p in DATE_PRICE_RE.findall(section_text):
        try:
            dt = datetime.strptime(d, "%Y/%m/%d").date().isoformat()
            dedup[dt] = int(p.replace(",", ""))
        except ValueError:
            pass
    return sorted(dedup.items(), reverse=True)

def get_body_text(page):
    return page.locator("body").inner_text(timeout=10000)

def get_price_section_text(page):
    text = get_body_text(page)
    start_key = "日付ごとの相場を見る"
    end_key = "商品情報"
    start = text.find(start_key)
    if start < 0:
        raise RuntimeError("『日付ごとの相場を見る』が見つかりません")
    text = text[start + len(start_key):]
    end = text.find(end_key)
    if end >= 0:
        text = text[:end]
    return text

def get_sales_history_text(page):
    text = get_body_text(page)
    start = text.find("売買履歴")
    if start < 0:
        raise RuntimeError("『売買履歴』が見つかりません")
    return text[start:start + 4000]

def click_psa10_in_sales_filter(page):
    heading = page.get_by_text("売買履歴", exact=True)
    if heading.count() == 0:
        raise RuntimeError("『売買履歴』見出しが見つかりません")

    heading.first.scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    hb = heading.first.bounding_box()
    if not hb:
        raise RuntimeError("売買履歴の位置を取得できません")

    candidates = page.get_by_text("PSA10", exact=True)
    scored = []
    for i in range(candidates.count()):
        loc = candidates.nth(i)
        try:
            if not loc.is_visible():
                continue
            box = loc.bounding_box()
            if not box:
                continue
            dy = box["y"] - hb["y"]
            if 0 <= dy <= 500:
                scored.append((dy, loc))
        except Exception:
            pass

    if not scored:
        raise RuntimeError("売買履歴の状態フィルター内にPSA10が見つかりません")

    scored.sort(key=lambda x: x[0])
    scored[0][1].click(timeout=3000)
    page.wait_for_timeout(1800)

def verify_psa10_sales_rows(page):
    text = get_sales_history_text(page)
    marker = "枚数"
    pos = text.find(marker)
    if pos >= 0:
        text = text[pos + len(marker):]
    psa10_count = len(re.findall(r"\bPSA10\b", text[:2500]))
    if psa10_count < 1:
        raise RuntimeError("PSA10選択後の売買履歴にPSA10取引を確認できません")
    return psa10_count

def expand_date_price_section(page):
    expander = page.get_by_text("日付ごとの相場を見る", exact=True)
    if expander.count() == 0:
        raise RuntimeError("『日付ごとの相場を見る』が見つかりません")
    try:
        expander.first.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        expander.first.click(timeout=3000)
        page.wait_for_timeout(700)
    except Exception:
        pass

def scrape_one(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    try:
        name = page.locator("h1").first.inner_text(timeout=5000).strip()
    except Exception:
        name = url.rsplit("/", 1)[-1]

    click_psa10_in_sales_filter(page)
    verified = verify_psa10_sales_rows(page)
    expand_date_price_section(page)

    history = parse_date_prices(get_price_section_text(page))
    if not history:
        raise RuntimeError("PSA10の日付別相場を取得できません")
    return name, verified, history

def load_urls():
    with CARDS_CSV.open(newline="", encoding="utf-8-sig") as f:
        return [r["url"].strip() for r in csv.DictReader(f) if r.get("url", "").strip()]

def load_existing():
    rows = {}
    if HISTORY_CSV.exists():
        with HISTORY_CSV.open(newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                rows[(r["url"], r["source_date"])] = r
    return rows

def save_all(rows):
    HISTORY_CSV.parent.mkdir(exist_ok=True)
    fieldnames = ["url", "name", "source_date", "price", "collected_at"]
    ordered = sorted(rows.values(), key=lambda r: (r["name"], r["source_date"]))
    with HISTORY_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(ordered)

def main():
    urls = load_urls()
    rows = load_existing()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"{len(urls)}件を取得します")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="ja-JP", viewport={"width": 1280, "height": 1400})
        page = context.new_page()
        ok = 0

        for idx, url in enumerate(urls, 1):
            try:
                name, verified, history = scrape_one(page, url)
                for source_date, price in history:
                    rows[(url, source_date)] = {
                        "url": url,
                        "name": name,
                        "source_date": source_date,
                        "price": str(price),
                        "collected_at": now,
                    }
                preview = ", ".join(f"{d}=¥{v:,}" for d, v in history[:3])
                print(f"[{idx}/{len(urls)}] OK {name}")
                print(f"          PSA10表示確認={verified}件 / 保存候補={len(history)}日分 / {preview}")
                ok += 1
            except Exception as e:
                print(f"[{idx}/{len(urls)}] NG {url}")
                print(f"          {type(e).__name__}: {e}")
            time.sleep(4)

        context.close()
        browser.close()

    save_all(rows)

    if ok < max(1, len(urls) // 2):
        raise SystemExit(f"取得成功が少なすぎます: {ok}/{len(urls)}")

if __name__ == "__main__":
    main()
