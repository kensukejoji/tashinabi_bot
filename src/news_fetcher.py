"""
ニュース収集モジュール。
Google News RSS フィードからノンアルコール・ヘルスケア関連ニュースを取得。
（APIキー不要）
"""

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

try:
    from googlenewsdecoder import gnewsdecoder as _gnewsdecoder
    _HAS_GNEWS_DECODER = True
except ImportError:
    _HAS_GNEWS_DECODER = False

# ─── 収集テーマ別検索クエリ ──────────────────────────────────────
SEARCH_QUERIES = [
    ("断酒・節酒", "断酒 OR 節酒 OR ソバーキュリアス"),
    ("ノンアルドリンク", "ノンアルコール 飲料 OR ノンアルドリンク OR ノンアルビール"),
    ("嗅覚・アロマ健康", "嗅覚 健康 OR アロマ 効果 OR ディフューザー ウェルネス"),
    ("睡眠・夜間心拍", "睡眠 質 改善 OR 夜間心拍 OR 睡眠 健康 研究"),
    ("老化防止・若返り", "老化防止 OR アンチエイジング OR 心臓 若返り"),
    ("ヘルスケアトレンド", "ウェルビーイング OR ヘルスケア トレンド 2025"),
    ("アルコール健康リスク", "アルコール 健康 リスク OR 飲酒 病気 研究"),
]

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _strip_html(text: str) -> str:
    """HTMLタグと余分な空白を除去"""
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _decode_google_news_url(url: str) -> str:
    """Google News RSS URLを実際の記事URLにデコードする"""
    if not _HAS_GNEWS_DECODER:
        return url
    if "news.google.com" not in url:
        return url
    try:
        result = _gnewsdecoder(url)
        if isinstance(result, dict) and result.get("status"):
            return result.get("decoded_url", url)
    except Exception:
        pass
    return url


def _fetch_og_image(url: str, timeout: int = 6) -> Optional[str]:
    """記事URLからOGP画像URLを取得する（Google News URLのデコード＋リダイレクト追跡）"""
    try:
        # Google News URL → 実際の記事URL に変換
        actual_url = _decode_google_news_url(url)

        req = urllib.request.Request(actual_url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # 先頭64KBのみ読み込み（全体取得を避けパフォーマンス向上）
            html = resp.read(65536).decode("utf-8", errors="ignore")

        # og:image メタタグを探す（属性順不同に対応）
        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                html, re.IGNORECASE,
            )
        # twitter:image も試す
        if not match:
            match = re.search(
                r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
                html, re.IGNORECASE,
            )
        return match.group(1) if match else None
    except Exception:
        return None


def fetch_news(
    queries: Optional[List[Tuple[str, str]]] = None,
    max_per_query: int = 4,
) -> List[dict]:
    """
    Google News RSS フィードからニュースを取得する。

    Args:
        queries: [(カテゴリ名, 検索クエリ), ...] のリスト。None なら SEARCH_QUERIES を使用。
        max_per_query: 各クエリから取得する最大件数。

    Returns:
        [{"title": str, "url": str, "source": str, "published": str,
          "summary": str, "category": str}, ...]
        取得失敗時は空リストを返す（例外は送出しない）。
    """
    if queries is None:
        queries = SEARCH_QUERIES

    articles: list[dict] = []
    seen_urls: set[str] = set()

    for category, query in queries:
        encoded = urllib.parse.quote(query)
        rss_url = (
            f"https://news.google.com/rss/search"
            f"?q={encoded}&hl=ja&gl=JP&ceid=JP:ja"
        )

        try:
            req = urllib.request.Request(rss_url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)

            for item in root.findall(".//item")[:max_per_query]:
                title = _strip_html(item.findtext("title") or "")
                url = item.findtext("link") or ""
                source = item.findtext("source") or ""
                pub_date = item.findtext("pubDate") or ""
                description = _strip_html(item.findtext("description") or "")

                # Google News の URL は t.co リダイレクト形式の場合があるためそのまま保持
                if not title or not url or url in seen_urls:
                    continue

                seen_urls.add(url)
                articles.append({
                    "title": title,
                    "url": url,
                    "source": str(source),
                    "published": pub_date[:22] if pub_date else "",
                    "summary": description[:250],
                    "category": category,
                    "og_image": None,  # 後で並列取得
                })

        except Exception:
            continue

    # ── OGP画像を並列取得 ────────────────────────────────────────
    if articles:
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_idx = {
                executor.submit(_fetch_og_image, a["url"]): i
                for i, a in enumerate(articles)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    articles[idx]["og_image"] = future.result()
                except Exception:
                    articles[idx]["og_image"] = None

    return articles
