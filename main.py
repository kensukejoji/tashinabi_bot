import click
from src.cli.product_cli import product_cli
from src.cli.generate_cli import generate_cli
from src.cli.stats_cli import stats_cli


@click.group()
def cli():
    """ソバーキュリアス SNS自動投稿システム"""
    pass


cli.add_command(product_cli)
cli.add_command(generate_cli)
cli.add_command(stats_cli)

if __name__ == "__main__":
    cli()
