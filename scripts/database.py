"""
JSON ファイルベースのデータベース
記事履歴、使用済み引用元、生成メタデータを管理する。
Supabase の代替として、Git リポジトリ内の JSON ファイルを使用。
"""

import json
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "article_history.json")
REFERENCES_FILE = os.path.join(DATA_DIR, "used_references.json")
METADATA_FILE = os.path.join(DATA_DIR, "generation_metadata.json")

MAX_ARTICLES = 100


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(filepath: str) -> list | dict:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_json(filepath: str, data) -> None:
    _ensure_data_dir()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# === 記事履歴 ===

def get_article_history() -> list[dict]:
    """全記事履歴を取得する。"""
    return _load_json(HISTORY_FILE)


def add_article_to_history(article: dict) -> None:
    """記事を履歴に追加する。"""
    history = get_article_history()
    article["generated_at"] = datetime.now(JST).isoformat()
    history.append(article)
    _save_json(HISTORY_FILE, history)


def get_recent_articles(n: int = 10) -> list[dict]:
    """直近N件の記事を取得する。"""
    history = get_article_history()
    return history[-n:]


def get_recent_topics(n: int = 20) -> list[str]:
    """直近N件の記事のトピックを取得する（重複テーマ回避用）。"""
    history = get_article_history()
    topics = []
    for article in history[-n:]:
        topics.append(article.get("title", ""))
        if article.get("topic"):
            topics.append(article["topic"])
    return topics


def get_recent_categories(n: int = 10) -> list[str]:
    """直近N件のカテゴリを取得する。"""
    history = get_article_history()
    return [a.get("category", "") for a in history[-n:] if a.get("category")]


# === 使用済み引用元 ===

def get_used_references() -> list[dict]:
    """使用済み引用元の一覧を取得する。"""
    return _load_json(REFERENCES_FILE)


def get_used_reference_ids() -> set[str]:
    """使用済み引用元のIDセットを取得する。"""
    refs = get_used_references()
    return {r.get("article_id", "") for r in refs}


def add_used_reference(article_id: str, article_title: str, article_url: str) -> None:
    """引用元を使用済みとして記録する。"""
    refs = get_used_references()
    refs.append({
        "article_id": article_id,
        "title": article_title,
        "url": article_url,
        "used_at": datetime.now(JST).isoformat(),
    })
    _save_json(REFERENCES_FILE, refs)


def get_unused_articles(available_articles: list[dict]) -> list[dict]:
    """まだ引用に使っていない記事を返す。すべて使用済みの場合はリセットして全記事を返す。"""
    used_ids = get_used_reference_ids()
    unused = [a for a in available_articles if a.get("id", "") not in used_ids]
    if not unused:
        # 全記事使用済みの場合、使用履歴をリセット
        _save_json(REFERENCES_FILE, [])
        return available_articles
    return unused


# === 生成メタデータ ===

def get_generation_metadata() -> dict:
    """生成メタデータを取得する。"""
    data = _load_json(METADATA_FILE)
    if isinstance(data, list):
        return {}
    return data


def update_generation_metadata(metadata: dict) -> None:
    """生成メタデータを更新する。"""
    current = get_generation_metadata()
    current.update(metadata)
    current["last_updated"] = datetime.now(JST).isoformat()
    _save_json(METADATA_FILE, current)


def get_generation_count() -> int:
    """総生成回数を取得する。"""
    meta = get_generation_metadata()
    return meta.get("total_generated", 0)


def increment_generation_count() -> int:
    """生成回数をインクリメントする。"""
    meta = get_generation_metadata()
    count = meta.get("total_generated", 0) + 1
    update_generation_metadata({"total_generated": count})
    return count


# === 記事数制限 ===

def enforce_article_limit() -> list[str]:
    """
    記事数が MAX_ARTICLES を超えている場合、古い記事を削除する。
    削除された記事のファイル名リストを返す。
    """
    history = get_article_history()
    deleted_files = []

    if len(history) <= MAX_ARTICLES:
        return deleted_files

    excess = len(history) - MAX_ARTICLES
    old_articles = history[:excess]
    remaining = history[excess:]

    for article in old_articles:
        filename = article.get("filename", "")
        if filename:
            filepath = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "_posts",
                filename,
            )
            if os.path.exists(filepath):
                os.remove(filepath)
                deleted_files.append(filename)
                print(f"[DB] Deleted old article: {filename}")

    _save_json(HISTORY_FILE, remaining)

    # 削除した記事の引用元も履歴から削除
    deleted_titles = {a.get("title", "") for a in old_articles}
    refs = get_used_references()
    refs = [r for r in refs if r.get("title", "") not in deleted_titles]
    _save_json(REFERENCES_FILE, refs)

    return deleted_files


# === 統計情報 ===

def get_stats() -> dict:
    """データベースの統計情報を取得する。"""
    history = get_article_history()
    refs = get_used_references()
    meta = get_generation_metadata()
    return {
        "total_articles": len(history),
        "used_references": len(refs),
        "total_generated": meta.get("total_generated", 0),
        "max_articles": MAX_ARTICLES,
    }
