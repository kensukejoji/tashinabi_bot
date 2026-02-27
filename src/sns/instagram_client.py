"""
Instagram Graph API クライアント

必要な環境変数:
  IG_USER_ID       ← 数字のInstagramユーザーID（Business/Creator）
  IG_ACCESS_TOKEN  ← Long-lived Access Token（有効期限: 約60日）

投稿フロー:
  1. メディアコンテナ作成（image_url + caption）
  2. コンテナを公開（media_publish）

取得可能なインサイト:
  impressions, reach, likes, comments, shares, saved
"""
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

_BASE = "https://graph.facebook.com/v21.0"


def _ig_user_id() -> str:
    uid = os.environ.get("IG_USER_ID", "")
    if not uid:
        raise EnvironmentError("IG_USER_ID が設定されていません")
    return uid


def _token() -> str:
    token = os.environ.get("IG_ACCESS_TOKEN", "")
    if not token:
        raise EnvironmentError("IG_ACCESS_TOKEN が設定されていません")
    return token


def _raise_for_error(resp: requests.Response) -> None:
    data = resp.json()
    if "error" in data:
        msg = data["error"].get("message", str(data["error"]))
        raise RuntimeError(f"Instagram API エラー: {msg}")
    resp.raise_for_status()


def post_image(caption: str, image_url: str) -> str:
    """
    画像付きフィード投稿を行い ig_media_id を返す。

    Args:
        caption:   投稿文（ハッシュタグ含む）
        image_url: 公開アクセス可能な画像URL
    Returns:
        ig_media_id (str)
    """
    uid = _ig_user_id()
    token = _token()

    # Step 1: メディアコンテナ作成
    resp = requests.post(
        f"{_BASE}/{uid}/media",
        params={
            "image_url":    image_url,
            "caption":      caption,
            "access_token": token,
        },
        timeout=30,
    )
    _raise_for_error(resp)
    container_id = resp.json()["id"]

    # Step 2: 公開（コンテナの処理を少し待つ）
    time.sleep(3)
    resp = requests.post(
        f"{_BASE}/{uid}/media_publish",
        params={
            "creation_id":  container_id,
            "access_token": token,
        },
        timeout=30,
    )
    _raise_for_error(resp)
    return resp.json()["id"]


def post_text_only(caption: str) -> str:
    """
    テキストのみ投稿（画像なし）。
    Instagram Graph API はフィード投稿に画像が必須なため、
    この関数は代わりに Threads API（同じIG_USER_ID/IG_ACCESS_TOKENで利用可）を使用する。
    Threads が利用できない場合は NotImplementedError を送出。

    Returns:
        ig_media_id (str)
    """
    uid = _ig_user_id()
    token = _token()

    # Threads POST エンドポイント (v21.0+)
    resp = requests.post(
        f"{_BASE}/{uid}/threads",
        params={
            "media_type":   "TEXT",
            "text":         caption,
            "access_token": token,
        },
        timeout=30,
    )
    data = resp.json()
    if "error" in data:
        raise NotImplementedError(
            "テキストのみのInstagram投稿はサポートされていません。"
            "商品に image_url を設定してください。"
        )
    container_id = data["id"]

    time.sleep(3)
    resp = requests.post(
        f"{_BASE}/{uid}/threads_publish",
        params={
            "creation_id":  container_id,
            "access_token": token,
        },
        timeout=30,
    )
    _raise_for_error(resp)
    return resp.json()["id"]


def fetch_insights(media_id: str) -> dict:
    """
    投稿インサイトを取得する。

    Returns:
        {
            "likes":       int,
            "reposts":     int,   # shares
            "comments":    int,
            "impressions": int,
        }
    """
    token = _token()
    resp = requests.get(
        f"{_BASE}/{media_id}/insights",
        params={
            "metric":       "impressions,reach,likes,comments,shares,saved",
            "access_token": token,
        },
        timeout=30,
    )
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Instagram Insights エラー: {data['error'].get('message')}")

    metrics = {item["name"]: item["values"][0]["value"] for item in data.get("data", [])}
    return {
        "likes":       metrics.get("likes", 0),
        "reposts":     metrics.get("shares", 0),
        "comments":    metrics.get("comments", 0),
        "impressions": metrics.get("impressions", 0),
    }


def check_credentials() -> bool:
    """環境変数が揃っているか確認"""
    return bool(os.environ.get("IG_USER_ID") and os.environ.get("IG_ACCESS_TOKEN"))
