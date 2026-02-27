import click
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich import box

from ..database import repository
from ..database.models import VALID_CATEGORIES
from ..generator.prompts import PATTERNS
from ..generator.post_generator import generate_post

console = Console()

PATTERN_LABELS = {
    "news":       "ニュース紹介型",
    "tips":       "Tips型",
    "experience": "体験共有型",
    "data":       "データ型",
}

SNS_CHOICES = ["x", "instagram", "both"]


@click.group(name="generate")
def generate_cli():
    """投稿文の生成"""
    repository.init_db()


@generate_cli.command("post")
@click.option(
    "--pattern", "-p",
    type=click.Choice(PATTERNS),
    default=None,
    help="投稿パターン（未指定でランダム）",
)
@click.option(
    "--category", "-c",
    type=click.Choice(VALID_CATEGORIES),
    default=None,
    help="商品紐づけ対象のカテゴリを絞り込み",
)
@click.option(
    "--publish",
    is_flag=True,
    default=False,
    help="生成後にSNSへ投稿する",
)
@click.option(
    "--to",
    type=click.Choice(SNS_CHOICES),
    default="both",
    show_default=True,
    help="投稿先 (--publish 時のみ有効)",
)
def generate_post_cmd(pattern, category, publish, to):
    """投稿文を生成してX・Instagram用を出力。--publish で実際に投稿。"""
    console.print("\n[bold cyan]投稿文を生成しています...[/bold cyan]")

    try:
        result = generate_post(pattern=pattern, category_filter=category)
    except Exception as e:
        console.print(f"[red]生成エラー: {e}[/red]")
        raise SystemExit(1)

    pattern_label = PATTERN_LABELS.get(result.pattern, result.pattern)

    console.print()
    console.print(Rule(f"[bold]パターン: {pattern_label}[/bold]"))

    # X用
    console.print()
    console.print(Panel(
        result.x_post_with_url,
        title="[bold blue]X（Twitter）投稿文[/bold blue]",
        box=box.ROUNDED,
        padding=(1, 2),
    ))
    x_len = len(result.x_post_with_url)
    color = "green" if x_len <= 140 else "red"
    console.print(f"  [{color}]文字数: {x_len} / 140[/{color}]")

    # Instagram用
    console.print()
    console.print(Panel(
        result.instagram_post_with_url,
        title="[bold magenta]Instagram 投稿文[/bold magenta]",
        box=box.ROUNDED,
        padding=(1, 2),
    ))
    console.print(f"  [dim]文字数: {len(result.instagram_post_with_url)}[/dim]")

    # 紐づけ商品情報
    console.print()
    if result.matched_product:
        console.print(f"[bold]紐づけ商品:[/bold] {result.matched_product.name} "
                      f"([dim]{result.matched_product.category}[/dim])")
    else:
        console.print("[yellow]紐づけ商品: 該当なし（DBに商品を登録してください）[/yellow]")

    if result.saved_post_id:
        console.print(f"[dim]DB保存済み: post_id={result.saved_post_id}[/dim]")
    console.print()

    # ── SNS 投稿 ───────────────────────────────────────────────────────
    if not publish:
        return

    _publish_to_sns(result, to)


def _publish_to_sns(result, to: str) -> None:
    """SNSへの投稿処理"""
    from ..sns import x_client, instagram_client

    post_id = result.saved_post_id
    tweet_id = None
    ig_media_id = None

    # ── X 投稿 ──────────────────────────────────────────────
    if to in ("x", "both"):
        if not x_client.check_credentials():
            console.print("[yellow]X APIキーが .env に設定されていません。スキップします。[/yellow]")
        else:
            console.print("[blue]X に投稿中...[/blue]")
            try:
                tweet_id = x_client.post_tweet(result.x_post_with_url)
                console.print(f"[green]✓ X 投稿完了 tweet_id={tweet_id}[/green]")
            except Exception as e:
                console.print(f"[red]X 投稿エラー: {e}[/red]")

    # ── Instagram 投稿 ──────────────────────────────────────
    if to in ("instagram", "both"):
        if not instagram_client.check_credentials():
            console.print("[yellow]Instagram APIキーが .env に設定されていません。スキップします。[/yellow]")
        else:
            console.print("[magenta]Instagram に投稿中...[/magenta]")
            try:
                image_url = result.matched_product.image_url if result.matched_product else None
                if image_url:
                    ig_media_id = instagram_client.post_image(
                        caption=result.instagram_post_with_url,
                        image_url=image_url,
                    )
                else:
                    ig_media_id = instagram_client.post_text_only(
                        caption=result.instagram_post_with_url,
                    )
                console.print(f"[green]✓ Instagram 投稿完了 media_id={ig_media_id}[/green]")
            except NotImplementedError as e:
                console.print(f"[yellow]Instagram: {e}[/yellow]")
            except Exception as e:
                console.print(f"[red]Instagram 投稿エラー: {e}[/red]")

    # DB に SNS ID を保存
    if post_id and (tweet_id or ig_media_id):
        repository.update_post_sns_ids(
            post_id=post_id,
            tweet_id=tweet_id,
            ig_media_id=ig_media_id,
        )
        console.print(f"[dim]SNS ID を DB に保存しました (post_id={post_id})[/dim]")
