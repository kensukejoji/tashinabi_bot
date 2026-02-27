from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

VALID_CATEGORIES = [
    "ノンアルドリンク",
    "アロマ・キャンドル",
    "ディフューザー",
    "観葉植物",
    "睡眠デバイス",
]

VALID_PLATFORMS = ["x", "instagram"]

VALID_PATTERNS = ["news", "tips", "experience", "data"]


@dataclass
class Product:
    name: str
    category: str
    description: str
    affiliate_url: str
    image_url: Optional[str] = None
    short_code: Optional[str] = None
    id: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("商品名は必須です")
        if self.category not in VALID_CATEGORIES:
            raise ValueError(f"カテゴリは次のいずれかを指定してください: {', '.join(VALID_CATEGORIES)}")
        if not self.affiliate_url.strip():
            raise ValueError("アフィリエイトURLは必須です")


@dataclass
class Post:
    pattern: str
    x_content: str
    ig_content: str
    product_id: Optional[int] = None
    id: Optional[int] = None
    tweet_id: Optional[str] = None       # X投稿後に保存
    ig_media_id: Optional[str] = None    # Instagram投稿後に保存
    posted_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class PostStats:
    post_id: int
    platform: str
    likes: int = 0
    reposts: int = 0
    comments: int = 0
    impressions: int = 0
    id: Optional[int] = None
    recorded_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def validate(self) -> None:
        if self.platform not in VALID_PLATFORMS:
            raise ValueError(f"platform は {VALID_PLATFORMS} のいずれかを指定してください")


@dataclass
class PostQueue:
    """投稿スケジュールキュー"""
    post_id: int
    platform: str                  # "x" / "instagram" / "both"
    scheduled_at: str              # ISO形式: "2025-01-01T09:00:00"
    status: str = "pending"        # "pending" / "posted" / "failed"
    error_msg: Optional[str] = None
    id: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    posted_at: Optional[str] = None


@dataclass
class LinkClick:
    product_id: int
    short_code: str
    referrer: Optional[str] = None
    id: Optional[int] = None
    clicked_at: str = field(default_factory=lambda: datetime.now().isoformat())
