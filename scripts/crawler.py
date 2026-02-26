"""
note.com/gensnotes クローラー
Genesis Vault の記事タイトル・テーマを取得し、日記生成のインスピレーション元として使用する。
"""

import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup

NOTE_BASE_URL = "https://note.com"
GENSNOTES_URL = "https://note.com/gensnotes"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CACHE_FILE = os.path.join(DATA_DIR, "crawled_articles.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MinaEurekaBlogBot/1.0; +https://github.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.5",
}


def fetch_note_api_articles(page: int = 1, per_page: int = 20) -> list[dict]:
    """note.com の API を使って記事一覧を取得する。"""
    api_url = f"https://note.com/api/v2/creators/gensnotes/contents?kind=note&page={page}&per_page={per_page}"
    try:
        resp = requests.get(api_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        articles = []
        for item in data.get("data", {}).get("contents", []):
            article = {
                "id": str(item.get("id", "")),
                "title": item.get("name", ""),
                "url": f"{NOTE_BASE_URL}/gensnotes/n/{item.get('key', '')}",
                "published_at": item.get("publishAt", ""),
                "like_count": item.get("likeCount", 0),
                "body_letters_count": item.get("bodyLettersCount", 0),
                "hashtags": [tag.get("hashtag", {}).get("name", "") for tag in item.get("hashtags", [])],
            }
            articles.append(article)
        return articles
    except Exception as e:
        print(f"[Crawler] API fetch failed: {e}")
        return []


def fetch_article_body(url: str) -> str:
    """個別記事ページから本文の概要を抽出する（無料部分のみ）。"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        body_el = soup.select_one("div.note-common-styles__textnote-body")
        if body_el:
            text = body_el.get_text(separator="\n", strip=True)
            return text[:500]
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            return og_desc["content"][:500]
        return ""
    except Exception as e:
        print(f"[Crawler] Body fetch failed for {url}: {e}")
        return ""


def crawl_gensnotes(max_pages: int = 3, fetch_bodies: bool = False) -> list[dict]:
    """Genesis Vault の記事を複数ページにわたってクロールする。"""
    all_articles = []
    for page in range(1, max_pages + 1):
        articles = fetch_note_api_articles(page=page)
        if not articles:
            break
        all_articles.extend(articles)
        time.sleep(1)

    if fetch_bodies:
        for article in all_articles[:10]:
            body = fetch_article_body(article["url"])
            article["body_preview"] = body
            time.sleep(1)

    return all_articles


def load_cached_articles() -> list[dict]:
    """キャッシュされた記事一覧を読み込む。"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_cached_articles(articles: list[dict]) -> None:
    """記事一覧をキャッシュファイルに保存する。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


def get_articles(force_refresh: bool = False) -> list[dict]:
    """
    記事一覧を取得する。キャッシュがある場合はキャッシュを使用。
    force_refresh=True の場合は再クロールする。
    """
    if not force_refresh:
        cached = load_cached_articles()
        if cached:
            return cached

    articles = crawl_gensnotes(max_pages=3, fetch_bodies=True)
    if articles:
        save_cached_articles(articles)
    return articles


if __name__ == "__main__":
    print("[Crawler] Fetching articles from Genesis Vault...")
    articles = get_articles(force_refresh=True)
    print(f"[Crawler] Found {len(articles)} articles")
    for a in articles[:5]:
        print(f"  - {a['title']} ({a['url']})")
