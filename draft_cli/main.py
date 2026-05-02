"""Draft CLI - git branch style article publishing."""
import typer
import httpx
import base64
import hashlib
import json
from pathlib import Path
from typing import Optional

app = typer.Typer(name="draft", help="Draft CLI - 1記事1ブランチで有料記事を管理", no_args_is_help=True)

CONFIG_PATH = Path.home() / ".draft" / "config.json"
DRAFTS_DIR = Path.home() / "drafts"

CLI_MESSAGES = {
    "ja": {
        "app_help": "Draft CLI - 1記事1ブランチで有料記事を管理",
        "no_server": "サーバー未設定。`draft remote <URL>` で設定してください。",
        "no_key": "SSH鍵が見つかりません (~/.ssh/)",
        "connect_fail": "接続失敗",
        "auth_fail": "認証失敗。Web UIでSSH鍵を登録してください。",
        "authenticating": "SSH認証中...",
        "auth_ok": "認証OK",
        "created": "記事ブランチを作成しました",
        "edit_file": "← 編集するファイル",
        "metadata": "← メタデータ",
        "push_confirm": "push?",
        "published": "公開しました",
        "not_found": "パスが見つかりません",
        "wsl_hint": "WSL/Linuxではスラッシュ(/)を使ってください",
        "no_draft_json": "draft.json が見つかりません。記事ディレクトリ内で実行するか、パスを指定してください",
        "no_md": ".mdが見つかりません",
        "no_slug": "まず draft push してください",
        "branch_title": "記事ブランチ",
        "server_articles": "記事一覧（サーバー）",
        "status_col": "ステータス",
        "price_col": "価格",
        "update_col": "更新日",
        "passphrase": "SSH鍵パスフレーズ",
        "uploaded": "📤",
        "new_label": "new",
        "update_label": "update",
    },
    "en": {
        "app_help": "Draft CLI - Manage paid articles with git-style branches",
        "no_server": "Server not set. Run `draft remote <URL>` first.",
        "no_key": "SSH key not found (~/.ssh/)",
        "connect_fail": "Connection failed",
        "auth_fail": "Auth failed. Register your SSH key at the web UI.",
        "authenticating": "Authenticating...",
        "auth_ok": "Auth OK",
        "created": "Article branch created",
        "edit_file": "← edit this file",
        "metadata": "← metadata",
        "push_confirm": "push?",
        "published": "Published",
        "not_found": "Path not found",
        "wsl_hint": "Use forward slashes (/) on WSL/Linux",
        "no_draft_json": "draft.json not found. Run inside an article directory or specify a path.",
        "no_md": "No .md files found",
        "no_slug": "Run draft push first",
        "branch_title": "Article Branches",
        "server_articles": "Articles (Server)",
        "status_col": "Status",
        "price_col": "Price",
        "update_col": "Updated",
        "passphrase": "SSH key passphrase",
        "uploaded": "📤",
        "new_label": "new",
        "update_label": "update",
    },
}

def get_lang():
    return get_config().get("lang", "ja")

def msg(key):
    lang = get_lang()
    return CLI_MESSAGES.get(lang, CLI_MESSAGES["ja"]).get(key, CLI_MESSAGES["ja"].get(key, key))


def get_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}

def save_config(config: dict):
    CONFIG_PATH.parent.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))

def get_base_url():
    config = get_config()
    url = config.get("server")
    if not url:
        typer.echo(f"❌ {msg('no_server')}")
        raise typer.Exit(1)
    return url


def find_private_key():
    for name in ["id_ed25519", "id_ecdsa", "id_rsa"]:
        p = Path.home() / ".ssh" / name
        if p.exists(): return p
    return None

def load_private_key(key_path):
    from cryptography.hazmat.primitives.serialization import load_ssh_private_key, load_pem_private_key
    key_data = key_path.read_bytes()
    try: return load_ssh_private_key(key_data, password=None)
    except Exception:
        try: return load_pem_private_key(key_data, password=None)
        except Exception:
            pw = typer.prompt("SSH鍵パスフレーズ", hide_input=True)
            try: return load_ssh_private_key(key_data, password=pw.encode())
            except Exception: return load_pem_private_key(key_data, password=pw.encode())

def ssh_authenticate(base_url):
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding
    from cryptography.hazmat.primitives import hashes
    key_path = find_private_key()
    if not key_path:
        typer.echo(f"❌ {msg('no_key')}")
        raise typer.Exit(1)
    pk = load_private_key(key_path)
    pub = pk.public_key().public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH)
    raw = base64.b64decode(pub.decode().split()[1])
    fp = hashlib.sha256(raw).hexdigest()
    try: res = httpx.post(f"{base_url}/api/auth/challenge", timeout=5)
    except httpx.ConnectError:
        typer.echo(f"❌ {msg('connect_fail')}: {base_url}")
        raise typer.Exit(1)
    nonce = res.json()["nonce"]
    nb = nonce.encode()
    if isinstance(pk, ed25519.Ed25519PrivateKey): sig = pk.sign(nb)
    elif isinstance(pk, ec.EllipticCurvePrivateKey): sig = pk.sign(nb, ec.ECDSA(hashes.SHA256()))
    else: sig = pk.sign(nb, padding.PKCS1v15(), hashes.SHA256())
    res = httpx.post(f"{base_url}/api/auth/verify",
        json={"fingerprint": fp, "nonce": nonce, "signature": base64.b64encode(sig).decode()}, timeout=5)
    if res.status_code == 200: return res.json()["api_key"]
    typer.echo(f"❌ {msg('auth_fail')}")
    raise typer.Exit(1)


def find_article_dir():
    """カレントディレクトリからdraft.jsonを探す"""
    cwd = Path.cwd()
    if (cwd / "draft.json").exists():
        return cwd
    # Check parent
    if (cwd.parent / "draft.json").exists():
        return cwd.parent
    return None


def load_draft_json(article_dir: Path) -> dict:
    return json.loads((article_dir / "draft.json").read_text())

def save_draft_json(article_dir: Path, data: dict):
    (article_dir / "draft.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ===== Commands =====

@app.command()
def remote(
    url: str = typer.Argument(..., help="Server URL"),
    lang: str = typer.Option("ja", "--lang", "-l", help="Language (ja/en)"),
):
    """Set server URL and language"""
    try: httpx.get(f"{url}/api/articles/?limit=1", timeout=5)
    except httpx.ConnectError:
        typer.echo(f"❌ {msg('connect_fail')}: {url}"); raise typer.Exit(1)
    if lang not in ("ja", "en"):
        lang = "ja"
    config = get_config()
    config["server"] = url.rstrip("/")
    config["lang"] = lang
    save_config(config)
    typer.echo(f"✅ {url} (lang: {lang})")


@app.command()
def new(title: str = typer.Argument(..., help="記事タイトル"),
        price: int = typer.Option(0, "-p", "--price"),
        tags: str = typer.Option("", "--tags")):
    """新規記事ブランチを作成"""
    import re, secrets
    from rich.console import Console
    console = Console()

    slug_base = re.sub(r'[^\w\s-]', '', title.lower())
    slug_base = re.sub(r'[\s_]+', '-', slug_base).strip('-')[:40]
    slug = f"{slug_base}-{secrets.token_hex(3)}" if slug_base else f"article-{secrets.token_hex(3)}"

    DRAFTS_DIR.mkdir(exist_ok=True)
    article_dir = DRAFTS_DIR / slug
    article_dir.mkdir()

    # Create article.md with frontmatter
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    md_content = f"""---
title: "{title}"
price: {price}
tags: {json.dumps(tag_list, ensure_ascii=False)}
---

# {title}

ここに記事を書く...

<!-- paywall -->

ここから有料部分...
"""
    (article_dir / "article.md").write_text(md_content, encoding="utf-8")

    draft_data = {
        "slug": slug, "title": title, "price": price, "tags": tag_list,
        "status": "draft", "server": get_base_url(),
        "created_at": __import__('datetime').datetime.now().isoformat(),
    }
    save_draft_json(article_dir, draft_data)

    console.print(f"\n📝 {msg('created')}")
    console.print(f"   {article_dir}/")
    console.print(f"   ├── article.md    {msg('edit_file')}")
    console.print(f"   └── draft.json    {msg('metadata')}")
    console.print(f"\n   $ cd {article_dir}")
    console.print(f"   $ cursor article.md")
    console.print(f"   $ draft push")


@app.command()
def checkout(slug: str = typer.Argument(..., help="記事slug")):
    """公開済み記事をローカルにダウンロード"""
    from rich.console import Console
    console = Console()
    base_url = get_base_url()
    api_key = ssh_authenticate(base_url)

    res = httpx.get(f"{base_url}/api/articles/{slug}/raw",
        headers={"X-Api-Key": api_key}, timeout=10)
    if res.status_code != 200:
        console.print(f"❌ 記事が見つかりません: {slug}", style="red")
        raise typer.Exit(1)

    data = res.json()
    DRAFTS_DIR.mkdir(exist_ok=True)
    article_dir = DRAFTS_DIR / slug
    article_dir.mkdir(exist_ok=True)

    (article_dir / "article.md").write_text(data["markdown_content"], encoding="utf-8")
    draft_data = {
        "slug": slug, "title": data["title"], "price": data["price"],
        "tags": data["tags"], "status": data["status"], "server": base_url,
        "revision": data.get("revision", 1),
    }
    save_draft_json(article_dir, draft_data)

    console.print(f"📥 {slug}/")
    console.print(f"   {data['title']}  rev.{data.get('revision',1)}  {data['status']}")
    console.print(f"   $ cd {article_dir} && cursor article.md")


@app.command()
def push(
    path: Path = typer.Argument(None, help=".mdファイル, フォルダ, or 省略(カレント)"),
    price: Optional[int] = typer.Option(None, "-p", "--price"),
    title: Optional[str] = typer.Option(None, "-t", "--title"),
    tags: Optional[str] = typer.Option(None, "--tags"),
):
    """記事をpush（SSH鍵で自動認証）"""
    import frontmatter
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    # Validate path first
    if path is None:
        article_dir = find_article_dir()
        if not article_dir:
            console.print(f"❌ {msg('no_draft_json')}", style="red")
            
            console.print("   e.g.: draft push ./my-article/", style="dim")
            raise typer.Exit(1)
    elif not (path.exists() if path else True):
        console.print(f"❌ {msg('not_found')}: {path}", style="red")
        if "\\" in str(path) or str(path).startswith(".\\"):
            console.print(f"   💡 {msg('wsl_hint')}", style="yellow")
            console.print(f"   例: draft push ./{str(path).replace(chr(92), '/')}/", style="dim")
        raise typer.Exit(1)

    base_url = get_base_url()
    console.print(f"🔑 {msg('authenticating')}", style="dim")
    api_key = ssh_authenticate(base_url)

    # Resolve article source
    article_dir = None
    if path is None:
        article_dir = find_article_dir()
        if article_dir:
            path = article_dir / "article.md"
        else:
            console.print("❌ draft.json が見つかりません。記事ディレクトリ内で実行するか、パスを指定してください", style="red")
            raise typer.Exit(1)
    elif path.is_dir():
        if (path / "draft.json").exists():
            article_dir = path
            path = path / "article.md"
        else:
            # Legacy folder mode
            md_files = sorted(path.glob("*.md")) + sorted(path.glob("*.markdown"))
            if not md_files:
                console.print("❌ .mdが見つかりません", style="red")
                raise typer.Exit(1)
            path = md_files[0] if len(md_files) == 1 else path

    # Load draft metadata
    draft_meta = None
    if article_dir and (article_dir / "draft.json").exists():
        draft_meta = load_draft_json(article_dir)

    # Read content
    if path.is_dir():
        md_files = sorted(path.glob("*.md"))
        contents = [f.read_text(encoding="utf-8") for f in md_files]
        md_content = "\n\n---\n\n".join(contents)
        img_dir = path
    else:
        md_content = path.read_text(encoding="utf-8")
        img_dir = path.parent

    # Upload images
    import re
    image_url_map = {}
    refs = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', md_content)
    for ref in refs:
        if ref.startswith(('http://', 'https://', '/storage/')):
            continue
        # Try full relative path first, then filename only
        img_path = img_dir / ref
        if not img_path.exists():
            img_path = img_dir / Path(ref).name
        if img_path.exists() and img_path.suffix.lower() in ('.png','.jpg','.jpeg','.gif','.webp','.svg'):
            ext = img_path.suffix.lower().lstrip('.')
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml"}.get(ext, f"image/{ext}")
            with open(img_path, "rb") as f:
                res = httpx.post(f"{base_url}/api/upload/",
                    files={"file": (img_path.name, f, mime)},
                    headers={"X-Api-Key": api_key},
                    timeout=30)
            if res.status_code == 200:
                image_url_map[img_path.name] = res.json()["url"]
                console.print(f"   📤 {img_path.name}", style="dim")
            else:
                console.print(f"   ✗ upload failed: {img_path.name} ({res.status_code}: {res.text[:100]})", style="red")

    # Parse frontmatter
    post = frontmatter.loads(md_content)
    body = post.content

    # Priority: CLI args > draft.json > frontmatter
    a_title = title or (draft_meta and draft_meta.get("title")) or post.get("title") or path.stem
    a_price = price if price is not None else (draft_meta and draft_meta.get("price")) or post.get("price", 0)
    if tags:
        a_tags = [t.strip() for t in tags.split(",") if t.strip()]
    elif draft_meta and draft_meta.get("tags"):
        a_tags = draft_meta["tags"]
    else:
        a_tags = post.get("tags", [])

    # Rewrite image paths
    for fn, url in image_url_map.items():
        escaped = re.escape(fn)
        body = re.sub(rf'(!\[[^\]]*\])\(([^)]*?{escaped})\)', rf'\1({url})', body)

    slug = draft_meta["slug"] if draft_meta else None

    # Summary
    console.print()
    status_label = msg("update_label") if slug else msg("new_label")
    console.print(f"[bold]{a_title}[/bold]")
    console.print(f"{'¥'+str(a_price) if a_price > 0 else '無料'}  {len(body)}文字  {len(image_url_map)}画像  [{status_label}]")

    if not typer.confirm(msg("push_confirm"), default=True):
        raise typer.Exit(0)

    # Push
    payload = {"title": a_title, "price": a_price, "tags": a_tags, "markdown_content": body, "language": get_lang()}
    headers = {"Content-Type": "application/json", "X-Api-Key": api_key}

    if slug:
        # Check if article exists on server
        check = httpx.get(f"{base_url}/api/articles/{slug}/raw", headers={"X-Api-Key": api_key}, timeout=10)
        if check.status_code == 200:
            res = httpx.put(f"{base_url}/api/articles/{slug}", headers=headers, json=payload, timeout=30)
        else:
            payload["status"] = draft_meta.get("status", "draft")
            res = httpx.post(f"{base_url}/api/articles/", headers=headers, json=payload, timeout=30)
    else:
        res = httpx.post(f"{base_url}/api/articles/", headers=headers, json=payload, timeout=30)

    if res.status_code == 200:
        data = res.json()
        console.print(f"\n🚀 {base_url}{data['url']}", style="bold green")
        console.print(f"   {data['word_count']}文字  無料{int(data['free_ratio']*100)}%")

        # Update draft.json
        if draft_meta:
            draft_meta["slug"] = data["slug"]
            draft_meta["title"] = a_title
            draft_meta["price"] = a_price
            draft_meta["tags"] = a_tags
            save_draft_json(article_dir, draft_meta)
    else:
        console.print(f"❌ {res.text}", style="red")
        raise typer.Exit(1)


@app.command()
def publish(
    unlisted: bool = typer.Option(False, "--unlisted",
        help="限定公開（リンクを知っている人のみアクセス可、検索/一覧から除外）"),
):
    """現在の記事を公開（draft → published）。--unlisted で限定公開"""
    from rich.console import Console
    console = Console()
    article_dir = find_article_dir()
    if not article_dir:
        console.print("❌ draft.jsonが見つかりません", style="red")
        raise typer.Exit(1)

    draft_meta = load_draft_json(article_dir)
    slug = draft_meta.get("slug")
    if not slug:
        console.print(f"❌ {msg('no_slug')}", style="red")
        raise typer.Exit(1)

    base_url = draft_meta.get("server") or get_base_url()
    api_key = ssh_authenticate(base_url)

    target_status = "unlisted" if unlisted else "published"
    res = httpx.patch(f"{base_url}/api/articles/{slug}/status?status={target_status}",
        headers={"X-Api-Key": api_key}, timeout=10)

    if res.status_code == 200:
        draft_meta["status"] = target_status
        save_draft_json(article_dir, draft_meta)
        if unlisted:
            console.print(f"🔗 限定公開: {base_url}/articles/{slug}", style="bold yellow")
        else:
            console.print(f"🚀 {msg('published')}: {base_url}/articles/{slug}", style="bold green")
    else:
        console.print(f"❌ {res.text}", style="red")


@app.command()
def status():
    """記事ブランチ一覧"""
    from rich.console import Console
    from rich.table import Table
    console = Console()

    if not DRAFTS_DIR.exists():
        console.print("記事ブランチはありません。`draft new` で作成してください。")
        return

    table = Table(title=msg("branch_title"))
    table.add_column("ブランチ", style="bold")
    table.add_column("タイトル")
    table.add_column("ステータス")
    table.add_column("価格", justify="right")

    for d in sorted(DRAFTS_DIR.iterdir()):
        if not d.is_dir(): continue
        dj = d / "draft.json"
        if not dj.exists(): continue
        meta = json.loads(dj.read_text())
        status_icon = "🟢" if meta.get("status") == "published" else "🟡"
        price = f"¥{meta['price']}" if meta.get('price', 0) > 0 else "無料"
        table.add_row(d.name, meta.get("title", ""), f"{status_icon} {meta.get('status','draft')}", price)

    console.print(table)


@app.command()
def log(slug: Optional[str] = typer.Argument(None)):
    """リビジョン履歴"""
    from rich.console import Console
    console = Console()

    if not slug:
        article_dir = find_article_dir()
        if article_dir:
            meta = load_draft_json(article_dir)
            slug = meta.get("slug")
    if not slug:
        console.print("❌ slugを指定するか、記事ディレクトリ内で実行してください", style="red")
        raise typer.Exit(1)

    base_url = get_base_url()
    res = httpx.get(f"{base_url}/api/articles/{slug}/revisions", timeout=10)
    if res.status_code != 200:
        console.print(f"❌ {res.text}", style="red")
        raise typer.Exit(1)

    revisions = res.json()
    console.print(f"\n  [bold]{slug}[/bold]\n")
    for rev in revisions:
        console.print(f"  ● rev.{rev['revision']}  {rev['created_at'][:16]}  {rev['word_count']}文字")
        if rev.get('revision_note'):
            console.print(f"    {rev['revision_note']}", style="dim")


@app.command()
def lang(language: str = typer.Argument(..., help="Language (ja/en)")):
    """Switch CLI language / 言語を切り替え"""
    if language not in ("ja", "en"):
        typer.echo("❌ ja or en"); raise typer.Exit(1)
    config = get_config()
    config["lang"] = language
    save_config(config)
    if language == "en":
        typer.echo(f"✅ Language set to English")
    else:
        typer.echo(f"✅ 言語を日本語に設定しました")


@app.command(name="list")
def list_articles():
    """サーバーの記事一覧"""
    from rich.console import Console
    from rich.table import Table
    console = Console()
    base_url = get_base_url()
    api_key = ssh_authenticate(base_url)

    res = httpx.get(f"{base_url}/api/articles/", headers={"X-Api-Key": api_key}, timeout=10)
    if res.status_code != 200:
        console.print(f"❌ {res.text}", style="red"); raise typer.Exit(1)

    articles = res.json()
    table = Table(title=msg("server_articles"))
    table.add_column("タイトル", style="bold")
    table.add_column("ステータス")
    table.add_column("rev")
    table.add_column("価格", justify="right")
    table.add_column("更新日")

    for a in articles:
        st = "🟢" if a["status"] == "published" else "🟡"
        price = f"¥{a['price']}" if a['price'] > 0 else "無料"
        table.add_row(a["title"], f"{st} {a['status']}", str(a.get("revision",1)), price, a["updated_at"][:10])

    console.print(table)


if __name__ == "__main__":
    try:
        app()
    except Exception as e:
        from rich.console import Console
        console = Console()
        err = str(e)
        if "No such file or directory" in err:
            console.print(f"❌ ファイルが見つかりません: {err.split(': ')[-1] if ': ' in err else err}", style="red")
            console.print("   💡 パスを確認してください。WSLではスラッシュ(/)を使います", style="yellow")
        elif "Connection refused" in err or "ConnectError" in err:
            console.print("❌ サーバーに接続できません", style="red")
            console.print("   `draft remote <URL>` でサーバーURLを確認してください", style="dim")
        elif "401" in err or "Authentication" in err:
            console.print("❌ 認証に失敗しました", style="red")
            console.print("   SSH公開鍵が登録されていない可能性があります", style="yellow")
            console.print("   Web UIの設定画面から登録してください: https://draft-publish.com/settings", style="dim")
        else:
            console.print(f"❌ エラー: {err}", style="red")
        raise SystemExit(1)
