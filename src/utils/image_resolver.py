"""
画像URL解決モジュール

優先順位:
  1. 商品の image_url（DB保存済み）
  2. Amazon商品ページから自動スクレイピング（affiliate_url がある場合）
  3. YouTube サムネイル
  4. ニュース記事の OGP 画像
  5. Gemini (Nano Banana) で AI 生成 → Telegraph にアップ
"""
import os
import re
import urllib.request
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"), override=True)


def resolve_image_url(
    product_image_url: Optional[str] = None,
    product_affiliate_url: Optional[str] = None,
    youtube_url: Optional[str] = None,
    news_url: Optional[str] = None,
    keywords: Optional[str] = None,
) -> Optional[str]:
    """優先順位順に画像URLを解決して返す"""
    if product_image_url:
        return product_image_url

    # Amazonアフィリエイトリンクから商品画像を自動取得
    if product_affiliate_url:
        from .amazon_image_fetcher import fetch_image_url
        img = fetch_image_url(product_affiliate_url)
        if img:
            return img

    if youtube_url:
        thumbnail = _youtube_thumbnail(youtube_url)
        if thumbnail:
            return thumbnail

    if news_url:
        ogp = _fetch_ogp_image(news_url)
        if ogp:
            return ogp

    if keywords:
        return _generate_with_gemini(keywords)

    return None


def _youtube_thumbnail(url: str) -> Optional[str]:
    """YouTube URL からサムネイル URL を生成"""
    match = re.search(r'(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})', url)
    if not match:
        return None
    video_id = match.group(1)
    # maxresdefault が存在しない場合は hqdefault にフォールバック
    maxres = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    try:
        req = urllib.request.Request(maxres, method="HEAD")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return maxres
    except Exception:
        pass
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


def _fetch_ogp_image(url: str) -> Optional[str]:
    """ニュース記事の OGP 画像 URL を取得"""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; tashinabi-bot/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        # property="og:image" content="..."
        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https?://[^"\'>\s]+)',
            html,
        )
        if not match:
            # content="..." property="og:image" の順番が逆のケース
            match = re.search(
                r'<meta[^>]+content=["\'](https?://[^"\'>\s]+)["\'][^>]+property=["\']og:image["\']',
                html,
            )
        return match.group(1) if match else None
    except Exception:
        return None


def _generate_with_gemini(keywords: str) -> Optional[str]:
    """Gemini (Nano Banana) で画像生成 → Telegraph にアップして URL を返す"""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)

        prompt = (
            f"ソバーキュリアス・健康的なライフスタイルをテーマにした"
            f"SNS投稿用の美しい写真風イメージ。テーマ: {keywords}。"
            "明るく清潔感のある構図、テキストなし、人物なし。"
        )

        model = genai.GenerativeModel("gemini-2.0-flash-preview-image-generation")
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_modalities=["IMAGE"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                image_bytes = part.inline_data.data
                return _upload_to_telegraph(image_bytes)
    except Exception as e:
        print(f"[image_resolver] Gemini生成エラー: {e}")

    return None


def _upload_to_telegraph(image_bytes: bytes) -> Optional[str]:
    """Telegraph に画像をアップロードして公開 URL を返す"""
    try:
        resp = requests.post(
            "https://telegra.ph/upload",
            files={"file": ("image.jpg", image_bytes, "image/jpeg")},
            timeout=30,
        )
        data = resp.json()
        if isinstance(data, list) and data:
            return "https://telegra.ph" + data[0]["src"]
    except Exception as e:
        print(f"[image_resolver] Telegraph アップロードエラー: {e}")
    return None
