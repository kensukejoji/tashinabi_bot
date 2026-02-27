"""
Facebook Graph API クライアント（Facebookページ投稿用）

必要な環境変数:
  FB_PAGE_ID           ← FacebookページのID（数字）
  FB_PAGE_ACCESS_TOKEN ← ページアクセストークン（長期トークン推奨）

取得方法:
  1. https://developers.facebook.com でアプリを作成
  2. Facebook Login 権限: pages_manage_posts, pages_read_engagement
  3. Graph API Explorer でページアクセストークンを取得・長期化

投稿フロー:
  - テキスト投稿: POST /{page_id}/feed  (message)
  - 画像投稿:    POST /{page_id}/photos (url + caption)
"""
import os
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

_BASE = "https://graph.facebook.com/v21.0"


def _page_id() -> str:
    pid = os.environ.get("FB_PAGE_ID", "")
    if not pid:
        raise EnvironmentError("FB_PAGE_ID が .env に設定されていません")
    return pid


def _token() -> str:
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    if not token:
        raise EnvironmentError("FB_PAGE_ACCESS_TOKEN が .env に設定されていません")
    return token


def _raise_for_error(resp: requests.Response) -> None:
    data = resp.json()
    if "error" in data:
        err = data["error"]
        msg = err.get("message", str(err))
        code = err.get("code", "")
        raise RuntimeError(f"Facebook API エラー (code={code}): {msg}")
    resp.raise_for_status()


def post_text(message: str) -> str:
    """
    Facebookページにテキスト投稿を行い、post_id を返す。

    Args:
        message: 投稿文
    Returns:
        fb_post_id (str)  例: "123456789_987654321"
    """
    pid = _page_id()
    token = _token()

    resp = requests.post(
        f"{_BASE}/{pid}/feed",
        data={
            "message":      message,
            "access_token": token,
        },
        timeout=30,
    )
    _raise_for_error(resp)
    return resp.json()["id"]


def post_image(message: str, image_url: str) -> str:
    """
    Facebookページに画像付き投稿を行い、post_id を返す。

    Args:
        message:   投稿文（キャプション）
        image_url: 公開アクセス可能な画像URL
    Returns:
        fb_post_id (str)
    """
    pid = _page_id()
    token = _token()

    resp = requests.post(
        f"{_BASE}/{pid}/photos",
        data={
            "url":          image_url,
            "caption":      message,
            "access_token": token,
        },
        timeout=30,
    )
    _raise_for_error(resp)
    data = resp.json()
    # photos API は {"id": ..., "post_id": ...} を返す
    return data.get("post_id") or data["id"]


def fetch_post_insights(post_id: str) -> dict:
    """
    投稿のインサイト（いいね・コメント・シェア・リーチ）を取得する。

    Returns:
        {
            "likes":       int,
            "reposts":     int,   # shares
            "comments":    int,
            "impressions": int,   # reach
        }
    """
    token = _token()

    resp = requests.get(
        f"{_BASE}/{post_id}",
        params={
            "fields":       "likes.summary(true),comments.summary(true),shares",
            "access_token": token,
        },
        timeout=30,
    )
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Facebook インサイト取得エラー: {data['error'].get('message')}")

    likes    = data.get("likes", {}).get("summary", {}).get("total_count", 0)
    comments = data.get("comments", {}).get("summary", {}).get("total_count", 0)
    shares   = data.get("shares", {}).get("count", 0)

    return {
        "likes":       likes,
        "reposts":     shares,
        "comments":    comments,
        "impressions": 0,  # ページインサイトAPIは別エンドポイントが必要
    }


def check_credentials() -> bool:
    """環境変数が揃っているか確認"""
    return bool(os.environ.get("FB_PAGE_ID") and os.environ.get("FB_PAGE_ACCESS_TOKEN"))
