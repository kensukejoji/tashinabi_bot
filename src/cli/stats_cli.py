import click
from rich.console import Console
from rich.table import Table
from rich.prompt import IntPrompt
from rich import box

from ..database import repository
from ..database.models import PostStats, VALID_PLATFORMS

console = Console()

PLATFORM_CHOICES = ["x", "instagram"]


@click.group(name="stats")
def stats_cli():
    """エンゲージメントの手動入力・確認"""
    repository.init_db()


@stats_cli.command("posts")
def list_posts():
    """保存済み投稿の一覧を表示"""
    posts = repository.list_posts()
    if not posts:
        console.print("[yellow]投稿が保存されていません。まず generate post を実行してください[/yellow]")
        return

    table = Table(box=box.ROUNDED, show_lines=True)
    table.add_column("ID", style="cyan", width=4)
    table.add_column("パターン", style="green", width=12)
    table.add_column("X投稿（冒頭）", min_width=35, max_width=50, overflow="fold")
    table.add_column("生成日時", style="dim", width=16)

    pattern_labels = {
        "news": "ニュース", "tips": "Tips",
        "experience": "体験共有", "data": "データ",
    }

    for p in posts:
        table.add_row(
            str(p.id),
            pattern_labels.get(p.pattern, p.pattern),
            p.x_content[:60] + "..." if len(p.x_content) > 60 else p.x_content,
            p.created_at[:16].replace("T", " "),
        )

    console.print(f"\n[bold]保存済み投稿[/bold] ({len(posts)}件)\n")
    console.print(table)


@stats_cli.command("add")
@click.argument("post_id", type=int)
@click.option("--platform", "-p", type=click.Choice(PLATFORM_CHOICES), default=None)
def add_stats(post_id: int, platform: str):
    """投稿のエンゲージメントを手動入力"""
    post = repository.get_post(post_id)
    if not post:
        console.print(f"[red]ID={post_id} の投稿が見つかりません[/red]")
        console.print("  → python3 main.py stats posts  で一覧を確認してください")
        return

    if not platform:
        console.print("\nプラットフォームを選択:")
        console.print("  1. X（Twitter）")
        console.print("  2. Instagram")
        choice = IntPrompt.ask("番号", default=1)
        platform = "x" if choice == 1 else "instagram"

    console.print(f"\n[bold yellow]── エンゲージメント入力 投稿ID={post_id} / {platform.upper()} ──[/bold yellow]")
    console.print("[dim]数値を入力してEnter（0でもOK）[/dim]\n")

    likes       = IntPrompt.ask("いいね数",       default=0)
    reposts     = IntPrompt.ask("リポスト/シェア数", default=0)
    comments    = IntPrompt.ask("コメント数",      default=0)
    impressions = IntPrompt.ask("インプレッション数", default=0)

    stats = PostStats(
        post_id=post_id,
        platform=platform,
        likes=likes,
        reposts=reposts,
        comments=comments,
        impressions=impressions,
    )

    try:
        saved = repository.add_post_stats(stats)
        console.print(f"\n[green]✓ エンゲージメントを記録しました (ID={saved.id})[/green]")
    except ValueError as e:
        console.print(f"[red]エラー: {e}[/red]")


@stats_cli.command("show")
@click.argument("post_id", type=int)
def show_stats(post_id: int):
    """特定投稿のエンゲージメント履歴を表示"""
    rows = repository.list_post_stats_with_posts()
    post_rows = [r for r in rows if r["post_id"] == post_id]

    if not post_rows:
        console.print(f"[yellow]ID={post_id} のエンゲージメントデータがありません[/yellow]")
        return

    table = Table(box=box.ROUNDED)
    table.add_column("プラットフォーム", style="cyan")
    table.add_column("いいね", justify="right")
    table.add_column("リポスト", justify="right")
    table.add_column("コメント", justify="right")
    table.add_column("インプレッション", justify="right")
    table.add_column("記録日時", style="dim")

    for r in post_rows:
        table.add_row(
            r["platform"].upper(),
            str(r["likes"]),
            str(r["reposts"]),
            str(r["comments"]),
            str(r["impressions"]),
            r["recorded_at"][:16].replace("T", " "),
        )

    console.print(f"\n[bold]投稿ID={post_id} エンゲージメント履歴[/bold]\n")
    console.print(table)


@stats_cli.command("fetch")
@click.option("--id", "post_id", type=int, default=None,
              help="取得する投稿ID（未指定で投稿済み全件）")
@click.option("--platform", "-p",
              type=click.Choice(VALID_PLATFORMS),
              default=None,
              help="取得対象プラットフォーム（未指定で両方）")
def fetch_stats(post_id, platform):
    """SNS APIからエンゲージメントを自動取得してDBに保存"""
    from ..sns import x_client, instagram_client

    if post_id:
        post = repository.get_post(post_id)
        posts = [post] if post else []
    else:
        posts = repository.list_published_posts()

    if not posts:
        console.print("[yellow]投稿済みの投稿がありません[/yellow]")
        console.print("  → python3 main.py generate post --publish  で投稿してください")
        return

    console.print(f"\n[bold cyan]{len(posts)} 件の投稿を処理します...[/bold cyan]\n")

    x_ok  = x_client.check_credentials()
    ig_ok = instagram_client.check_credentials()
    success = 0
    skipped = 0

    for post in posts:
        console.print(f"[dim]post_id={post.id}  pattern={post.pattern}[/dim]")

        # ── X エンゲージメント取得 ─────────────────────────────
        if platform in (None, "x") and post.tweet_id:
            if not x_ok:
                console.print("  [yellow]X: APIキー未設定のためスキップ[/yellow]")
            else:
                try:
                    metrics = x_client.fetch_metrics(post.tweet_id)
                    repository.add_post_stats(PostStats(
                        post_id=post.id, platform="x", **metrics
                    ))
                    console.print(
                        f"  [green]✓ X: いいね={metrics['likes']} "
                        f"RT={metrics['reposts']} 返信={metrics['comments']}[/green]"
                    )
                    success += 1
                except Exception as e:
                    console.print(f"  [red]X 取得エラー: {e}[/red]")
        elif platform in (None, "x") and not post.tweet_id:
            console.print("  [dim]X: tweet_id 未設定のためスキップ[/dim]")
            skipped += 1

        # ── Instagram エンゲージメント取得 ─────────────────────
        if platform in (None, "instagram") and post.ig_media_id:
            if not ig_ok:
                console.print("  [yellow]Instagram: APIキー未設定のためスキップ[/yellow]")
            else:
                try:
                    metrics = instagram_client.fetch_insights(post.ig_media_id)
                    repository.add_post_stats(PostStats(
                        post_id=post.id, platform="instagram", **metrics
                    ))
                    console.print(
                        f"  [green]✓ Instagram: いいね={metrics['likes']} "
                        f"シェア={metrics['reposts']} コメント={metrics['comments']} "
                        f"インプレッション={metrics['impressions']}[/green]"
                    )
                    success += 1
                except Exception as e:
                    console.print(f"  [red]Instagram 取得エラー: {e}[/red]")
        elif platform in (None, "instagram") and not post.ig_media_id:
            console.print("  [dim]Instagram: media_id 未設定のためスキップ[/dim]")
            skipped += 1

    console.print(f"\n[bold]完了: 成功 {success} 件 / スキップ {skipped} 件[/bold]\n")
