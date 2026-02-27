import random
import sqlite3
import string
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import LinkClick, Post, PostQueue, PostStats, Product

DB_PATH = Path(__file__).parent.parent.parent / "db" / "products.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                category      TEXT    NOT NULL,
                description   TEXT    NOT NULL,
                affiliate_url TEXT    NOT NULL,
                image_url     TEXT,
                short_code    TEXT    UNIQUE,
                created_at    TEXT    NOT NULL,
                updated_at    TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER REFERENCES products(id),
                pattern     TEXT    NOT NULL,
                x_content   TEXT    NOT NULL,
                ig_content  TEXT    NOT NULL,
                posted_at   TEXT,
                created_at  TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS post_stats (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id     INTEGER NOT NULL REFERENCES posts(id),
                platform    TEXT    NOT NULL,
                likes       INTEGER NOT NULL DEFAULT 0,
                reposts     INTEGER NOT NULL DEFAULT 0,
                comments    INTEGER NOT NULL DEFAULT 0,
                impressions INTEGER NOT NULL DEFAULT 0,
                recorded_at TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS link_clicks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER NOT NULL REFERENCES products(id),
                short_code  TEXT    NOT NULL,
                referrer    TEXT,
                clicked_at  TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS post_queue (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id      INTEGER NOT NULL REFERENCES posts(id),
                platform     TEXT    NOT NULL,
                scheduled_at TEXT    NOT NULL,
                status       TEXT    NOT NULL DEFAULT 'pending',
                error_msg    TEXT,
                posted_at    TEXT,
                created_at   TEXT    NOT NULL
            )
        """)
        # 既存DBとの互換: カラムが存在しない場合のみ追加
        for alter_sql in [
            "ALTER TABLE products ADD COLUMN short_code TEXT",
            "ALTER TABLE posts ADD COLUMN tweet_id TEXT",
            "ALTER TABLE posts ADD COLUMN ig_media_id TEXT",
        ]:
            try:
                conn.execute(alter_sql)
            except sqlite3.OperationalError:
                pass
        conn.commit()


# ─────────────────────────────────────────
# Utility
# ─────────────────────────────────────────

def _generate_short_code(length: int = 6) -> str:
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))


def _ensure_short_code(product_id: int) -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT short_code FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if row and row["short_code"]:
            return row["short_code"]
        # 重複しないコードを生成
        for _ in range(10):
            code = _generate_short_code()
            existing = conn.execute(
                "SELECT id FROM products WHERE short_code = ?", (code,)
            ).fetchone()
            if not existing:
                conn.execute(
                    "UPDATE products SET short_code = ? WHERE id = ?", (code, product_id)
                )
                conn.commit()
                return code
    raise RuntimeError("short_code の生成に失敗しました")


# ─────────────────────────────────────────
# Products
# ─────────────────────────────────────────

def _row_to_product(row: sqlite3.Row) -> Product:
    return Product(
        id=row["id"],
        name=row["name"],
        category=row["category"],
        description=row["description"],
        affiliate_url=row["affiliate_url"],
        image_url=row["image_url"],
        short_code=row["short_code"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def add_product(product: Product) -> Product:
    product.validate()
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO products
              (name, category, description, affiliate_url, image_url, short_code, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (product.name, product.category, product.description,
             product.affiliate_url, product.image_url, product.short_code, now, now),
        )
        conn.commit()
        product.id = cursor.lastrowid
        product.created_at = now
        product.updated_at = now
    # short_code が未設定なら自動生成
    if not product.short_code:
        product.short_code = _ensure_short_code(product.id)
    return product


def get_product(product_id: int) -> Optional[Product]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
    return _row_to_product(row) if row else None


def get_product_by_short_code(short_code: str) -> Optional[Product]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE short_code = ?", (short_code,)
        ).fetchone()
    return _row_to_product(row) if row else None


def list_products(category: Optional[str] = None) -> list[Product]:
    with get_connection() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM products WHERE category = ? ORDER BY id", (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    return [_row_to_product(r) for r in rows]


def update_product(product: Product) -> Product:
    if product.id is None:
        raise ValueError("idが設定されていません")
    product.validate()
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE products
            SET name=?, category=?, description=?, affiliate_url=?, image_url=?, updated_at=?
            WHERE id=?
            """,
            (product.name, product.category, product.description,
             product.affiliate_url, product.image_url, now, product.id),
        )
        conn.commit()
        product.updated_at = now
    return product


def delete_product(product_id: int) -> bool:
    with get_connection() as conn:
        result = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
    return result.rowcount > 0


# ─────────────────────────────────────────
# Posts
# ─────────────────────────────────────────

def _row_to_post(row: sqlite3.Row) -> Post:
    return Post(
        id=row["id"],
        product_id=row["product_id"],
        pattern=row["pattern"],
        x_content=row["x_content"],
        ig_content=row["ig_content"],
        tweet_id=row["tweet_id"] if "tweet_id" in row.keys() else None,
        ig_media_id=row["ig_media_id"] if "ig_media_id" in row.keys() else None,
        posted_at=row["posted_at"],
        created_at=row["created_at"],
    )


def save_post(post: Post) -> Post:
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO posts
              (product_id, pattern, x_content, ig_content, tweet_id, ig_media_id, posted_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (post.product_id, post.pattern, post.x_content, post.ig_content,
             post.tweet_id, post.ig_media_id, post.posted_at, now),
        )
        conn.commit()
        post.id = cursor.lastrowid
        post.created_at = now
    return post


def update_post_sns_ids(
    post_id: int,
    tweet_id: Optional[str] = None,
    ig_media_id: Optional[str] = None,
    posted_at: Optional[str] = None,
) -> None:
    """X/Instagram投稿後のIDとposted_atを保存"""
    now = posted_at or datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE posts
            SET tweet_id=COALESCE(?, tweet_id),
                ig_media_id=COALESCE(?, ig_media_id),
                posted_at=?
            WHERE id=?
            """,
            (tweet_id, ig_media_id, now, post_id),
        )
        conn.commit()


def get_post(post_id: int) -> Optional[Post]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return _row_to_post(row) if row else None


def list_posts() -> list[Post]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
    return [_row_to_post(r) for r in rows]


def list_published_posts() -> list[Post]:
    """tweet_id または ig_media_id が設定されている投稿のみ返す"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM posts WHERE tweet_id IS NOT NULL OR ig_media_id IS NOT NULL ORDER BY id DESC"
        ).fetchall()
    return [_row_to_post(r) for r in rows]


# ─────────────────────────────────────────
# PostStats
# ─────────────────────────────────────────

def add_post_stats(stats: PostStats) -> PostStats:
    stats.validate()
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO post_stats
              (post_id, platform, likes, reposts, comments, impressions, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (stats.post_id, stats.platform, stats.likes, stats.reposts,
             stats.comments, stats.impressions, now),
        )
        conn.commit()
        stats.id = cursor.lastrowid
        stats.recorded_at = now
    return stats


def list_post_stats_with_posts() -> list[dict]:
    """投稿情報とエンゲージメントをJOINして返す（ダッシュボード用）"""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                ps.id            AS stats_id,
                ps.post_id,
                ps.platform,
                ps.likes,
                ps.reposts,
                ps.comments,
                ps.impressions,
                ps.recorded_at,
                p.pattern,
                p.x_content,
                p.ig_content,
                p.created_at     AS post_created_at,
                p.product_id,
                pr.name          AS product_name,
                pr.category      AS product_category
            FROM post_stats ps
            JOIN posts p   ON ps.post_id    = p.id
            LEFT JOIN products pr ON p.product_id = pr.id
            ORDER BY ps.recorded_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────
# PostQueue
# ─────────────────────────────────────────

def _row_to_queue(row: sqlite3.Row) -> PostQueue:
    return PostQueue(
        id=row["id"],
        post_id=row["post_id"],
        platform=row["platform"],
        scheduled_at=row["scheduled_at"],
        status=row["status"],
        error_msg=row["error_msg"],
        posted_at=row["posted_at"],
        created_at=row["created_at"],
    )


def add_to_queue(item: PostQueue) -> PostQueue:
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO post_queue
              (post_id, platform, scheduled_at, status, error_msg, posted_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (item.post_id, item.platform, item.scheduled_at,
             item.status, item.error_msg, item.posted_at, now),
        )
        conn.commit()
        item.id = cursor.lastrowid
        item.created_at = now
    return item


def list_queue(status: Optional[str] = None) -> list[PostQueue]:
    with get_connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM post_queue WHERE status=? ORDER BY scheduled_at", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM post_queue ORDER BY scheduled_at DESC"
            ).fetchall()
    return [_row_to_queue(r) for r in rows]


def list_due_queue() -> list[PostQueue]:
    """scheduled_at <= 現在時刻 かつ status=pending のものを返す"""
    now = datetime.now().isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM post_queue WHERE status='pending' AND scheduled_at <= ? ORDER BY scheduled_at",
            (now,),
        ).fetchall()
    return [_row_to_queue(r) for r in rows]


def update_queue_status(
    queue_id: int,
    status: str,
    error_msg: Optional[str] = None,
    posted_at: Optional[str] = None,
) -> None:
    now = posted_at or datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE post_queue SET status=?, error_msg=?, posted_at=? WHERE id=?",
            (status, error_msg, now if status == "posted" else None, queue_id),
        )
        conn.commit()


def delete_queue_item(queue_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM post_queue WHERE id=?", (queue_id,))
        conn.commit()


def list_queue_with_posts() -> list[dict]:
    """キューと投稿内容をJOINして返す（スケジュール管理画面用）"""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                q.id           AS queue_id,
                q.post_id,
                q.platform,
                q.scheduled_at,
                q.status,
                q.error_msg,
                q.posted_at,
                q.created_at,
                p.pattern,
                p.x_content,
                p.ig_content
            FROM post_queue q
            JOIN posts p ON q.post_id = p.id
            ORDER BY q.scheduled_at
        """).fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────
# LinkClicks
# ─────────────────────────────────────────

def record_click(product_id: int, short_code: str, referrer: Optional[str] = None) -> LinkClick:
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO link_clicks (product_id, short_code, referrer, clicked_at) VALUES (?, ?, ?, ?)",
            (product_id, short_code, referrer, now),
        )
        conn.commit()
    return LinkClick(
        id=cursor.lastrowid,
        product_id=product_id,
        short_code=short_code,
        referrer=referrer,
        clicked_at=now,
    )


def list_clicks_with_products() -> list[dict]:
    """クリックログと商品情報をJOINして返す（ダッシュボード用）"""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                lc.id         AS click_id,
                lc.product_id,
                lc.short_code,
                lc.referrer,
                lc.clicked_at,
                pr.name       AS product_name,
                pr.category   AS product_category
            FROM link_clicks lc
            JOIN products pr ON lc.product_id = pr.id
            ORDER BY lc.clicked_at DESC
        """).fetchall()
    return [dict(r) for r in rows]
