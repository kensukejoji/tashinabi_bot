"""
嗜美Bot — メインGUIアプリ

起動方法:
    streamlit run app.py
"""
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from src.database import repository
from src.database.models import VALID_CATEGORIES, VALID_PLATFORMS, PostQueue, PostStats, Product
from src.generator.prompts import PATTERNS

# ─────────────────────────────────────────
# ページ設定（必ず最初に呼ぶ）
# ─────────────────────────────────────────
st.set_page_config(
    page_title="嗜美Bot",
    page_icon="🍵",
    layout="wide",
)

repository.init_db()

# ─────────────────────────────────────────
# 定数
# ─────────────────────────────────────────
PATTERN_LABELS = {
    "news": "ニュース紹介型",
    "tips": "Tips型",
    "experience": "体験共有型",
    "data": "データ型",
    "youtube": "YouTube紹介型",
}
PATTERN_LABELS_INV = {v: k for k, v in PATTERN_LABELS.items()}
CHART_COLOR = px.colors.qualitative.Pastel

# ─────────────────────────────────────────
# カスタムCSS
# ─────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .stRadio > div { gap: 0.3rem; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; }
    .post-box {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.5rem;
        white-space: pre-wrap;
        font-size: 0.95rem;
        line-height: 1.6;
    }
    .success-banner {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 6px;
        padding: 0.8rem 1rem;
        color: #155724;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# サイドバー ナビゲーション
# ─────────────────────────────────────────
st.sidebar.image("https://em-content.zobj.net/source/twitter/376/teacup-without-handle_1f375.png", width=60)
st.sidebar.title("嗜美Bot")
st.sidebar.markdown("---")

PAGE_NAMES = [
    "📊 ダッシュボード",
    "📰 今日のニュース",
    "📅 投稿スケジュール",
    "✍️ 投稿を生成",
    "📋 投稿一覧",
    "🛒 商品管理",
    "📈 エンゲージメント入力",
    "⚙️ 設定確認",
]
page = st.sidebar.radio("ナビゲーション", PAGE_NAMES, label_visibility="collapsed")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 データを更新"):
    st.cache_data.clear()
    st.rerun()

# ─────────────────────────────────────────
# データ読み込みヘルパー
# ─────────────────────────────────────────
@st.cache_data(ttl=30)
def load_stats() -> pd.DataFrame:
    rows = repository.list_post_stats_with_posts()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["pattern_label"] = df["pattern"].map(PATTERN_LABELS).fillna(df["pattern"])
    df["platform_label"] = df["platform"].map({"x": "X", "instagram": "Instagram", "facebook": "Facebook"}).fillna(df["platform"])
    df["recorded_at"] = pd.to_datetime(df["recorded_at"])
    df["hour"] = df["recorded_at"].dt.hour
    df["engagement"] = df["likes"] + df["reposts"] + df["comments"]
    return df


@st.cache_data(ttl=30)
def load_clicks() -> pd.DataFrame:
    rows = repository.list_clicks_with_products()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["clicked_at"] = pd.to_datetime(df["clicked_at"])
    return df


@st.cache_data(ttl=3600)
def load_youtube_videos() -> list[dict]:
    """YouTubeチャンネルの最新動画リストを取得（1時間キャッシュ）"""
    from src.youtube_fetcher import fetch_channel_videos
    return fetch_channel_videos()


@st.cache_data(ttl=1800)
def load_news() -> list[dict]:
    """ニュース記事を取得（30分キャッシュ）"""
    from src.news_fetcher import fetch_news
    return fetch_news()


# ═══════════════════════════════════════════════════════════════════
# PAGE: ダッシュボード
# ═══════════════════════════════════════════════════════════════════
if page == "📊 ダッシュボード":
    st.title("📊 ダッシュボード")

    df_stats = load_stats()
    df_clicks = load_clicks()

    # KPI
    col1, col2, col3, col4 = st.columns(4)
    total_posts       = len(repository.list_posts())
    total_likes       = int(df_stats["likes"].sum())        if not df_stats.empty else 0
    total_impressions = int(df_stats["impressions"].sum())  if not df_stats.empty else 0
    total_clicks      = len(df_clicks)

    col1.metric("総投稿数",              f"{total_posts} 件")
    col2.metric("累計いいね",            f"{total_likes:,}")
    col3.metric("累計インプレッション",    f"{total_impressions:,}")
    col4.metric("アフィリエイトクリック",  f"{total_clicks:,}")

    st.markdown("---")

    if df_stats.empty:
        st.info("エンゲージメントデータがまだありません。「✍️ 投稿を生成」から投稿を作成し、「📈 エンゲージメント入力」でデータを登録してください。")
        st.stop()

    # 投稿タイプ別エンゲージメント
    row1_l, row1_r = st.columns([3, 2])

    with row1_l:
        st.subheader("📈 投稿タイプ別 エンゲージメント比較")
        pattern_agg = (
            df_stats.groupby("pattern_label")[["likes", "reposts", "comments"]]
            .sum().reset_index()
        )
        fig = go.Figure()
        for metric, color, label in [
            ("likes", "#FF6B6B", "いいね"),
            ("reposts", "#4ECDC4", "リポスト"),
            ("comments", "#45B7D1", "コメント"),
        ]:
            fig.add_trace(go.Bar(name=label, x=pattern_agg["pattern_label"],
                                  y=pattern_agg[metric], marker_color=color))
        fig.update_layout(barmode="group", height=350, xaxis_title="投稿タイプ",
                          yaxis_title="件数", legend_title="指標")
        st.plotly_chart(fig, use_container_width=True)

    with row1_r:
        st.subheader("🏆 人気投稿 TOP5")
        top = (
            df_stats.groupby(["post_id", "pattern_label", "x_content"])["engagement"]
            .sum().reset_index().sort_values("engagement", ascending=False)
            .head(5).reset_index(drop=True)
        )
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, row in top.iterrows():
            st.markdown(
                f"{medals[i]} **[{row['pattern_label']}]** {row['x_content'][:40]}…  "
                f"`{int(row['engagement']):,}`"
            )

    st.markdown("---")

    # クリック & 時間帯
    row2_l, row2_r = st.columns(2)

    with row2_l:
        st.subheader("🛒 商品別クリック数")
        if df_clicks.empty:
            st.info("クリックデータがありません。redirect_server.py を起動してリンクをテストしてください。")
        else:
            cr = df_clicks.groupby("product_name").size().reset_index(name="クリック数").sort_values("クリック数", ascending=False)
            fig2 = px.bar(cr, x="product_name", y="クリック数",
                          color="product_name", color_discrete_sequence=CHART_COLOR,
                          labels={"product_name": "商品名"})
            fig2.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig2, use_container_width=True)

    with row2_r:
        st.subheader("🕐 時間帯別 エンゲージメント")
        hourly = df_stats.groupby("hour")["engagement"].sum().reset_index()
        all_hours = pd.DataFrame({"hour": range(24)})
        hourly = all_hours.merge(hourly, on="hour", how="left").fillna(0)
        fig3 = px.line(hourly, x="hour", y="engagement", markers=True,
                       labels={"hour": "時間帯", "engagement": "合計"},
                       color_discrete_sequence=["#4ECDC4"])
        fig3.update_layout(height=300, xaxis=dict(tickmode="linear", tick0=0, dtick=3))
        st.plotly_chart(fig3, use_container_width=True)

    st.markdown("---")

    # インサイト
    st.subheader("💡 投稿戦略インサイト")
    ins1, ins2, ins3 = st.columns(3)
    best_pattern = df_stats.groupby("pattern_label")["engagement"].sum().idxmax()
    ins1.metric("最高エンゲージメント パターン", best_pattern)
    if hourly["engagement"].sum() > 0:
        best_hour = int(hourly.loc[hourly["engagement"].idxmax(), "hour"])
        ins2.metric("最高エンゲージメント 時間帯", f"{best_hour}:00〜{best_hour+1}:00")
    else:
        ins2.metric("最高エンゲージメント 時間帯", "—")
    if not df_clicks.empty:
        ins3.metric("最多クリック 商品", df_clicks["product_name"].value_counts().idxmax())
    else:
        ins3.metric("最多クリック 商品", "—")


# ═══════════════════════════════════════════════════════════════════
# PAGE: 今日のニュース
# ═══════════════════════════════════════════════════════════════════
elif page == "📰 今日のニュース":
    st.title("📰 今日のニュース")
    st.caption("気になる記事にチェックを入れて優先度を設定 → 一括で投稿文を生成してスケジュール登録できます。")

    # ── ヘッダー ──────────────────────────────────────────────────
    col_h1, col_h2 = st.columns([4, 1])
    with col_h2:
        if st.button("🔄 ニュースを更新", use_container_width=True):
            load_news.clear()
            st.rerun()

    with st.spinner("ニュースを収集中..."):
        articles = load_news()

    if not articles:
        st.warning("ニュースの取得に失敗しました。しばらくしてから「ニュースを更新」を試してください。")
        st.stop()

    st.success(f"✓ {len(articles)} 件のニュースを取得しました")
    st.markdown("---")

    # ── カテゴリフィルター ────────────────────────────────────────
    categories = sorted(set(a["category"] for a in articles))
    selected_cats = st.multiselect(
        "カテゴリで絞り込み",
        options=categories,
        default=categories,
    )
    filtered = [a for a in articles if a["category"] in selected_cats]
    st.caption(f"{len(filtered)} 件表示中　　チェックした記事から投稿を一括生成できます")
    st.markdown("---")

    # ── 記事一覧（チェックボックス＋優先度＋サムネイル） ─────────
    checked_articles = []
    for i, article in enumerate(filtered):
        chk_col, pri_col, info_col = st.columns([0.5, 0.8, 9])
        with chk_col:
            checked = st.checkbox("", key=f"chk_{i}", label_visibility="collapsed")
        with pri_col:
            priority = st.number_input(
                "優先度", min_value=1, max_value=99, value=i + 1,
                key=f"pri_{i}", label_visibility="collapsed",
            )
        with info_col:
            og_image = article.get("og_image")
            img_html = (
                f'<img src="{og_image}" style="'
                f'width:140px;min-width:140px;border-radius:6px;'
                f'float:left;margin-right:14px;margin-bottom:6px;object-fit:cover;" />'
                if og_image else ""
            )
            summary_html = (
                f'<p style="color:#555;font-size:0.83rem;margin:4px 0 0 0;">'
                f'{article["summary"][:180]}</p>'
                if article.get("summary") else ""
            )
            st.markdown(
                f'<div style="overflow:hidden;min-height:80px;">'
                f'{img_html}'
                f'<strong><a href="{article["url"]}" target="_blank" style="font-size:1rem;">'
                f'{article["title"]}</a></strong><br/>'
                f'<span style="color:#999;font-size:0.82rem;">'
                f'{article["category"]} ／ {article.get("source","")} ／ {article.get("published","")[:10]}'
                f'</span>'
                f'{summary_html}'
                f'</div>',
                unsafe_allow_html=True,
            )

        if checked:
            checked_articles.append((priority, article))

        st.markdown("---")

    # ── 一括生成パネル ────────────────────────────────────────────
    if checked_articles:
        # 優先度順にソート
        checked_articles.sort(key=lambda x: x[0])
        top_articles = [a for _, a in checked_articles[:5]]  # 最大5件

        st.markdown("### ✅ 選択中の記事")
        for idx, art in enumerate(top_articles, 1):
            st.markdown(f"**{idx}.** {art['title']}")

        st.markdown("---")
        st.markdown("#### 📅 投稿スケジュール設定")

        import datetime as dt
        today = dt.date.today()
        sch_col1, sch_col2, sch_col3 = st.columns(3)

        with sch_col1:
            post_date = st.date_input("投稿日", value=today, key="bulk_date")
        with sch_col2:
            platform_choice = st.selectbox(
                "投稿先", ["X（Twitter）", "Instagram", "Facebook", "両方"], key="bulk_platform"
            )
        with sch_col3:
            time_slots = ["朝 09:00", "昼 12:00", "夕 18:00", "夜 21:00", "カスタム"]
            slot_choice = st.selectbox("時間帯", time_slots, key="bulk_timeslot")

        # カスタム時間
        if slot_choice == "カスタム":
            custom_times = []
            for idx in range(len(top_articles)):
                t = st.time_input(
                    f"記事{idx+1}の投稿時刻",
                    value=dt.time(9 + idx * 3, 0),
                    key=f"custom_time_{idx}",
                )
                custom_times.append(t)
        else:
            slot_map = {
                "朝 09:00": [dt.time(9, 0), dt.time(12, 0), dt.time(18, 0), dt.time(21, 0), dt.time(9, 0)],
                "昼 12:00": [dt.time(12, 0), dt.time(15, 0), dt.time(18, 0), dt.time(21, 0), dt.time(12, 0)],
                "夕 18:00": [dt.time(18, 0), dt.time(19, 0), dt.time(20, 0), dt.time(21, 0), dt.time(18, 0)],
                "夜 21:00": [dt.time(21, 0), dt.time(21, 30), dt.time(22, 0), dt.time(22, 30), dt.time(21, 0)],
            }
            base_times = slot_map.get(slot_choice, [dt.time(9, 0)] * 5)
            # 記事ごとに1時間ずつずらす
            custom_times = []
            for idx in range(len(top_articles)):
                h = (base_times[0].hour + idx * 3) % 24
                custom_times.append(dt.time(h, 0))

        platform_key = {"X（Twitter）": "x", "Instagram": "instagram", "Facebook": "facebook", "両方": "both"}[platform_choice]

        # ── STEP 1: 生成ボタン ───────────────────────────────────────
        if st.button("✍️ 投稿文を生成してプレビュー", type="primary", use_container_width=True):
            from src.generator.post_generator import generate_post

            progress = st.progress(0)
            drafts = []
            for idx, article in enumerate(top_articles):
                progress.progress((idx + 1) / len(top_articles))
                with st.spinner(f"({idx+1}/{len(top_articles)}) 「{article['title'][:30]}…」の投稿文を生成中..."):
                    try:
                        result = generate_post(news_article=article)
                        scheduled_dt = dt.datetime.combine(post_date, custom_times[idx])
                        drafts.append({
                            "article_title": article["title"],
                            "scheduled_dt": scheduled_dt,
                            "platform": platform_key,
                            "post_id": result.saved_post_id,
                            "x_text": result.x_post_with_url,
                            "ig_text": result.instagram_post_with_url,
                        })
                        # テキストエリアの初期値をsession_stateにセット
                        st.session_state[f"news_x_{idx}"] = result.x_post_with_url
                        st.session_state[f"news_ig_{idx}"] = result.instagram_post_with_url
                    except Exception as e:
                        st.error(f"記事{idx+1} エラー: {e}")
                        with st.expander("詳細エラー情報"):
                            st.code(traceback.format_exc())

            progress.empty()
            st.session_state["news_drafts"] = drafts
            st.cache_data.clear()
            if drafts:
                st.success(f"✓ {len(drafts)} 件の投稿文を生成しました。下で確認・編集してからスケジュール登録してください。")

        # ── STEP 2: プレビュー・編集・スケジュール登録 ───────────────
        drafts = st.session_state.get("news_drafts", [])
        if drafts:
            st.markdown("---")
            st.markdown("### 📝 生成された投稿文（編集可）")

            for i, draft in enumerate(drafts):
                with st.expander(
                    f"記事{i+1}: {draft['article_title'][:50]}…  "
                    f"📅 {draft['scheduled_dt'].strftime('%m/%d %H:%M')}",
                    expanded=True,
                ):
                    tab_x, tab_ig = st.tabs(["🐦 X投稿文", "📷 Instagram投稿文"])
                    with tab_x:
                        st.text_area(
                            "X", key=f"news_x_{i}", height=160,
                            label_visibility="collapsed",
                        )
                        x_len = len(st.session_state.get(f"news_x_{i}", ""))
                        color = "green" if x_len <= 140 else "red"
                        st.markdown(
                            f"<span style='color:{color}'>文字数: {x_len} / 140</span>",
                            unsafe_allow_html=True,
                        )
                    with tab_ig:
                        st.text_area(
                            "IG", key=f"news_ig_{i}", height=200,
                            label_visibility="collapsed",
                        )

            st.markdown("---")
            col_cancel, col_schedule = st.columns([1, 3])
            with col_cancel:
                if st.button("✖️ キャンセル", use_container_width=True):
                    st.session_state.pop("news_drafts", None)
                    st.rerun()
            with col_schedule:
                if st.button("📅 スケジュール登録", type="primary", use_container_width=True):
                    success_count = 0
                    for i, draft in enumerate(drafts):
                        try:
                            edited_x  = st.session_state.get(f"news_x_{i}", draft["x_text"])
                            edited_ig = st.session_state.get(f"news_ig_{i}", draft["ig_text"])
                            # 編集内容をDBに反映
                            if draft["post_id"]:
                                repository.update_post_content(draft["post_id"], edited_x, edited_ig)
                            # キューに追加
                            repository.add_to_queue(PostQueue(
                                post_id=draft["post_id"],
                                platform=draft["platform"],
                                scheduled_at=draft["scheduled_dt"].isoformat(),
                            ))
                            success_count += 1
                            st.success(
                                f"✓ 記事{i+1}: {draft['article_title'][:35]}… "
                                f"→ {draft['scheduled_dt'].strftime('%m/%d %H:%M')} にスケジュール登録"
                            )
                        except Exception as e:
                            st.error(f"記事{i+1} スケジュール登録エラー: {e}")

                    if success_count > 0:
                        st.session_state.pop("news_drafts", None)
                        st.cache_data.clear()
                        st.balloons()
                        st.success(f"✅ {success_count} 件の投稿をスケジュール登録しました！「📅 投稿スケジュール」ページで確認できます。")


# ═══════════════════════════════════════════════════════════════════
# PAGE: 投稿スケジュール
# ═══════════════════════════════════════════════════════════════════
elif page == "📅 投稿スケジュール":
    import datetime as dt
    st.title("📅 投稿スケジュール")
    st.caption("登録済みの投稿予約を確認・管理します。`auto_post.py` を cron で動かすと自動投稿されます。")

    queue_rows = repository.list_queue_with_posts()

    if not queue_rows:
        st.info("スケジュール登録された投稿がありません。「📰 今日のニュース」ページで記事を選んで一括生成してください。")
        st.stop()

    # ステータスフィルター
    status_filter = st.radio(
        "ステータス",
        ["すべて", "pending（待機中）", "posted（投稿済）", "failed（失敗）"],
        horizontal=True,
    )
    status_map = {
        "すべて": None,
        "pending（待機中）": "pending",
        "posted（投稿済）": "posted",
        "failed（失敗）": "failed",
    }
    filter_status = status_map[status_filter]

    filtered_queue = [r for r in queue_rows if filter_status is None or r["status"] == filter_status]
    st.caption(f"{len(filtered_queue)} 件")
    st.markdown("---")

    STATUS_ICONS = {"pending": "⏳", "posted": "✅", "failed": "❌"}
    PLATFORM_LABELS = {"x": "🐦 X", "instagram": "📷 IG", "facebook": "📘 FB", "both": "🐦📷 両方"}

    now_iso = dt.datetime.now().isoformat()

    for row in filtered_queue:
        status_icon = STATUS_ICONS.get(row["status"], "")
        platform_label = PLATFORM_LABELS.get(row["platform"], row["platform"])
        scheduled = row["scheduled_at"][:16].replace("T", " ")
        is_overdue = row["status"] == "pending" and row["scheduled_at"] < now_iso

        with st.expander(
            f"{status_icon} {scheduled}　{platform_label}　"
            f"[{PATTERN_LABELS.get(row['pattern'], row['pattern'])}]　"
            f"{row['x_content'][:40]}…",
            expanded=False,
        ):
            tab_x, tab_ig = st.tabs(["🐦 X投稿文", "📷 Instagram投稿文"])
            with tab_x:
                sq_x_key = f"sq_x_{row['queue_id']}"
                if sq_x_key not in st.session_state:
                    st.session_state[sq_x_key] = row["x_content"]
                st.text_area("X", key=sq_x_key, height=120, label_visibility="collapsed",
                             disabled=(row["status"] == "posted"))
                if row["status"] != "posted":
                    x_len = len(st.session_state.get(sq_x_key, ""))
                    color = "green" if x_len <= 140 else "red"
                    st.markdown(f"<span style='color:{color}'>文字数: {x_len} / 140</span>", unsafe_allow_html=True)
            with tab_ig:
                sq_ig_key = f"sq_ig_{row['queue_id']}"
                if sq_ig_key not in st.session_state:
                    st.session_state[sq_ig_key] = row["ig_content"]
                st.text_area("IG", key=sq_ig_key, height=160, label_visibility="collapsed",
                             disabled=(row["status"] == "posted"))

            meta1, meta2, meta3 = st.columns(3)
            meta1.caption(f"スケジュール: {scheduled}")
            meta2.caption(f"ステータス: {row['status']}")
            meta3.caption(f"post_id: {row['post_id']}")
            if row.get("error_msg"):
                st.warning(f"エラー: {row['error_msg']}")

            # 編集保存ボタン（pending/failedのみ）
            if row["status"] != "posted":
                if st.button("💾 編集を保存", key=f"save_{row['queue_id']}"):
                    repository.update_post_content(
                        row["post_id"],
                        st.session_state.get(f"sq_x_{row['queue_id']}", row["x_content"]),
                        st.session_state.get(f"sq_ig_{row['queue_id']}", row["ig_content"]),
                    )
                    st.success("✓ 保存しました")

            btn1, btn2, btn3 = st.columns(3)

            # 今すぐ投稿
            if row["status"] in ("pending", "failed"):
                if btn1.button("▶️ 今すぐ投稿", key=f"now_{row['queue_id']}"):
                    from src.sns import x_client, instagram_client, facebook_client
                    post = repository.get_post(row["post_id"])
                    errors = []
                    if row["platform"] in ("x", "both"):
                        try:
                            tid = x_client.post_tweet(post.x_content)
                            repository.update_post_sns_ids(post.id, tweet_id=tid)
                        except Exception as e:
                            errors.append(f"X: {e}")
                    if row["platform"] in ("instagram", "both"):
                        try:
                            igid = instagram_client.post_text_only(post.ig_content)
                            repository.update_post_sns_ids(post.id, ig_media_id=igid)
                        except Exception as e:
                            errors.append(f"IG: {e}")
                    if row["platform"] == "facebook":
                        try:
                            fbid = facebook_client.post_text(post.ig_content)
                            repository.update_post_sns_ids(post.id, fb_post_id=fbid)
                        except Exception as e:
                            errors.append(f"FB: {e}")
                    if errors:
                        repository.update_queue_status(row["queue_id"], "failed", error_msg="; ".join(errors))
                        st.error("; ".join(errors))
                    else:
                        repository.update_queue_status(row["queue_id"], "posted")
                        st.success("✅ 投稿しました！")
                        st.rerun()

            # 削除
            if btn3.button("🗑️ 削除", key=f"del_{row['queue_id']}"):
                repository.delete_queue_item(row["queue_id"])
                st.rerun()

        if is_overdue:
            st.warning("⚠️ スケジュール時刻を過ぎています")


# ═══════════════════════════════════════════════════════════════════
# PAGE: 投稿を生成
# ═══════════════════════════════════════════════════════════════════
elif page == "✍️ 投稿を生成":
    st.title("✍️ 投稿を生成")

    # 設定パネル
    with st.expander("⚙️ 生成オプション", expanded=True):
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            pattern_choice = st.selectbox(
                "投稿パターン",
                ["ランダム"] + [PATTERN_LABELS[p] for p in PATTERNS],
                help="どの型で投稿を生成するか選択します"
            )
        with col_opt2:
            category_choice = st.selectbox(
                "商品カテゴリ絞り込み",
                ["すべて"] + VALID_CATEGORIES,
                help="紐づける商品のカテゴリを絞り込めます"
            )

        # YouTube動画選択（YouTube紹介型またはランダム時に表示）
        is_youtube = pattern_choice in ("YouTube紹介型", "ランダム")
        youtube_url_input = ""
        if is_youtube:
            st.markdown("##### 🎥 YouTube動画（任意）")
            yt_videos = load_youtube_videos()

            if yt_videos:
                video_map = {"（YouTubeなし）": ""}
                for v in yt_videos:
                    video_map[f"🎥 {v['title']}"] = v["url"]

                yt_col, refresh_col = st.columns([5, 1])
                with yt_col:
                    selected_label = st.selectbox(
                        "動画を選択",
                        list(video_map.keys()),
                        key="yt_video_select",
                        label_visibility="collapsed",
                    )
                with refresh_col:
                    if st.button("🔄", help="動画リストを更新", key="yt_refresh"):
                        load_youtube_videos.clear()
                        st.rerun()

                youtube_url_input = video_map[selected_label]
                if youtube_url_input:
                    st.caption(f"🔗 {youtube_url_input}")
            else:
                # 取得失敗時はテキスト入力にフォールバック
                st.warning("動画リストの取得に失敗しました。URLを直接入力してください。")
                youtube_url_input = st.text_input(
                    "YouTube動画URL",
                    placeholder="https://www.youtube.com/watch?v=XXXXXXX",
                    key="yt_manual_input",
                    label_visibility="collapsed",
                )

    if st.button("🚀 投稿文を生成", type="primary", use_container_width=True):
        from src.generator.post_generator import generate_post

        selected_pattern = None if pattern_choice == "ランダム" else PATTERN_LABELS_INV[pattern_choice]
        selected_category = None if category_choice == "すべて" else category_choice
        youtube_url = youtube_url_input.strip() if youtube_url_input else None

        with st.spinner("Claude AIが投稿文を生成中..."):
            try:
                result = generate_post(
                    pattern=selected_pattern,
                    category_filter=selected_category,
                    youtube_url=youtube_url,
                )
                st.session_state["last_result"] = result
                st.cache_data.clear()
                st.success("投稿文を生成しました！")
            except Exception as e:
                st.error(f"生成エラー: {e}")
                with st.expander("詳細エラー情報"):
                    st.code(traceback.format_exc())
                st.stop()

    # 生成結果の表示
    result = st.session_state.get("last_result")
    if result:
        st.markdown("---")
        st.subheader(f"生成結果 — パターン: {PATTERN_LABELS.get(result.pattern, result.pattern)}")

        # 新しい生成結果の場合のみテキストエリアの初期値をリセット
        if st.session_state.get("_last_result_id") != result.saved_post_id:
            st.session_state["edit_x_text"] = result.x_post_with_url
            st.session_state["edit_ig_text"] = result.instagram_post_with_url
            st.session_state["_last_result_id"] = result.saved_post_id

        col_x, col_ig = st.columns(2)

        with col_x:
            st.markdown("#### 🐦 X（Twitter）投稿文　✏️ 編集可")
            edited_x = st.text_area(
                "X投稿文",
                key="edit_x_text",
                height=220,
                label_visibility="collapsed",
            )
            x_len = len(edited_x)
            color = "green" if x_len <= 140 else "red"
            st.markdown(f"<span style='color:{color}'>文字数: {x_len} / 140</span>", unsafe_allow_html=True)

        with col_ig:
            st.markdown("#### 📷 Instagram 投稿文　✏️ 編集可")
            edited_ig = st.text_area(
                "Instagram投稿文",
                key="edit_ig_text",
                height=220,
                label_visibility="collapsed",
            )
            st.caption(f"文字数: {len(edited_ig)}")

        if result.youtube_url:
            title_text = f"「{result.youtube_title}」" if result.youtube_title else ""
            st.info(f"🎥 YouTube動画 {title_text}: {result.youtube_url}")

        if result.matched_product:
            st.info(f"🛒 紐づけ商品: **{result.matched_product.name}** ({result.matched_product.category})")
        else:
            st.warning("紐づけ商品: 該当なし。商品管理ページで商品を登録してください。")

        if result.saved_post_id:
            st.caption(f"DB保存済み: post_id = {result.saved_post_id}")

        # 編集内容をDBに保存するボタン
        if st.button("💾 編集内容をDBに保存", use_container_width=False):
            if result.saved_post_id:
                repository.update_post_content(
                    result.saved_post_id,
                    st.session_state.get("edit_x_text", result.x_post_with_url),
                    st.session_state.get("edit_ig_text", result.instagram_post_with_url),
                )
                st.success("✓ 編集内容を保存しました")

        # SNS投稿ボタン
        st.markdown("---")
        st.subheader("📤 SNSに投稿する")
        st.caption("上で編集したテキストがそのまま投稿されます。")

        pub_col1, pub_col2, pub_col3 = st.columns(3)

        with pub_col1:
            if st.button("🐦 Xに投稿する", use_container_width=True):
                from src.sns import x_client
                if not x_client.check_credentials():
                    st.error("X APIキーが .env に設定されていません。⚙️ 設定確認 ページを確認してください。")
                else:
                    with st.spinner("Xに投稿中..."):
                        try:
                            x_text = st.session_state.get("edit_x_text", result.x_post_with_url)
                            tweet_id = x_client.post_tweet(x_text)
                            if result.saved_post_id:
                                repository.update_post_sns_ids(result.saved_post_id, tweet_id=tweet_id)
                                repository.update_post_content(result.saved_post_id, x_text,
                                    st.session_state.get("edit_ig_text", result.instagram_post_with_url))
                            st.success(f"✓ X投稿完了！ tweet_id: {tweet_id}")
                        except Exception as e:
                            st.error(f"X投稿エラー: {e}")

        with pub_col2:
            if st.button("📷 Instagramに投稿する", use_container_width=True):
                from src.sns import instagram_client
                from src.utils.image_resolver import resolve_image_url
                if not instagram_client.check_credentials():
                    st.error("Instagram APIキーが .env に設定されていません。⚙️ 設定確認 ページを確認してください。")
                else:
                    with st.spinner("Instagramに投稿中..."):
                        try:
                            ig_text = st.session_state.get("edit_ig_text", result.instagram_post_with_url)
                            with st.spinner("画像を取得中..."):
                                image_url = resolve_image_url(
                                    product_image_url=result.matched_product.image_url if result.matched_product else None,
                                    youtube_url=result.youtube_url,
                                    news_url=result.news_url,
                                    keywords=result.suggested_category or "ソバーキュリアス 健康",
                                )
                            if image_url:
                                ig_id = instagram_client.post_image(ig_text, image_url)
                            else:
                                ig_id = instagram_client.post_text_only(ig_text)
                            if result.saved_post_id:
                                repository.update_post_sns_ids(result.saved_post_id, ig_media_id=ig_id)
                                repository.update_post_content(result.saved_post_id,
                                    st.session_state.get("edit_x_text", result.x_post_with_url), ig_text)
                            st.success(f"✓ Instagram投稿完了！ media_id: {ig_id}")
                        except NotImplementedError as e:
                            st.warning(str(e))
                        except Exception as e:
                            st.error(f"Instagram投稿エラー: {e}")

        with pub_col3:
            if st.button("📘 Facebookに投稿する", use_container_width=True):
                from src.sns import facebook_client
                from src.utils.image_resolver import resolve_image_url
                if not facebook_client.check_credentials():
                    st.error("Facebook APIキーが .env に設定されていません。⚙️ 設定確認 ページを確認してください。")
                else:
                    with st.spinner("Facebookページに投稿中..."):
                        try:
                            fb_text = st.session_state.get("edit_ig_text", result.instagram_post_with_url)
                            with st.spinner("画像を取得中..."):
                                image_url = resolve_image_url(
                                    product_image_url=result.matched_product.image_url if result.matched_product else None,
                                    youtube_url=result.youtube_url,
                                    news_url=result.news_url,
                                    keywords=result.suggested_category or "ソバーキュリアス 健康",
                                )
                            if image_url:
                                fb_id = facebook_client.post_image(fb_text, image_url)
                            else:
                                fb_id = facebook_client.post_text(fb_text)
                            if result.saved_post_id:
                                repository.update_post_sns_ids(result.saved_post_id, fb_post_id=fb_id)
                            st.success(f"✓ Facebook投稿完了！ post_id: {fb_id}")
                        except Exception as e:
                            st.error(f"Facebook投稿エラー: {e}")


# ═══════════════════════════════════════════════════════════════════
# PAGE: 投稿一覧
# ═══════════════════════════════════════════════════════════════════
elif page == "📋 投稿一覧":
    st.title("📋 投稿一覧")

    posts = repository.list_posts()
    if not posts:
        st.info("投稿がまだありません。「✍️ 投稿を生成」ページで最初の投稿を作成してください。")
        st.stop()

    # フィルター
    filter_col1, filter_col2 = st.columns([2, 1])
    with filter_col1:
        pattern_filter = st.multiselect(
            "パターンで絞り込み",
            options=list(PATTERN_LABELS.values()),
            default=[],
        )
    with filter_col2:
        show_published = st.checkbox("SNS投稿済みのみ表示", value=False)

    st.caption(f"全 {len(posts)} 件")

    for post in posts:
        # フィルター適用
        if pattern_filter and PATTERN_LABELS.get(post.pattern) not in pattern_filter:
            continue
        if show_published and not (post.tweet_id or post.ig_media_id):
            continue

        with st.expander(
            f"[{PATTERN_LABELS.get(post.pattern, post.pattern)}] "
            f"{post.x_content[:50]}…  "
            f"（ID: {post.id} / {post.created_at[:10]}）",
            expanded=False,
        ):
            tab_x, tab_ig = st.tabs(["🐦 X投稿文", "📷 Instagram投稿文"])
            with tab_x:
                st.text_area("X投稿文", post.x_content, height=120, key=f"x_{post.id}", disabled=True, label_visibility="collapsed")
            with tab_ig:
                st.text_area("Instagram投稿文", post.ig_content, height=200, key=f"ig_{post.id}", disabled=True, label_visibility="collapsed")

            meta_col1, meta_col2, meta_col3 = st.columns(3)
            meta_col1.caption(f"生成日時: {post.created_at[:16].replace('T', ' ')}")
            meta_col2.caption(f"tweet_id: {post.tweet_id or '未投稿'}")
            meta_col3.caption(f"ig_media_id: {post.ig_media_id or '未投稿'}")
            if post.fb_post_id:
                st.caption(f"fb_post_id: {post.fb_post_id}")


# ═══════════════════════════════════════════════════════════════════
# PAGE: 商品管理
# ═══════════════════════════════════════════════════════════════════
elif page == "🛒 商品管理":
    st.title("🛒 商品管理")

    products = repository.list_products()

    # ── 商品一覧 ──────────────────────────────────────────────────
    st.subheader(f"登録済み商品 （{len(products)} 件）")

    if not products:
        st.info("商品が登録されていません。下のフォームから追加してください。")
    else:
        for prod in products:
            with st.expander(f"[{prod.category}] {prod.name}  (ID: {prod.id})", expanded=False):
                detail_col, btn_col = st.columns([4, 1])
                with detail_col:
                    st.markdown(f"**説明:** {prod.description}")
                    st.markdown(f"**URL:** {prod.affiliate_url}")
                    st.markdown(f"**画像URL:** {prod.image_url or '未設定'}")
                    st.caption(f"short_code: {prod.short_code or '—'} ／ 更新: {prod.updated_at[:10]}")
                with btn_col:
                    # 編集フォームのトグル
                    edit_key = f"edit_{prod.id}"
                    if st.button("✏️ 編集", key=f"btn_edit_{prod.id}"):
                        st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                    if st.button("🗑️ 削除", key=f"btn_del_{prod.id}"):
                        st.session_state[f"confirm_del_{prod.id}"] = True

                # 削除確認
                if st.session_state.get(f"confirm_del_{prod.id}"):
                    st.warning(f"「{prod.name}」を削除しますか？この操作は取り消せません。")
                    c1, c2 = st.columns(2)
                    if c1.button("はい、削除する", key=f"yes_del_{prod.id}", type="primary"):
                        repository.delete_product(prod.id)
                        st.session_state.pop(f"confirm_del_{prod.id}", None)
                        st.cache_data.clear()
                        st.success("削除しました。")
                        st.rerun()
                    if c2.button("キャンセル", key=f"no_del_{prod.id}"):
                        st.session_state.pop(f"confirm_del_{prod.id}", None)
                        st.rerun()

                # 編集フォーム
                if st.session_state.get(edit_key):
                    with st.form(key=f"form_edit_{prod.id}"):
                        st.markdown("**商品情報を編集**")
                        new_name = st.text_input("商品名", value=prod.name)
                        new_cat  = st.selectbox("カテゴリ", VALID_CATEGORIES,
                                                index=VALID_CATEGORIES.index(prod.category) if prod.category in VALID_CATEGORIES else 0)
                        new_desc = st.text_area("説明", value=prod.description, height=100)
                        new_url  = st.text_input("アフィリエイトURL", value=prod.affiliate_url)
                        new_img  = st.text_input("画像URL（任意）", value=prod.image_url or "")

                        if st.form_submit_button("💾 保存"):
                            try:
                                prod.name = new_name
                                prod.category = new_cat
                                prod.description = new_desc
                                prod.affiliate_url = new_url
                                prod.image_url = new_img or None
                                repository.update_product(prod)
                                st.session_state.pop(edit_key, None)
                                st.cache_data.clear()
                                st.success("更新しました！")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))

    st.markdown("---")

    # ── アフィリエイトURLビルダー ─────────────────────────────────
    st.subheader("🔗 アフィリエイトURLビルダー")
    st.caption("ASINや商品URLを入力するだけで、アフィリエイトリンクを自動生成します。")

    import os, urllib.parse
    from dotenv import load_dotenv
    load_dotenv()

    amz_tag      = os.environ.get("AMAZON_ASSOCIATE_TAG", "")
    rakuten_afid = os.environ.get("RAKUTEN_AFFILIATE_ID", "")

    builder_tab1, builder_tab2 = st.tabs(["🛍️ Amazon", "🛒 楽天"])

    with builder_tab1:
        if not amz_tag:
            st.warning("AMAZON_ASSOCIATE_TAG が .env に未設定です。⚙️ 設定確認ページで登録してください。")
        else:
            st.caption(f"使用タグ: `{amz_tag}`")

        amz_input = st.text_input(
            "ASIN または Amazon商品URL",
            placeholder="B0CXXXX または https://www.amazon.co.jp/dp/B0CXXXX",
            key="amz_builder_input",
        )
        if amz_input:
            # ASINを抽出（URLからでも直接でも）
            import re
            asin_match = re.search(r"/dp/([A-Z0-9]{10})", amz_input)
            asin = asin_match.group(1) if asin_match else amz_input.strip()
            tag  = amz_tag or "YOUR_TAG-22"
            amz_url = f"https://www.amazon.co.jp/dp/{asin}?tag={tag}"
            st.text_input("生成されたアフィリエイトURL", value=amz_url, key="amz_result")
            st.session_state["clipboard_url"] = amz_url

    with builder_tab2:
        if not rakuten_afid:
            st.warning("RAKUTEN_AFFILIATE_ID が .env に未設定です。")
        else:
            st.caption(f"使用ID: `{rakuten_afid}`")

        rakuten_input = st.text_input(
            "楽天商品URL",
            placeholder="https://item.rakuten.co.jp/...",
            key="rakuten_builder_input",
        )
        if rakuten_input:
            afid = rakuten_afid or "YOUR_AFFILIATE_ID"
            encoded = urllib.parse.quote(rakuten_input, safe="")
            rakuten_url = f"https://hb.afl.rakuten.co.jp/hgc/{afid}/?pc={encoded}"
            st.text_input("生成されたアフィリエイトURL", value=rakuten_url, key="rakuten_result")
            st.session_state["clipboard_url"] = rakuten_url

    st.markdown("---")

    # ── 商品追加フォーム ──────────────────────────────────────────
    st.subheader("➕ 新しい商品を追加")

    with st.form("add_product_form", clear_on_submit=True):
        f1, f2 = st.columns(2)
        with f1:
            add_name = st.text_input("商品名 *")
            add_cat  = st.selectbox("カテゴリ *", VALID_CATEGORIES)
            add_url  = st.text_input("アフィリエイトURL *")
        with f2:
            add_desc = st.text_area("説明 *", height=100)
            add_img  = st.text_input("画像URL（任意）")

        if st.form_submit_button("追加する", type="primary"):
            if not add_name or not add_url or not add_desc:
                st.error("商品名・説明・URLは必須です。")
            else:
                try:
                    new_product = Product(
                        name=add_name,
                        category=add_cat,
                        description=add_desc,
                        affiliate_url=add_url,
                        image_url=add_img or None,
                    )
                    saved = repository.add_product(new_product)
                    st.cache_data.clear()
                    st.success(f"「{saved.name}」を追加しました！（ID: {saved.id}）")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))


# ═══════════════════════════════════════════════════════════════════
# PAGE: エンゲージメント入力
# ═══════════════════════════════════════════════════════════════════
elif page == "📈 エンゲージメント入力":
    st.title("📈 エンゲージメント入力")

    posts = repository.list_posts()
    if not posts:
        st.info("投稿がありません。先に「✍️ 投稿を生成」から投稿を作成してください。")
        st.stop()

    tab_manual, tab_auto = st.tabs(["手動入力", "APIから自動取得"])

    # ── 手動入力タブ ──────────────────────────────────────────────
    with tab_manual:
        st.subheader("エンゲージメントを手動入力")

        post_options = {
            f"ID:{p.id} [{PATTERN_LABELS.get(p.pattern, p.pattern)}] {p.x_content[:40]}…": p.id
            for p in posts
        }

        selected_label = st.selectbox("投稿を選択", list(post_options.keys()))
        selected_post_id = post_options[selected_label]

        platform = st.radio("プラットフォーム", ["X（Twitter）", "Instagram", "Facebook"], horizontal=True)
        platform_key = {"X（Twitter）": "x", "Instagram": "instagram", "Facebook": "facebook"}[platform]

        with st.form("stats_form", clear_on_submit=True):
            s1, s2, s3, s4 = st.columns(4)
            likes       = s1.number_input("いいね数",         min_value=0, value=0, step=1)
            reposts     = s2.number_input("リポスト/シェア数", min_value=0, value=0, step=1)
            comments    = s3.number_input("コメント数",        min_value=0, value=0, step=1)
            impressions = s4.number_input("インプレッション数", min_value=0, value=0, step=1)

            if st.form_submit_button("💾 記録する", type="primary"):
                try:
                    stats = PostStats(
                        post_id=selected_post_id,
                        platform=platform_key,
                        likes=int(likes),
                        reposts=int(reposts),
                        comments=int(comments),
                        impressions=int(impressions),
                    )
                    saved = repository.add_post_stats(stats)
                    st.cache_data.clear()
                    st.success(f"✓ エンゲージメントを記録しました（stats_id: {saved.id}）")
                except ValueError as e:
                    st.error(str(e))

        # 既存の記録を表示
        st.markdown("---")
        st.subheader("記録済みエンゲージメント")
        all_stats = repository.list_post_stats_with_posts()
        if all_stats:
            df_s = pd.DataFrame(all_stats)
            df_s["パターン"] = df_s["pattern"].map(PATTERN_LABELS).fillna(df_s["pattern"])
            df_s["プラットフォーム"] = df_s["platform"].str.upper()
            df_s["記録日時"] = df_s["recorded_at"].str[:16].str.replace("T", " ")
            show_df = df_s[["post_id", "パターン", "プラットフォーム",
                             "likes", "reposts", "comments", "impressions", "記録日時"]]
            show_df = show_df.rename(columns={
                "post_id": "投稿ID", "likes": "いいね",
                "reposts": "リポスト", "comments": "コメント",
                "impressions": "インプレッション"
            })
            st.dataframe(show_df, use_container_width=True, hide_index=True)
        else:
            st.caption("記録がまだありません。")

    # ── API自動取得タブ ──────────────────────────────────────────
    with tab_auto:
        st.subheader("APIからエンゲージメントを自動取得")
        st.caption("X APIまたはInstagram Graph APIからデータを自動的に取得してDBに保存します。")

        published_posts = repository.list_published_posts()
        if not published_posts:
            st.warning("SNS投稿済みの投稿がありません。投稿生成ページで「SNSに投稿する」を実行してください。")
        else:
            target_platform = st.radio(
                "取得対象",
                ["両方", "X（Twitter）のみ", "Instagramのみ"],
                horizontal=True,
            )

            if st.button("📥 エンゲージメントを取得", type="primary"):
                from src.sns import x_client, instagram_client

                platform_map = {
                    "両方": None,
                    "X（Twitter）のみ": "x",
                    "Instagramのみ": "instagram",
                }
                target = platform_map[target_platform]

                x_ok  = x_client.check_credentials()
                ig_ok = instagram_client.check_credentials()
                success = skipped = 0

                progress = st.progress(0)
                for i, post in enumerate(published_posts):
                    progress.progress((i + 1) / len(published_posts))

                    if target in (None, "x") and post.tweet_id:
                        if not x_ok:
                            st.warning("X: APIキー未設定のためスキップ")
                        else:
                            try:
                                metrics = x_client.fetch_metrics(post.tweet_id)
                                repository.add_post_stats(PostStats(post_id=post.id, platform="x", **metrics))
                                st.success(f"✓ post_id={post.id} X: いいね={metrics['likes']} RT={metrics['reposts']}")
                                success += 1
                            except Exception as e:
                                st.error(f"post_id={post.id} X取得エラー: {e}")

                    if target in (None, "instagram") and post.ig_media_id:
                        if not ig_ok:
                            st.warning("Instagram: APIキー未設定のためスキップ")
                        else:
                            try:
                                metrics = instagram_client.fetch_insights(post.ig_media_id)
                                repository.add_post_stats(PostStats(post_id=post.id, platform="instagram", **metrics))
                                st.success(f"✓ post_id={post.id} IG: いいね={metrics['likes']}")
                                success += 1
                            except Exception as e:
                                st.error(f"post_id={post.id} IG取得エラー: {e}")

                progress.empty()
                st.cache_data.clear()
                st.info(f"完了: 成功 {success} 件 / スキップ {skipped} 件")


# ═══════════════════════════════════════════════════════════════════
# PAGE: 設定確認
# ═══════════════════════════════════════════════════════════════════
elif page == "⚙️ 設定確認":
    st.title("⚙️ 設定確認")
    st.caption(".env ファイルの各APIキーの設定状況を確認します（値は表示されません）。")

    import os
    from dotenv import load_dotenv
    load_dotenv()

    def check_key(key: str) -> bool:
        return bool(os.environ.get(key))

    def status_badge(ok: bool) -> str:
        return "✅ 設定済み" if ok else "❌ 未設定"

    st.subheader("Claude AI（投稿生成）")
    st.markdown(f"ANTHROPIC_API_KEY: **{status_badge(check_key('ANTHROPIC_API_KEY'))}**")

    st.markdown("---")
    st.subheader("X（Twitter）API")
    x_keys = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET", "X_BEARER_TOKEN"]
    for k in x_keys:
        st.markdown(f"{k}: **{status_badge(check_key(k))}**")

    st.markdown("---")
    st.subheader("Instagram Graph API")
    ig_keys = ["IG_USER_ID", "IG_ACCESS_TOKEN"]
    for k in ig_keys:
        st.markdown(f"{k}: **{status_badge(check_key(k))}**")

    st.markdown("---")
    st.subheader("Facebook Graph API（ページ投稿）")
    fb_keys = ["FB_PAGE_ID", "FB_PAGE_ACCESS_TOKEN"]
    for k in fb_keys:
        st.markdown(f"{k}: **{status_badge(check_key(k))}**")
    if not check_key("FB_PAGE_ID") or not check_key("FB_PAGE_ACCESS_TOKEN"):
        st.warning("Facebookページ投稿を使うには FB_PAGE_ID と FB_PAGE_ACCESS_TOKEN を .env に設定してください。")

    st.markdown("---")
    st.subheader("Amazonアソシエイト")
    amz_keys = ["AMAZON_ASSOCIATE_TAG", "AMAZON_CLIENT_ID", "AMAZON_CLIENT_SECRET"]
    for k in amz_keys:
        st.markdown(f"{k}: **{status_badge(check_key(k))}**")
    if not check_key("AMAZON_ASSOCIATE_TAG"):
        st.warning("AMAZON_ASSOCIATE_TAG が未設定です。Amazonアソシエイト管理画面のトラッキングIDを設定してください。")

    st.markdown("---")
    st.subheader("楽天アフィリエイト")
    rakuten_keys = ["RAKUTEN_APP_ID", "RAKUTEN_AFFILIATE_ID"]
    for k in rakuten_keys:
        st.markdown(f"{k}: **{status_badge(check_key(k))}**")

    st.markdown("---")
    st.subheader(".env ファイルの場所")
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        st.success(f"✓ .env ファイルが存在します: `{env_path}`")
    else:
        st.error(f".env ファイルが見つかりません: `{env_path}`")
        st.code("""# .env を作成するには:
cp .env.example .env
open -a TextEdit .env""", language="bash")

    st.markdown("---")
    st.subheader("APIキーの設定方法")
    with st.expander("X（Twitter）APIキーの取得・設定"):
        st.markdown("""
1. [X Developer Portal](https://developer.x.com/en/portal/dashboard) を開く
2. アプリを選択 → **「Keys and tokens」** タブ
3. 以下の値を `.env` に設定:
   - `X_API_KEY` / `X_API_SECRET`（API Key & Secret）
   - `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET`（Access Token & Secret）
   - `X_BEARER_TOKEN`（Bearer Token）
4. ⚠️ アプリのパーミッションが **「Read and Write」** になっているか確認
5. パーミッション変更後は **Access Token を再生成** する必要があります
        """)
    with st.expander("Instagram Graph APIキーの取得・設定"):
        st.markdown("""
1. [Meta for Developers](https://developers.facebook.com/) → あなたのアプリ
2. `IG_USER_ID`: InstagramのビジネスアカウントID（数字）
3. `IG_ACCESS_TOKEN`: Long-lived Access Token（有効期限約60日）
        """)
    with st.expander("Facebook Graph APIキーの取得・設定"):
        st.markdown("""
1. [Facebook](https://www.facebook.com) で **「嗜美」ページを作成**
2. [Meta for Developers](https://developers.facebook.com/) でアプリを作成（または既存のInstagramアプリを流用）
3. **Graph API Explorer** を開く → ページを選択 → Generate Access Token
4. 権限: `pages_manage_posts`, `pages_read_engagement` を付与
5. アクセストークンをツール上で **Long-lived token（長期トークン）に変換**（有効期限60日）
6. `.env` に以下を設定:
   - `FB_PAGE_ID`: FacebookページのID（ページURL または ページ設定で確認）
   - `FB_PAGE_ACCESS_TOKEN`: 上で取得したページアクセストークン
        """)
    with st.expander("Claude AIのAPIキーの取得・設定"):
        st.markdown("""
1. [Anthropic Console](https://console.anthropic.com/) → API Keys
2. 新しいキーを作成してコピー
3. `.env` の `ANTHROPIC_API_KEY` に設定
        """)
