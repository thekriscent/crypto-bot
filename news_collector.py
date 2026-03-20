import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.error import URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from storage import initialize_database, insert_news_item


DEFAULT_DB_FILE = "trend_bot.db"
FEEDS = [
    {
        "source": "CoinDesk",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    },
    {
        "source": "Federal Reserve Press Releases",
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
    },
    {
        "source": "BLS Latest Releases",
        "url": "https://www.bls.gov/feed/bls_latest.rss",
    },
]


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def local_name(tag):
    return tag.split("}", 1)[-1]


def find_text(element, names):
    for child in element.iter():
        if local_name(child.tag) in names:
            text = child.text.strip() if child.text else ""
            if text:
                return unescape(text)
    return None


def normalize_published_at(value):
    if not value:
        return None

    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        dt = None

    if dt is None:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc).isoformat()


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    items = []

    for element in root.iter():
        tag = local_name(element.tag)
        if tag not in {"item", "entry"}:
            continue

        headline = find_text(element, {"title"})
        if not headline:
            continue

        url = find_text(element, {"link", "id"})
        if url is None:
            for child in element:
                if local_name(child.tag) == "link":
                    href = child.attrib.get("href")
                    if href:
                        url = href.strip()
                        break

        published_at = normalize_published_at(
            find_text(element, {"pubDate", "published", "updated", "date"})
        )

        items.append(
            {
                "headline": headline,
                "url": url,
                "published_at": published_at,
            }
        )

    return items


def fetch_feed(feed_url, timeout=20):
    request = Request(
        feed_url,
        headers={
            "User-Agent": "crypto-bot-news-collector/1.0",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def collect_news(db_filename):
    initialize_database(db_filename)

    processed = 0
    inserted = 0
    errors = []

    for feed in FEEDS:
        try:
            xml_bytes = fetch_feed(feed["url"])
            items = parse_feed(xml_bytes)
        except (URLError, ET.ParseError, TimeoutError, ValueError) as exc:
            errors.append((feed["source"], str(exc)))
            continue

        for item in items:
            was_inserted = insert_news_item(
                db_filename=db_filename,
                timestamp_utc=utc_now_iso(),
                published_at=item["published_at"],
                source=feed["source"],
                headline=item["headline"],
                url=item["url"],
            )
            processed += 1
            if was_inserted:
                inserted += 1

    return processed, inserted, errors


def main():
    parser = argparse.ArgumentParser(description="Collect crypto and macro news from RSS into SQLite.")
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_FILE,
        help="Path to the SQLite database file (default: trend_bot.db)",
    )
    args = parser.parse_args()

    processed, inserted, errors = collect_news(args.db)
    print(f"Database: {args.db}")
    print(f"Feeds configured: {len(FEEDS)}")
    print(f"Items processed: {processed}")
    print(f"Items inserted: {inserted}")

    if errors:
        print("Feed errors:")
        for source, error in errors:
            print(f"- {source}: {error}")


if __name__ == "__main__":
    main()
