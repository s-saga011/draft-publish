# Draft CLI

Publish paid articles from your terminal. Like git push.

ターミナルから有料記事を公開。git push のように。

## Install

```bash
pipx install git+https://github.com/s-saga011/draft-publish.git
```

> No pipx? `brew install pipx` (Mac) / `apt install pipx` (Linux) / `pip install pipx` (Windows WSL)

## Setup

```bash
# Set server and language (first time only)
draft remote https://draft-publish.com --lang en  # or --lang ja

# Register your SSH public key at the web UI
# → https://draft-publish.com/settings
```

## Usage

```bash
# Create a new article
draft new "My Article" --price 500 --tags "investing,AI"

# Edit the article
cd ~/drafts/my-article-xxxxxx/
cursor article.md

# Push (SSH auth + auto image upload)
draft push

# Publish (draft → published)
draft publish
```

## Push a folder

```bash
# Push markdown + images together
draft push ./my-article/ --price 500
# → Images auto-detected, uploaded, and linked
```

## Frontmatter

```markdown
---
title: "My Article"
price: 500
tags: [investing, AI]
---

# Article Title

Content here...

<!-- paywall -->

Paid content here...
```

## Commands

| Command | Description |
|---------|-------------|
| `draft remote <url> --lang en` | Set server URL and language |
| `draft new "title"` | Create article branch |
| `draft push [path]` | Push article (SSH auth) |
| `draft publish` | Draft → Published |
| `draft checkout <slug>` | Download existing article |
| `draft status` | List local branches |
| `draft log` | Revision history |
| `draft list` | List server articles |
| `draft lang en/ja` | Switch language |

## Auth

SSH public key (GitHub style). No passwords or API keys stored locally.

SSH公開鍵認証（GitHub方式）。パスワードやAPIキーの保存は不要。

## Links

- Web: https://draft-publish.com
- CLI Guide: https://draft-publish.com/cli
