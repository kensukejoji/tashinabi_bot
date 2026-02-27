"""
YouTube チャンネルの最新動画リストを取得するユーティリティ。
YouTube Data API キー不要 — チャンネルページのスクレイプ + RSS フィードを利用。
"""

import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# デフォルトのチャンネル URL（.env の YOUTUBE_CHANNEL_URL で上書き可）
DEFAULT_CHANNEL_URL = "https://www.youtube.com/@jinkaejoji"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _get_channel_id(channel_url: str) -> Optional[str]:
    """チャンネルページの HTML から channel ID（UC...）を抽出する"""
    try:
        req = urllib.request.Request(channel_url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # パターン1: "externalId":"UCxxxxxxxx"
        m = re.search(r'"externalId"\s*:\s*"(UC[A-Za-z0-9_\-]+)"', html)
        if m:
            return m.group(1)

        # パターン2: /channel/UCxxxxxxxx
        m = re.search(r'youtube\.com/channel/(UC[A-Za-z0-9_\-]+)', html)
        if m:
            return m.group(1)

        # パターン3: "channelId":"UCxxxxxxxx"
        m = re.search(r'"channelId"\s*:\s*"(UC[A-Za-z0-9_\-]+)"', html)
        if m:
            return m.group(1)

        return None
    except Exception:
        return None


def fetch_channel_videos(
    channel_url: Optional[str] = None,
    max_videos: int = 20,
) -> list[dict]:
    """
    チャンネルの最新動画リストを返す。

    Returns:
        [{"title": str, "url": str, "video_id": str}, ...]
        取得失敗時は空リストを返す（例外は送出しない）。
    """
    url = channel_url or os.environ.get("YOUTUBE_CHANNEL_URL", DEFAULT_CHANNEL_URL)

    channel_id = _get_channel_id(url)
    if not channel_id:
        return []

    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        req = urllib.request.Request(rss_url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
            "media": "http://search.yahoo.com/mrss/",
        }

        videos = []
        for entry in root.findall("atom:entry", ns)[:max_videos]:
            video_id = entry.findtext("yt:videoId", namespaces=ns)
            title = entry.findtext("atom:title", namespaces=ns)
            if video_id and title:
                videos.append({
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "video_id": video_id,
                })

        return videos
    except Exception:
        return []
