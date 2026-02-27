"""
Amazon商品画像自動取得モジュール

amzn.to 短縮URLを解決し、商品ページから画像URLをスクレイピングする。
取得した画像URLはDBに保存して再取得を防ぐ。
"""
import json
import re
import urllib.request
from typing import Optional


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9",
}


def fetch_image_url(affiliate_url: str) -> Optional[str]:
    """
    アフィリエイトURL（amzn.to 短縮 or 通常URL）から商品画像URLを取得する。

    Returns:
        公開アクセス可能な画像URL、取得失敗時は None
    """
    try:
        full_url = _resolve_short_url(affiliate_url)
        if not full_url:
            return None
        return _scrape_product_image(full_url)
    except Exception as e:
        print(f"[amazon_image_fetcher] 画像取得エラー ({affiliate_url}): {e}")
        return None


def _resolve_short_url(url: str) -> Optional[str]:
    """amzn.to / amzn.jp 短縮URLを解決してフルURLを返す"""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        # リダイレクトを追って最終URLを取得
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.url
    except Exception:
        return None


def _scrape_product_image(url: str) -> Optional[str]:
    """Amazon商品ページから最高解像度の商品画像URLを取得する"""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # 方法1: data-a-dynamic-image 属性（JSON形式で複数解像度が入っている）
        match = re.search(r'data-a-dynamic-image=["\'](\{[^"\']+\})["\']', html)
        if match:
            try:
                images = json.loads(match.group(1).replace("&quot;", '"'))
                if images:
                    # 最大面積の画像を選ぶ
                    best = max(images.items(), key=lambda kv: kv[1][0] * kv[1][1])
                    return best[0]
            except Exception:
                pass

        # 方法2: id="landingImage" の src
        match = re.search(r'id="landingImage"[^>]+src="(https://[^"]+)"', html)
        if match:
            return match.group(1)

        # 方法3: media-amazon.com の画像URLを探す
        match = re.search(
            r'(https://m\.media-amazon\.com/images/I/[A-Za-z0-9%._-]+\.(?:jpg|png|jpeg))',
            html,
        )
        if match:
            return match.group(1)

    except Exception as e:
        print(f"[amazon_image_fetcher] スクレイピングエラー ({url}): {e}")

    return None
