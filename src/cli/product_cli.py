import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box

from ..database import repository
from ..database.models import Product, VALID_CATEGORIES

console = Console()


def _category_prompt(default: str = "") -> str:
    console.print("\n[bold]カテゴリを選択してください:[/bold]")
    for i, cat in enumerate(VALID_CATEGORIES, 1):
        console.print(f"  {i}. {cat}")
    while True:
        raw = Prompt.ask("番号を入力", default=str(VALID_CATEGORIES.index(default) + 1) if default in VALID_CATEGORIES else "")
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(VALID_CATEGORIES):
                return VALID_CATEGORIES[idx]
        except ValueError:
            pass
        console.print("[red]1〜5の番号を入力してください[/red]")


@click.group(name="product")
def product_cli():
    """商品データベースの管理"""
    repository.init_db()


@product_cli.command("list")
@click.option("--category", "-c", default=None, help="カテゴリで絞り込み")
def list_products(category: str):
    """商品一覧を表示"""
    products = repository.list_products(category=category)
    if not products:
        console.print("[yellow]商品が登録されていません[/yellow]")
        return

    table = Table(box=box.ROUNDED, show_lines=True)
    table.add_column("ID", style="cyan", width=4)
    table.add_column("商品名", style="bold white", min_width=20)
    table.add_column("カテゴリ", style="green", min_width=14)
    table.add_column("説明", min_width=30, max_width=50, overflow="fold")
    table.add_column("URL", style="blue", min_width=20, max_width=40, overflow="fold")

    for p in products:
        table.add_row(
            str(p.id),
            p.name,
            p.category,
            p.description,
            p.affiliate_url,
        )

    console.print(f"\n[bold]商品一覧[/bold] ({len(products)}件)\n")
    console.print(table)


@product_cli.command("show")
@click.argument("product_id", type=int)
def show_product(product_id: int):
    """商品の詳細を表示"""
    product = repository.get_product(product_id)
    if not product:
        console.print(f"[red]ID={product_id} の商品が見つかりません[/red]")
        return

    console.print(f"\n[bold cyan]── 商品詳細 ID={product.id} ──[/bold cyan]")
    console.print(f"[bold]商品名:[/bold]        {product.name}")
    console.print(f"[bold]カテゴリ:[/bold]      {product.category}")
    console.print(f"[bold]説明:[/bold]          {product.description}")
    console.print(f"[bold]アフィリエイトURL:[/bold] {product.affiliate_url}")
    console.print(f"[bold]画像URL:[/bold]       {product.image_url or '(未設定)'}")
    console.print(f"[bold]登録日:[/bold]        {product.created_at[:10]}")
    console.print(f"[bold]更新日:[/bold]        {product.updated_at[:10]}\n")


@product_cli.command("add")
def add_product():
    """商品を追加（対話式）"""
    console.print("\n[bold green]── 商品追加 ──[/bold green]")

    name = Prompt.ask("商品名")
    category = _category_prompt()
    description = Prompt.ask("商品説明")
    affiliate_url = Prompt.ask("アフィリエイトURL")
    image_url = Prompt.ask("画像URL（スキップはEnter）", default="") or None

    product = Product(
        name=name,
        category=category,
        description=description,
        affiliate_url=affiliate_url,
        image_url=image_url,
    )

    try:
        saved = repository.add_product(product)
        console.print(f"\n[green]✓ 商品を登録しました (ID={saved.id})[/green]")
    except ValueError as e:
        console.print(f"[red]エラー: {e}[/red]")


@product_cli.command("edit")
@click.argument("product_id", type=int)
def edit_product(product_id: int):
    """商品を編集（対話式）"""
    product = repository.get_product(product_id)
    if not product:
        console.print(f"[red]ID={product_id} の商品が見つかりません[/red]")
        return

    console.print(f"\n[bold yellow]── 商品編集 ID={product_id} ──[/bold yellow]")
    console.print("[dim]変更しない項目はEnterを押してください[/dim]\n")

    name = Prompt.ask("商品名", default=product.name)
    category = _category_prompt(default=product.category)
    description = Prompt.ask("商品説明", default=product.description)
    affiliate_url = Prompt.ask("アフィリエイトURL", default=product.affiliate_url)
    image_url = Prompt.ask("画像URL", default=product.image_url or "") or None

    product.name = name
    product.category = category
    product.description = description
    product.affiliate_url = affiliate_url
    product.image_url = image_url

    try:
        repository.update_product(product)
        console.print(f"\n[green]✓ 商品を更新しました (ID={product_id})[/green]")
    except ValueError as e:
        console.print(f"[red]エラー: {e}[/red]")


@product_cli.command("delete")
@click.argument("product_id", type=int)
def delete_product(product_id: int):
    """商品を削除"""
    product = repository.get_product(product_id)
    if not product:
        console.print(f"[red]ID={product_id} の商品が見つかりません[/red]")
        return

    console.print(f"\n[bold]削除対象:[/bold] {product.name}")
    if Confirm.ask("[red]本当に削除しますか？[/red]"):
        repository.delete_product(product_id)
        console.print(f"[green]✓ 削除しました[/green]")
    else:
        console.print("キャンセルしました")
