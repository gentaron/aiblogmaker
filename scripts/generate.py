#!/usr/bin/env python3
"""
メイン生成パイプライン
クローラー → CEO Agent → SEO Agent → Writer Agent → Editor Agent → 記事出力

このスクリプトは GitHub Actions から2時間ごとに実行される。
"""

import json
import os
import random
import re
import sys
from datetime import datetime, timezone, timedelta

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawler import get_articles
from database import (
    get_article_history,
    add_article_to_history,
    get_recent_topics,
    get_recent_categories,
    get_unused_articles,
    add_used_reference,
    increment_generation_count,
    enforce_article_limit,
    get_stats,
)
from agents import (
    ceo_agent,
    seo_agent,
    writer_agent,
    editor_agent,
    persona_guard,
    classify_category,
)

JST = timezone(timedelta(hours=9))
POSTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_posts")


def select_reference_article() -> dict:
    """インスピレーション元の記事を選択する（未使用のものを優先）。"""
    print("[Pipeline] Fetching articles from note.com/gensnotes...")
    all_articles = get_articles(force_refresh=True)

    if not all_articles:
        print("[Pipeline] No articles found. Using fallback topic.")
        return {
            "id": "fallback",
            "title": "日常のひらめき",
            "hashtags": ["日常", "思考", "ひらめき"],
            "body_preview": "今日ふと気づいたことを書いてみる。",
            "url": "",
        }

    unused = get_unused_articles(all_articles)
    print(f"[Pipeline] {len(unused)} unused articles available out of {len(all_articles)} total")

    # ランダムに選択（多様性のため）
    selected = random.choice(unused)
    print(f"[Pipeline] Selected reference: {selected['title']}")
    return selected


def generate_filename(date: datetime, slug: str) -> str:
    """Jekyll用のファイル名を生成する。"""
    date_str = date.strftime("%Y-%m-%d")
    # slugをサニタイズ
    slug = re.sub(r'[^a-z0-9\-]', '', slug.lower().replace(' ', '-'))
    slug = re.sub(r'-+', '-', slug).strip('-')
    if not slug:
        slug = f"diary-{date.strftime('%H%M')}"
    return f"{date_str}-{slug}.md"


def generate_front_matter(seo_data: dict, topic_plan: dict, reference: dict, date: datetime) -> str:
    """Jekyll Front Matter を生成する。"""
    title = seo_data.get("title", "無題の日記")
    tags = seo_data.get("tags", [])
    keywords = seo_data.get("keywords", "")
    meta_desc = seo_data.get("meta_description", "")
    category = topic_plan.get("category", "日常のひらめき")

    # YAML用にエスケープ
    title_escaped = title.replace('"', '\\"')
    meta_escaped = meta_desc.replace('"', '\\"')

    tags_yaml = "\n".join(f'  - "{tag}"' for tag in tags)

    front_matter = f"""---
layout: post
title: "{title_escaped}"
date: {date.strftime('%Y-%m-%d %H:%M:%S +0900')}
category: "{category}"
tags:
{tags_yaml}
keywords: "{keywords}"
meta_description: "{meta_escaped}"
reference_title: "{reference.get('title', '').replace('"', '\\"')}"
reference_url: "{reference.get('url', '')}"
author: "ミナ・エウレカ"
---
"""
    return front_matter


def run_pipeline():
    """メイン生成パイプラインを実行する。"""
    print("=" * 60)
    print("[Pipeline] ミナ・エウレカの思考日記 — 記事生成開始")
    print("=" * 60)

    # 統計表示
    stats = get_stats()
    print(f"[Pipeline] Current stats: {json.dumps(stats, ensure_ascii=False)}")

    # Step 1: インスピレーション元の記事を選択
    print("\n[Step 1] Selecting reference article...")
    reference = select_reference_article()

    # Step 2: CEO Agent — テーマ決定
    print("\n[Step 2] CEO Agent — Deciding topic and angle...")
    recent_topics = get_recent_topics(n=20)
    recent_categories = get_recent_categories(n=10)

    topic_plan = ceo_agent(reference, recent_topics, recent_categories)
    if not topic_plan or not topic_plan.get("topic"):
        print("[Pipeline] CEO Agent failed. Using fallback.")
        topic_plan = {
            "topic": f"{reference.get('title', '今日の発見')}について考えた",
            "angle": "日常の気づきから掘り下げる",
            "category": "日常のひらめき",
            "mood": "内省的",
            "key_question": "なぜこれが気になったのだろう？",
        }
    print(f"[Pipeline] Topic: {topic_plan.get('topic', '?')}")
    print(f"[Pipeline] Angle: {topic_plan.get('angle', '?')}")
    print(f"[Pipeline] Category: {topic_plan.get('category', '?')}")

    # Step 3: SEO Agent — メタ情報生成
    print("\n[Step 3] SEO Agent — Generating SEO metadata...")
    seo_data = seo_agent(topic_plan)
    if not seo_data or not seo_data.get("title"):
        print("[Pipeline] SEO Agent failed. Using fallback.")
        seo_data = {
            "title": topic_plan.get("topic", "今日の思考メモ"),
            "tags": ["日記", "ミナ・エウレカ", topic_plan.get("category", "思考")],
            "keywords": "ミナ・エウレカ, 日記, " + topic_plan.get("category", ""),
            "meta_description": topic_plan.get("topic", "ミナ・エウレカの日記"),
            "slug": "diary-entry",
        }
    print(f"[Pipeline] Title: {seo_data.get('title', '?')}")

    # Step 4: Writer Agent — 本文執筆
    print("\n[Step 4] Writer Agent — Writing diary entry...")
    draft = writer_agent(topic_plan, seo_data)
    if not draft or len(draft) < 200:
        print("[Pipeline] Writer Agent produced insufficient content. Aborting.")
        sys.exit(1)
    print(f"[Pipeline] Draft length: {len(draft)} characters")

    # Step 4.5: Persona Guard — ペルソナチェック
    print("\n[Step 4.5] Persona Guard — Checking persona consistency...")
    persona_ok = persona_guard(draft)
    if not persona_ok:
        print("[Pipeline] Warning: Persona check did not fully pass. Proceeding with Editor review.")

    # Step 5: Editor Agent — 校正・品質チェック
    print("\n[Step 5] Editor Agent — Editing and quality check...")
    edit_result = editor_agent(draft, topic_plan, seo_data)

    if edit_result and edit_result.get("edited_body"):
        final_body = edit_result["edited_body"]
        quality = edit_result.get("quality_score", "N/A")
        feedback = edit_result.get("feedback", "")
        persona_check = edit_result.get("persona_check", "")
        print(f"[Pipeline] Quality score: {quality}")
        print(f"[Pipeline] Feedback: {feedback}")
        print(f"[Pipeline] Persona check: {persona_check}")
    else:
        print("[Pipeline] Editor Agent returned no edits. Using original draft.")
        final_body = draft

    # Step 5.5: Category Classifier — カテゴリ補正
    title = seo_data.get("title", "")
    classified_cat = classify_category(title, final_body)
    if classified_cat != topic_plan.get("category"):
        print(f"[Pipeline] Category adjusted: {topic_plan.get('category')} → {classified_cat}")
        topic_plan["category"] = classified_cat

    # Step 6: 記事ファイルを生成
    print("\n[Step 6] Generating post file...")
    now = datetime.now(JST)
    slug = seo_data.get("slug", "diary")
    filename = generate_filename(now, slug)

    front_matter = generate_front_matter(seo_data, topic_plan, reference, now)
    full_content = front_matter + "\n" + final_body

    os.makedirs(POSTS_DIR, exist_ok=True)
    filepath = os.path.join(POSTS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(full_content)
    print(f"[Pipeline] Post saved: {filepath}")

    # Step 7: データベース更新
    print("\n[Step 7] Updating database...")
    article_record = {
        "title": seo_data.get("title", ""),
        "topic": topic_plan.get("topic", ""),
        "category": topic_plan.get("category", ""),
        "tags": seo_data.get("tags", []),
        "filename": filename,
        "reference_id": reference.get("id", ""),
        "reference_title": reference.get("title", ""),
        "quality_score": edit_result.get("quality_score") if edit_result else None,
    }
    add_article_to_history(article_record)

    # 引用元を使用済みとして記録
    add_used_reference(
        reference.get("id", ""),
        reference.get("title", ""),
        reference.get("url", ""),
    )

    # 生成カウントをインクリメント
    count = increment_generation_count()
    print(f"[Pipeline] Total articles generated: {count}")

    # Step 8: 記事数制限の適用
    print("\n[Step 8] Enforcing article limit...")
    deleted = enforce_article_limit()
    if deleted:
        print(f"[Pipeline] Deleted {len(deleted)} old articles: {deleted}")
    else:
        print("[Pipeline] No articles need to be deleted.")

    # 完了
    print("\n" + "=" * 60)
    print("[Pipeline] Article generation complete!")
    print(f"[Pipeline] File: {filename}")
    print(f"[Pipeline] Title: {seo_data.get('title', '?')}")
    print("=" * 60)

    return filename


if __name__ == "__main__":
    filename = run_pipeline()
    print(f"\nOutput: {filename}")
