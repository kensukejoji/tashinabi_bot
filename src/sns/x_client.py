"""
X (Twitter) API v2 クライアント

Free プランで利用可能な操作:
  - ツイート投稿
  - public_metrics 取得（いいね・RT・返信・引用）
  ※ インプレッションは Basic tier 以上が必要

必要な環境変数:
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET  ← 投稿用 (OAuth 1.0a)
  X_BEARER_TOKEN                                                    ← 取得用
"""
import os
from typing import Optional

import tweepy
from dotenv import load_dotenv

load_dotenv()


def _write_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def _read_client() -> tweepy.Client:
    return tweepy.Client(bearer_token=os.environ["X_BEARER_TOKEN"])


def post_tweet(text: str) -> str:
    """ツイートを投稿して tweet_id を返す"""
    client = _write_client()
    response = client.create_tweet(text=text)
    return str(response.data["id"])


def fetch_metrics(tweet_id: str) -> dict:
    """
    public_metrics を取得して返す。

    Returns:
        {
            "likes":       int,
            "reposts":     int,   # retweet + quote
            "comments":    int,   # reply
            "impressions": int,   # Free tier では 0 固定
        }
    """
    client = _read_client()
    response = client.get_tweet(
        tweet_id,
        tweet_fields=["public_metrics"],
    )
    if response.data is None:
        raise ValueError(f"tweet_id={tweet_id} のデータが取得できませんでした")

    m = response.data.public_metrics
    return {
        "likes":       m["like_count"],
        "reposts":     m["retweet_count"] + m.get("quote_count", 0),
        "comments":    m["reply_count"],
        "impressions": 0,  # Free tier では取得不可
    }


def check_credentials() -> bool:
    """環境変数が揃っているか確認"""
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN",
                "X_ACCESS_TOKEN_SECRET", "X_BEARER_TOKEN"]
    return all(os.environ.get(k) for k in required)
