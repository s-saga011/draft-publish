# Draft CLI

ターミナルから有料記事を公開。git push のように。

## インストール（ワンライン）

```bash
pipx install git+https://github.com/s-saga011/draft-publish.git
```

> [pipx](https://pipx.pypa.io/) がない場合: `brew install pipx` (Mac) / `apt install pipx` (Linux) / `pip install pipx` (その他)

## セットアップ

```bash
# サーバー設定（初回のみ）
draft remote https://draft-publish.com

# SSH公開鍵をWeb UIの設定画面から登録
# → https://draft-publish.com/login
```

## 使い方

```bash
# 新規記事を作成
draft new "記事タイトル" --price 500 --tags "投資,AI"

# 記事を編集
cd ~/drafts/記事タイトル-xxxxxx/
cursor article.md

# push（SSH鍵で自動認証、画像も自動アップロード）
draft push

# 公開
draft publish
```

## フォルダごとpush

```bash
# Markdownと画像をフォルダにまとめてpush
draft push ./my-article/ --price 500
# → 画像は自動検出・アップロード・リンク書き換え
```

## Frontmatter

```markdown
---
title: "記事タイトル"
price: 1000
tags: [投資, AI, 暴落]
---

# 記事タイトル

ここに本文...

<!-- paywall -->

ここから有料部分...
```

## コマンド一覧

| コマンド | 説明 |
|---------|------|
| `draft remote <url>` | サーバーURLを設定 |
| `draft new "タイトル"` | 新規記事ブランチを作成 |
| `draft push [path]` | 記事をpush |
| `draft publish` | 下書き → 公開 |
| `draft checkout <slug>` | 既存記事をダウンロード |
| `draft status` | ローカルの記事一覧 |
| `draft log` | リビジョン履歴 |
| `draft list` | サーバーの記事一覧 |

## 認証

SSH公開鍵認証（GitHub方式）。パスワードやAPIキーの保存は不要。

## リンク

- Web: https://draft-publish.com
- CLI詳細: https://draft-publish.com/cli
