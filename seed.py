"""サンプルデータ投入スクリプト"""
from src.database import repository
from src.database.models import Product

SAMPLE_PRODUCTS = [
    Product(
        name="クラウスターラー ノンアルコールビール",
        category="ノンアルドリンク",
        description="ドイツ生まれの本格ノンアルコールビール。麦芽100%使用で本物のビールに限りなく近い味わい。カロリーは通常ビールの約1/3。",
        affiliate_url="https://example.com/affiliate/clausthaler",
        image_url="https://example.com/images/clausthaler.jpg",
    ),
    Product(
        name="美酢（ミチョ）フルーツビネガー",
        category="ノンアルドリンク",
        description="韓国発のフルーツビネガードリンク。ざくろ・パイナップル・カラマンシーなど豊富なフレーバー。腸活・美容にも注目の機能性飲料。",
        affiliate_url="https://example.com/affiliate/micho",
        image_url="https://example.com/images/micho.jpg",
    ),
    Product(
        name="亀山キャンドル アロマキャンドル",
        category="アロマ・キャンドル",
        description="三重県亀山市の老舗キャンドルメーカーが作る高品質アロマキャンドル。天然精油使用で豊かな香り。燃焼時間は約30時間。",
        affiliate_url="https://example.com/affiliate/kameyama-candle",
        image_url="https://example.com/images/kameyama.jpg",
    ),
    Product(
        name="Garmin Venu 3 スマートウォッチ",
        category="睡眠デバイス",
        description="睡眠スコア・睡眠ステージ・睡眠中の血中酸素レベルを計測。ストレス指数やボディバッテリーで毎日のコンディションを可視化。",
        affiliate_url="https://example.com/affiliate/garmin-venu3",
        image_url="https://example.com/images/garmin-venu3.jpg",
    ),
]


def main():
    repository.init_db()
    for product in SAMPLE_PRODUCTS:
        saved = repository.add_product(product)
        print(f"✓ 登録完了: [{saved.id}] {saved.name}")
    print(f"\n合計 {len(SAMPLE_PRODUCTS)} 件のサンプルデータを投入しました")


if __name__ == "__main__":
    main()
