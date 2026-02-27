"""
PDFの嗜美製品リストを DBに登録するスクリプト
- 既存のダミーデータ（post_queue / post_stats / posts / link_clicks / products）を全削除
- 実商品データを一括 INSERT
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "db" / "products.db"

PRODUCTS = [
    # ──────────── ノンアルドリンク ────────────
    {
        "name": "クラウスターラー ノンアルコールビール",
        "category": "ノンアルドリンク",
        "description": "ドイツ産本格ノンアルビール。麦芽の旨みとホップの香りをしっかり再現。カロリー控えめでソバーキュリアス生活にぴったり。",
        "affiliate_url": "https://amzn.to/46uOxkq",
    },
    {
        "name": "ヒューガルデン ゼロ",
        "category": "ノンアルドリンク",
        "description": "ベルギーの名門ヒューガルデンが手がけるノンアルコールホワイトビール。コリアンダーとオレンジピールの爽やかな香り。",
        "affiliate_url": "https://amzn.to/4gjwIIx",
    },
    {
        "name": "ヴェリタスブロイ PURE&FREE",
        "category": "ノンアルドリンク",
        "description": "ドイツの伝統製法で造られたノンアルビール。カロリーゼロ・糖質ゼロで罪悪感なく楽しめる。",
        "affiliate_url": "https://amzn.to/4mZ33GT",
    },
    {
        "name": "黒酢とざくろの酢",
        "category": "ノンアルドリンク",
        "description": "黒酢とざくろを組み合わせた飲む酢。フルーティな酸味でそのまま飲んでも、炭酸で割っても美味しい。",
        "affiliate_url": "https://amzn.to/42q3q50",
    },
    {
        "name": "クランベリーストレートジュース",
        "category": "ノンアルドリンク",
        "description": "果汁100%のストレートクランベリージュース。砂糖不使用で自然の甘酸っぱさをそのまま味わえる。",
        "affiliate_url": "https://amzn.to/3J0ixfd",
    },
    {
        "name": "町田しなもん",
        "category": "ノンアルドリンク",
        "description": "国産シナモンを使用したドリンク。ホットにもアイスにも合い、体を内側から温めてくれる。",
        "affiliate_url": "https://amzn.to/46xNb8u",
    },
    {
        "name": "岩手紫波百花蜜",
        "category": "ノンアルドリンク",
        "description": "岩手県紫波産の百花蜜。豊かな花の香りと奥深い甘さが特徴のプレミアムはちみつ。ハーブティーに溶かすと絶品。",
        "affiliate_url": "https://amzn.to/42pkPLh",
    },
    # ──────────── アロマ・キャンドル ────────────
    {
        "name": "3world キャンドルホルダー",
        "category": "アロマ・キャンドル",
        "description": "スタイリッシュなデザインのキャンドルホルダー。ティーライトキャンドルをセットすれば温かみのある光でリラックス空間を演出。",
        "affiliate_url": "https://amzn.to/48amQ1J",
    },
    {
        "name": "ococolar ティーライトキャンドル",
        "category": "アロマ・キャンドル",
        "description": "長時間燃焼するティーライトキャンドル。まとめ買いしやすいコスパの良さで、毎日のリラックスタイムに。",
        "affiliate_url": "https://amzn.to/4o7gFAj",
    },
    {
        "name": "吉野ひのき アロマ",
        "category": "アロマ・キャンドル",
        "description": "奈良・吉野の天然ひのきを使ったアロマ製品。清々しい森林の香りがストレス解消と深呼吸を促す。",
        "affiliate_url": "https://amzn.to/4gjwIIx",
    },
    # ──────────── ディフューザー ────────────
    {
        "name": "NEROLI 精油",
        "category": "ディフューザー",
        "description": "ビターオレンジの花から抽出したネロリ精油。甘くフローラルな香りが不安を和らげ、深いリラクゼーションへ誘う。",
        "affiliate_url": "https://amzn.to/46iLBWK",
    },
    {
        "name": "ユーカリ 精油",
        "category": "ディフューザー",
        "description": "クリアで清涼感あるユーカリ精油。呼吸を楽にしてくれる効果で、集中タイムや朝のルーティンに最適。",
        "affiliate_url": "https://amzn.to/46dGUgT",
    },
    {
        "name": "フランキンセンス 精油",
        "category": "ディフューザー",
        "description": "古来から瞑想や儀式に使われてきたフランキンセンス精油。深みのある樹脂香がマインドフルネスをサポート。",
        "affiliate_url": "https://amzn.to/46iTNXi",
    },
    {
        "name": "ココナッツ 精油",
        "category": "ディフューザー",
        "description": "トロピカルで甘やかなココナッツの香り。ディフューザーで使えばリゾート気分のリラックスタイムに。",
        "affiliate_url": "https://amzn.to/47BkPvf",
    },
]


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        print("=== 既存データを削除 ===")
        # 外部キー参照のある順に削除
        for table in ["post_queue", "post_stats", "link_clicks", "posts", "products"]:
            result = conn.execute(f"DELETE FROM {table}")
            print(f"  {table}: {result.rowcount} 件削除")
        conn.commit()

        print("\n=== 商品を登録 ===")
        from datetime import datetime
        now = datetime.now().isoformat()

        for p in PRODUCTS:
            conn.execute(
                """
                INSERT INTO products (name, category, description, affiliate_url, image_url, short_code, created_at, updated_at)
                VALUES (?, ?, ?, ?, NULL, NULL, ?, ?)
                """,
                (p["name"], p["category"], p["description"], p["affiliate_url"], now, now),
            )
            print(f"  ✓ {p['name']} ({p['category']})")

        conn.commit()

        # 登録件数確認
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        print(f"\n登録完了: {count} 件")

        print("\n=== 登録済み商品一覧 ===")
        rows = conn.execute("SELECT id, name, category FROM products ORDER BY id").fetchall()
        for r in rows:
            print(f"  id={r[0]:2d} | [{r[2]}] {r[1]}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
