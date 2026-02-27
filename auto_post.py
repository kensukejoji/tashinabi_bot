"""
自動投稿スクリプト。
post_queue テーブルの scheduled_at が現在時刻以前の pending 投稿を自動的にSNSに投稿する。

【設定方法】
# 毎分チェック（crontab -e で設定）:
* * * * * cd /Users/kensukejoji/aiworks/tashinabi_bot && python3 auto_post.py >> logs/auto_post.log 2>&1

# または5分ごと:
*/5 * * * * cd /Users/kensukejoji/aiworks/tashinabi_bot && python3 auto_post.py >> logs/auto_post.log 2>&1

【手動実行】
python3 auto_post.py

【ドライランモード（実際には投稿しない）】
python3 auto_post.py --dry-run
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from src.database import repository

# ログディレクトリを作成
Path("logs").mkdir(exist_ok=True)

DRY_RUN = "--dry-run" in sys.argv


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run() -> None:
    due_items = repository.list_due_queue()

    if not due_items:
        log("待機中の投稿なし")
        return

    log(f"{len(due_items)} 件の投稿を処理します")

    from src.sns import x_client, instagram_client

    for item in due_items:
        post = repository.get_post(item.post_id)
        if not post:
            log(f"  [SKIP] queue_id={item.id}: post_id={item.post_id} が見つかりません")
            repository.update_queue_status(item.id, "failed", error_msg="post not found")
            continue

        log(f"  [START] queue_id={item.id} platform={item.platform} post_id={item.post_id}")
        log(f"          内容: {post.x_content[:60]}…")

        if DRY_RUN:
            log(f"  [DRY-RUN] 実際の投稿はスキップ")
            continue

        errors = []

        # X に投稿
        if item.platform in ("x", "both"):
            if x_client.check_credentials():
                try:
                    tweet_id = x_client.post_tweet(post.x_content)
                    repository.update_post_sns_ids(post.id, tweet_id=tweet_id)
                    log(f"  [OK] X投稿完了 tweet_id={tweet_id}")
                except Exception as e:
                    errors.append(f"X: {e}")
                    log(f"  [ERR] X投稿失敗: {e}")
            else:
                errors.append("X: APIキー未設定")
                log("  [SKIP] X: APIキー未設定")

        # Instagram に投稿
        if item.platform in ("instagram", "both"):
            if instagram_client.check_credentials():
                try:
                    ig_id = instagram_client.post_text_only(post.ig_content)
                    repository.update_post_sns_ids(post.id, ig_media_id=ig_id)
                    log(f"  [OK] Instagram投稿完了 media_id={ig_id}")
                except Exception as e:
                    errors.append(f"IG: {e}")
                    log(f"  [ERR] Instagram投稿失敗: {e}")
            else:
                errors.append("Instagram: APIキー未設定")
                log("  [SKIP] Instagram: APIキー未設定")

        # ステータス更新
        if errors:
            repository.update_queue_status(item.id, "failed", error_msg="; ".join(errors))
        else:
            repository.update_queue_status(item.id, "posted")
            log(f"  [DONE] queue_id={item.id} → posted")

    log("処理完了")


if __name__ == "__main__":
    run()
