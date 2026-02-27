import json
import os
import random
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

import anthropic
from dotenv import load_dotenv

from ..database.models import Post, Product
from ..database import repository
from .prompts import PostPattern, build_prompt, random_pattern

load_dotenv()

# カテゴリと関連キーワードのマッピング（URL紐づけに使用）
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "ノンアルドリンク": ["ノンアル", "ビール", "ドリンク", "飲み物", "酒", "乾杯", "お茶", "ジュース", "ビネガー", "酢"],
    "アロマ・キャンドル": ["アロマ", "キャンドル", "香り", "癒し", "リラックス", "香"],
    "ディフューザー": ["ディフューザー", "香り", "アロマ", "空間", "部屋"],
    "観葉植物": ["植物", "グリーン", "インテリア", "自然", "観葉"],
    "睡眠デバイス": ["睡眠", "眠り", "寝る", "朝", "目覚め", "スマートウォッチ", "ガーミン", "Garmin", "健康"],
}


@dataclass
class GeneratedPost:
    pattern: PostPattern
    x_post: str
    instagram_post: str
    suggested_category: str
    matched_product: Optional[Product]
    saved_post_id: Optional[int] = None
    youtube_url: Optional[str] = None
    youtube_title: Optional[str] = None
    news_url: Optional[str] = None

    @property
    def x_post_with_url(self) -> str:
        parts = []
        # YouTube URL を先に追加（スペースを確保）
        yt_suffix = f" {self.youtube_url}" if self.youtube_url else ""
        prod_suffix = f" {self.matched_product.affiliate_url}" if self.matched_product else ""
        limit = 140 - len(yt_suffix) - len(prod_suffix)
        base = self.x_post[:limit] if len(self.x_post) > limit else self.x_post
        return base + yt_suffix + prod_suffix

    @property
    def instagram_post_with_url(self) -> str:
        result = self.instagram_post
        if self.youtube_url:
            result += f"\n\n▶️ 動画で詳しく解説中！\n{self.youtube_url}"
        if self.matched_product:
            result += (
                f"\n\n🛒 おすすめ商品: {self.matched_product.name}\n"
                + self.matched_product.affiliate_url
            )
        return result


def _fetch_youtube_title(url: str) -> str:
    """YouTube oEmbed APIで動画タイトルを取得する（APIキー不要）"""
    oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(url, safe='')}&format=json"
    try:
        req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("title", "")
    except Exception:
        return ""


def _find_matching_product(category: str, all_products: list[Product]) -> Optional[Product]:
    """カテゴリに一致する商品からランダムに1件返す"""
    matched = [p for p in all_products if p.category == category]
    if matched:
        return random.choice(matched)

    # カテゴリ完全一致がなければキーワードで探す
    keywords = CATEGORY_KEYWORDS.get(category, [])
    keyword_matched = [
        p for p in all_products
        if any(kw in p.name or kw in p.description for kw in keywords)
    ]
    return random.choice(keyword_matched) if keyword_matched else None


def generate_post(
    pattern: Optional[PostPattern] = None,
    category_filter: Optional[str] = None,
    youtube_url: Optional[str] = None,
    news_article: Optional[dict] = None,
) -> GeneratedPost:
    """投稿文を生成してDBの商品URLを紐づける

    Args:
        pattern: 投稿パターン（None でランダム）
        category_filter: 商品カテゴリ絞り込み
        youtube_url: YouTube動画URL（指定するとパターンが youtube に固定）
        news_article: ニュース記事情報 {"title", "url", "summary", "source"}
                      指定するとパターンが news に固定
    """
    selected_pattern = pattern or random_pattern()

    # YouTube URLが指定されたらパターンをyoutubeに固定し、タイトルを取得
    video_title = ""
    if youtube_url:
        selected_pattern = "youtube"
        video_title = _fetch_youtube_title(youtube_url)

    # ニュース記事が指定されたらパターンをnewsに固定
    if news_article:
        selected_pattern = "news"

    system_prompt, user_prompt = build_prompt(
        selected_pattern,
        video_title=video_title,
        news_article=news_article,
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY が設定されていません。.env ファイルに正しい API キーを記入してください。"
        )
    try:
        api_key.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(
            "ANTHROPIC_API_KEY に日本語などの非ASCII文字が含まれています。"
            ".env ファイルの ANTHROPIC_API_KEY=（既存） を実際の APIキー（sk-ant-api03-...）に書き換えてください。"
        )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()

    # JSONブロックのみ抽出（複数パターンに対応）
    # 1) ```json ... ``` または ``` ... ``` 形式
    import re as _re
    code_match = _re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
    if code_match:
        raw = code_match.group(1).strip()
    else:
        # 2) { ... } のJSONオブジェクト部分だけ取り出す
        obj_match = _re.search(r'\{[\s\S]*\}', raw)
        if obj_match:
            raw = obj_match.group(0).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Claude の返答を JSON として解析できませんでした: {e}\n"
            f"--- 返答内容 ---\n{raw[:500]}"
        ) from e

    # 商品とのマッチング
    all_products = repository.list_products(category=category_filter)
    suggested_category = data.get("suggested_category", "")
    # カテゴリ絞り込みが指定されている場合はそのリストから直接選ぶ
    if category_filter and all_products:
        matched_product = random.choice(all_products)
    else:
        matched_product = _find_matching_product(suggested_category, all_products)

    result = GeneratedPost(
        pattern=data["pattern"],
        x_post=data["x_post"],
        instagram_post=data["instagram_post"],
        suggested_category=suggested_category,
        matched_product=matched_product,
        youtube_url=youtube_url,
        youtube_title=video_title or None,
        news_url=news_article.get("url") if news_article else None,
    )

    # 生成した投稿をDBに保存
    saved = repository.save_post(Post(
        pattern=result.pattern,
        x_content=result.x_post_with_url,
        ig_content=result.instagram_post_with_url,
        product_id=matched_product.id if matched_product else None,
    ))
    result.saved_post_id = saved.id

    return result
