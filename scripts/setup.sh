#!/usr/bin/env bash
# ============================================================
# ミナ・エウレカ AI日記ブログ — ワンクリックセットアップ
#
# 使い方:
#   chmod +x scripts/setup.sh && ./scripts/setup.sh
#
# やること:
#   1. Gemini API キーの設定（GitHub Secrets に自動登録）
#   2. GitHub Pages の有効化
#   3. 初回記事生成のテスト
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════╗"
echo "║  ミナ・エウレカの思考日記 — セットアップ     ║"
echo "║  ひらめきを真剣に生きる                     ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# --- Step 1: gh CLI チェック ---
if ! command -v gh &> /dev/null; then
    echo -e "${RED}✗ GitHub CLI (gh) がインストールされていません${NC}"
    echo "  インストール: https://cli.github.com/"
    exit 1
fi
echo -e "${GREEN}✓ GitHub CLI detected${NC}"

# --- Step 2: ログイン確認 ---
if ! gh auth status &> /dev/null 2>&1; then
    echo -e "${YELLOW}→ GitHub にログインしてください${NC}"
    gh auth login
fi
echo -e "${GREEN}✓ GitHub authenticated${NC}"

# --- Step 3: リポジトリ確認 ---
REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null || echo "")
if [ -z "$REPO" ]; then
    echo -e "${RED}✗ GitHub リポジトリが見つかりません${NC}"
    echo "  先に 'gh repo create' でリポジトリを作成してください"
    exit 1
fi
echo -e "${GREEN}✓ Repository: ${REPO}${NC}"

# --- Step 4: Gemini API キー設定 ---
echo ""
echo -e "${CYAN}=== Gemini API キーの設定 ===${NC}"
echo ""
echo "Gemini API キーが必要です（無料）。"
echo -e "取得先: ${YELLOW}https://aistudio.google.com/apikey${NC}"
echo ""

# 既存のシークレットチェック
EXISTING=$(gh secret list 2>/dev/null | grep "GEMINI_API_KEY" || echo "")
if [ -n "$EXISTING" ]; then
    echo -e "${GREEN}✓ GEMINI_API_KEY は既に設定されています${NC}"
    read -p "上書きしますか？ (y/N): " OVERWRITE
    if [ "$OVERWRITE" != "y" ] && [ "$OVERWRITE" != "Y" ]; then
        echo "スキップします"
    else
        read -sp "Gemini API Key: " API_KEY
        echo ""
        echo "$API_KEY" | gh secret set GEMINI_API_KEY
        echo -e "${GREEN}✓ GEMINI_API_KEY を更新しました${NC}"
    fi
else
    read -sp "Gemini API Key: " API_KEY
    echo ""
    if [ -z "$API_KEY" ]; then
        echo -e "${RED}✗ API キーが空です${NC}"
        exit 1
    fi
    echo "$API_KEY" | gh secret set GEMINI_API_KEY
    echo -e "${GREEN}✓ GEMINI_API_KEY を設定しました${NC}"
fi

# --- Step 5: GitHub Pages 有効化 ---
echo ""
echo -e "${CYAN}=== GitHub Pages 設定 ===${NC}"
echo ""
echo -e "${YELLOW}→ GitHub Pages を有効化するには:${NC}"
echo "  1. ${REPO} の Settings → Pages に移動"
echo "  2. Source: 'GitHub Actions' を選択"
echo ""
echo -e "  URL: ${YELLOW}https://github.com/${REPO}/settings/pages${NC}"
echo ""

# --- Step 6: テスト実行 ---
echo -e "${CYAN}=== セットアップ完了 ===${NC}"
echo ""
echo "以下のコマンドで動作確認できます:"
echo ""
echo -e "  ${YELLOW}# ローカルで記事生成テスト${NC}"
echo "  export GEMINI_API_KEY='your-key'"
echo "  pip install -r requirements.txt"
echo "  python scripts/generate.py"
echo ""
echo -e "  ${YELLOW}# GitHub Actions を手動実行${NC}"
echo "  gh workflow run 'ミナ・エウレカ 日記自動生成'"
echo ""
echo -e "  ${YELLOW}# ワークフロー実行状況を確認${NC}"
echo "  gh run list --workflow=generate-diary.yml"
echo ""
echo -e "${GREEN}✓ セットアップ完了！2時間ごとに自動で日記が生成されます。${NC}"
