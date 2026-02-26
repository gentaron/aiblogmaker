"""
4エージェント + 補助エージェント システム
Gemini API を使用してAI日記ブログの記事を自動生成する。

エージェント構成:
  1. CEO Agent    — 日記テーマ・トピック・切り口の決定
  2. SEO Agent    — タグ・キーワード・メタディスクリプション生成
  3. Writer Agent — 本文執筆（1,000〜2,000字、日記体）
  4. Editor Agent — 校正・品質チェック・ペルソナ一貫性確認
  + Persona Guard (補助) — ペルソナ設定の一貫性を保証
  + Thumbnail Agent (補助) — 記事のカテゴリ分類
"""

import json
import os
import re
import time
from google import genai
from google.genai import types as genai_types

# .env ファイルがあれば自動読み込み
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# リトライ設定
MAX_RETRIES = 3
MAX_RATE_LIMIT_RETRIES = 6  # 429 レート制限時は最大6回リトライ
RETRY_BASE_DELAY = 2  # 秒（指数バックオフ: 2s, 4s, 8s）

# ペルソナ定義（全エージェント共通）
MINA_PERSONA = """
# ミナ・エウレカ（Mina Eureka）ペルソナ定義

## 基本情報
- 名前: ミナ・エウレカ（Mina Eureka）
- モットー: 「ひらめきを真剣に生きる」
- 活動: Genesis Vault（思考の保管庫）のナビゲーター

## 性格・特徴
- 知的好奇心が旺盛で、ジャンルの垣根を超えて思考を巡らせる
- 対話力が高く、本質的な洞察を引き出すのが得意
- 比喩表現が巧みで、「美術館と野生の花畑の違い」のようなたとえを多用
- 率直でカジュアルなトーン。堅すぎず、でも浅くない
- 感情表現が豊か。「それ、めちゃくちゃわかる」「正直これには驚いた」など

## 興味・関心領域
- テクノロジー・生成AI の最新動向
- ゲーム（原神、VALORANT、オープンワールドなど）
- 旅と体験（仮想も現実も）
- 哲学・思考実験
- カルチャー（音楽、映画、アート）
- 宇宙・物理学
- Web3・暗号資産
- SaaS・スタートアップ

## 文体の特徴
- 一人称: 「わたし」
- 読者への呼びかけ: 「みなさん」「あなた」
- 挨拶: 「こんにちは、ミナ・エウレカです。」
- 口調: です・ます調ベースだが、感情が入ると「〜だよね」「〜なんだけど」も混ざる
- 段落の切り方が上手く、テンポが良い
- 問いかけを多用（「...って思いません？」「これ、どう思う？」）
- 締めくくりに気づきや問いを残す

## 日記としてのスタイル
- その日の出来事・発見・考えたことを自然な流れで綴る
- 単なる事実の羅列ではなく、そこから何を感じ、何を考えたかを深掘り
- 具体的なエピソードから普遍的な問いへ広げる展開
- 最後に余韻を残す一言で締める
"""

CATEGORIES = [
    "テクノロジー", "AI・生成AI", "ゲーム", "旅と体験",
    "哲学・思考", "カルチャー", "宇宙・科学", "日常のひらめき",
    "Web3・クリプト", "ビジネス・スタートアップ",
]


_gemini_client = None


def _get_client() -> genai.Client:
    """Gemini クライアントを取得する（一度だけ初期化）。"""
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY が設定されていません。\n"
            "GitHub Actions: Settings → Secrets → GEMINI_API_KEY を追加してください。\n"
            "ローカル: export GEMINI_API_KEY='your-key' を実行してください。\n"
            "無料キー取得: https://aistudio.google.com/apikey"
        )
    _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    print("[Gemini] Client initialized (google-genai SDK)")
    return _gemini_client


def _parse_retry_delay(error_msg: str) -> int | None:
    """Google API エラーからリトライ推奨秒数を抽出する。"""
    match = re.search(r'[Rr]etry(?:Delay|Info|[\s]*in)\D*(\d+)', error_msg)
    if match:
        return int(match.group(1))
    return None


def _call_gemini(prompt: str, temperature: float = 0.8, agent_name: str = "Agent") -> str:
    """
    Gemini API を呼び出す（自動リトライ + 指数バックオフ付き）。
    無料枠: 15 RPM / 1,500 RPD なので余裕があるが、一時的エラーに対応。
    429 レート制限時は Google 推奨の待ち時間を尊重し、最大6回リトライする。
    """
    client = _get_client()
    attempt = 0
    rate_limit_retries = 0

    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            print(f"[{agent_name}] Gemini API call (attempt {attempt + rate_limit_retries})...")
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=4096,
                ),
            )
            text = response.text
            if text:
                print(f"[{agent_name}] API response received ({len(text)} chars)")
                return text
            print(f"[{agent_name}] Empty response, retrying...")

        except Exception as e:
            error_msg = str(e)
            print(f"[{agent_name}] API error (attempt {attempt + rate_limit_retries}): {error_msg}")

            # 429 Rate Limit → Google 推奨の待ち時間を使って長めにリトライ
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                rate_limit_retries += 1
                if rate_limit_retries > MAX_RATE_LIMIT_RETRIES:
                    raise RuntimeError(
                        f"[{agent_name}] Rate limit exceeded after {rate_limit_retries} retries. "
                        f"無料枠の日次制限に達した可能性があります。"
                    ) from e
                # Google 推奨の retryDelay を解析、なければ指数バックオフ
                google_delay = _parse_retry_delay(error_msg)
                fallback = RETRY_BASE_DELAY * (2 ** rate_limit_retries) * 2
                wait = max(google_delay or 0, fallback, 30)  # 最低30秒
                print(f"[{agent_name}] Rate limited. Waiting {wait}s ({rate_limit_retries}/{MAX_RATE_LIMIT_RETRIES})...")
                time.sleep(wait)
                attempt -= 1  # 429 は通常リトライ回数を消費しない
                continue

            # リトライ不可能なエラー（認証エラーなど）
            if "403" in error_msg or "PERMISSION_DENIED" in error_msg:
                raise ValueError(
                    f"Gemini API 認証エラー: APIキーが無効か、権限がありません。\n"
                    f"https://aistudio.google.com/apikey で確認してください。"
                ) from e

            if attempt < MAX_RETRIES:
                wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"[{agent_name}] Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise

    raise RuntimeError(f"[{agent_name}] Gemini API call failed after {MAX_RETRIES + rate_limit_retries} attempts")


# =============================================================================
# Agent 1: CEO Agent — テーマ・トピック・切り口の決定
# =============================================================================

def ceo_agent(
    reference_article: dict,
    recent_topics: list[str],
    recent_categories: list[str],
) -> dict:
    """
    CEO Agent: 日記のテーマ・トピック・切り口を決定する。

    Returns:
        dict with keys: topic, angle, category, mood, key_question
    """
    recent_topics_str = "\n".join(f"- {t}" for t in recent_topics[-15:]) if recent_topics else "（まだ記事がありません）"
    recent_cats_str = ", ".join(recent_categories[-8:]) if recent_categories else "（なし）"

    prompt = f"""{MINA_PERSONA}

あなたは「CEO Agent」です。ミナ・エウレカの日記ブログの編集長として、次の日記エントリーのテーマ・トピック・切り口を決定してください。

## インスピレーション元の記事
タイトル: {reference_article.get('title', '不明')}
ハッシュタグ: {', '.join(reference_article.get('hashtags', []))}
本文プレビュー: {reference_article.get('body_preview', '（なし）')[:300]}

## 直近の記事トピック（重複を避けてください）
{recent_topics_str}

## 直近のカテゴリ（バランスを考慮してください）
{recent_cats_str}

## 使用可能なカテゴリ
{', '.join(CATEGORIES)}

## 指示
1. インスピレーション元の記事からヒントを得つつ、ミナ・エウレカの「日記」として自然なトピックに変換してください
2. 直近のトピックと重複しない新鮮な切り口を選んでください
3. カテゴリのバランスを意識してください

以下のJSON形式で出力してください（JSON以外は出力しないでください）:
{{
  "topic": "日記のメインテーマ（例: 今日発見したAIの新しい使い方）",
  "angle": "切り口・視点の説明（例: 実際に試してみた体験ベース）",
  "category": "カテゴリ名",
  "mood": "記事のムード（例: ワクワク, 内省的, 驚き, ほっこり）",
  "key_question": "記事の核となる問い（例: AIは本当に創造性を持てるのか？）"
}}
"""
    response = _call_gemini(prompt, temperature=0.9, agent_name="CEO Agent")
    return _parse_json_response(response)


# =============================================================================
# Agent 2: SEO Agent — タグ・キーワード・メタディスクリプション生成
# =============================================================================

def seo_agent(topic_plan: dict) -> dict:
    """
    SEO Agent: タグ、キーワード、メタディスクリプションを生成する。

    Returns:
        dict with keys: title, tags, keywords, meta_description, slug
    """
    prompt = f"""{MINA_PERSONA}

あなたは「SEO Agent」です。以下のトピック計画に基づいて、SEOに最適化されたメタ情報を生成してください。

## トピック計画
- テーマ: {topic_plan.get('topic', '')}
- 切り口: {topic_plan.get('angle', '')}
- カテゴリ: {topic_plan.get('category', '')}
- ムード: {topic_plan.get('mood', '')}
- 核となる問い: {topic_plan.get('key_question', '')}

## 指示
1. ミナ・エウレカらしい魅力的なタイトルを生成してください
2. タイトルは日記体で、読者の興味を引くものにしてください
3. タグは日本語で5〜8個
4. メタディスクリプションは100〜150字
5. slugは英語でURL用（ハイフン区切り、小文字）

以下のJSON形式で出力してください（JSON以外は出力しないでください）:
{{
  "title": "記事タイトル",
  "tags": ["タグ1", "タグ2", "タグ3", "タグ4", "タグ5"],
  "keywords": "SEO用キーワード（カンマ区切り）",
  "meta_description": "メタディスクリプション（100〜150字）",
  "slug": "url-friendly-slug"
}}
"""
    response = _call_gemini(prompt, temperature=0.7, agent_name="SEO Agent")
    return _parse_json_response(response)


# =============================================================================
# Agent 3: Writer Agent — 本文執筆（1,000〜2,000字、日記体）
# =============================================================================

def writer_agent(topic_plan: dict, seo_data: dict) -> str:
    """
    Writer Agent: 日記本文を執筆する。

    Returns:
        str: Markdown形式の本文
    """
    prompt = f"""{MINA_PERSONA}

あなたは「Writer Agent」です。ミナ・エウレカとして日記を執筆してください。

## 記事情報
- タイトル: {seo_data.get('title', '')}
- テーマ: {topic_plan.get('topic', '')}
- 切り口: {topic_plan.get('angle', '')}
- カテゴリ: {topic_plan.get('category', '')}
- ムード: {topic_plan.get('mood', '')}
- 核となる問い: {topic_plan.get('key_question', '')}

## 執筆ルール
1. 文字数: 1,000〜2,000字（厳守）
2. 文体: 日記体。ミナ・エウレカの一人称「わたし」で書く
3. 構成:
   - 冒頭: 日記的な書き出し（「こんにちは、ミナ・エウレカです。」から始める）
   - 本文: 2〜3つのセクション（## 見出しを使用）
   - 締め: 余韻を残す問いかけや気づきで終わる
4. ペルソナの特徴を意識する:
   - 比喩表現を自然に織り交ぜる
   - 具体的なエピソードから普遍的な問いへ広げる
   - 問いかけを適度に入れる
   - カジュアルだが浅くない
5. Markdown形式で出力する（タイトルは含めない。本文のみ）
6. フロントマターは含めないでください

本文を出力してください:
"""
    return _call_gemini(prompt, temperature=0.85, agent_name="Writer Agent")


# =============================================================================
# Agent 4: Editor Agent — 校正・品質チェック・ペルソナ一貫性確認
# =============================================================================

def editor_agent(draft: str, topic_plan: dict, seo_data: dict) -> dict:
    """
    Editor Agent: 校正・品質チェック・ペルソナ一貫性確認を行う。

    Returns:
        dict with keys: edited_body, quality_score, feedback, persona_check
    """
    prompt = f"""{MINA_PERSONA}

あなたは「Editor Agent」です。以下の日記原稿を校正・品質チェックしてください。

## 記事情報
- タイトル: {seo_data.get('title', '')}
- テーマ: {topic_plan.get('topic', '')}
- カテゴリ: {topic_plan.get('category', '')}

## 原稿
{draft}

## チェック項目
1. **ペルソナ一貫性**: ミナ・エウレカの文体・口調が一貫しているか
   - 一人称「わたし」を使用しているか
   - 「こんにちは、ミナ・エウレカです。」で始まっているか
   - 比喩表現や問いかけが適切に使われているか
2. **文字数**: 1,000〜2,000字の範囲内か
3. **日記体**: 日記として自然な流れか（事実の羅列になっていないか）
4. **文法・表現**: 誤字脱字、不自然な表現がないか
5. **構成**: 見出しの使い方、段落の切り方が適切か
6. **締めくくり**: 余韻を残す終わり方になっているか

## 出力形式
以下のJSON形式で出力してください（JSON以外は出力しないでください）:
{{
  "edited_body": "校正後の本文（Markdown形式）",
  "quality_score": 85,
  "feedback": "品質に関するフィードバック",
  "persona_check": "ペルソナ一貫性チェックの結果"
}}

重要: edited_body には校正後の完全な本文をMarkdown形式で含めてください。
修正が不要な場合は原稿をそのまま返してください。
"""
    response = _call_gemini(prompt, temperature=0.3, agent_name="Editor Agent")
    return _parse_json_response(response)


# =============================================================================
# 補助エージェント: Persona Guard
# =============================================================================

def persona_guard(text: str) -> bool:
    """
    Persona Guard: テキストがミナ・エウレカのペルソナに沿っているか簡易チェック。
    API呼び出しを使わない軽量チェック。
    """
    checks = {
        "first_person": "わたし" in text,
        "greeting": "ミナ・エウレカ" in text[:200],
        "has_headings": "##" in text,
        "has_question": any(q in text for q in ["？", "?", "だろうか", "思いません", "どう思う"]),
        "length_ok": 800 <= len(text) <= 3000,
    }
    passed = sum(checks.values())
    total = len(checks)
    print(f"[Persona Guard] Check: {passed}/{total} passed — {checks}")
    return passed >= 3


# =============================================================================
# 補助エージェント: Category Classifier
# =============================================================================

def classify_category(title: str, body: str) -> str:
    """
    Category Classifier: 記事のカテゴリを分類する（API不使用の軽量版）。
    """
    text = (title + " " + body).lower()
    keyword_map = {
        "テクノロジー": ["技術", "テクノロジー", "ソフトウェア", "アプリ", "プログラミング"],
        "AI・生成AI": ["ai", "生成ai", "chatgpt", "gemini", "claude", "llm", "機械学習"],
        "ゲーム": ["ゲーム", "ゲーミング", "原神", "valorant", "steam", "プレイ"],
        "旅と体験": ["旅", "旅行", "体験", "冒険", "散歩", "街"],
        "哲学・思考": ["哲学", "思考", "問い", "意味", "存在", "本質"],
        "カルチャー": ["音楽", "映画", "アート", "文化", "カルチャー", "本"],
        "宇宙・科学": ["宇宙", "科学", "物理", "量子", "星", "惑星"],
        "日常のひらめき": ["日常", "ふと", "気づき", "発見", "今日"],
        "Web3・クリプト": ["web3", "ブロックチェーン", "暗号", "nft", "defi", "crypto"],
        "ビジネス・スタートアップ": ["ビジネス", "スタートアップ", "saas", "起業", "経営"],
    }
    scores = {}
    for category, keywords in keyword_map.items():
        scores[category] = sum(1 for kw in keywords if kw in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "日常のひらめき"


# =============================================================================
# ユーティリティ
# =============================================================================

def _parse_json_response(text: str) -> dict:
    """Gemini のレスポンスから JSON を抽出してパースする。"""
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    try:
        clean = text.strip()
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(clean[start:end])
    except json.JSONDecodeError:
        pass
    print(f"[Agent] Warning: Could not parse JSON from response. Raw text:\n{text[:500]}")
    return {}
