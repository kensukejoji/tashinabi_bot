"""
ソバーキュリアスBot 分析ダッシュボード

起動方法:
    streamlit run dashboard.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from src.database import repository

# ─────────────────────────────────────────
# 定数
# ─────────────────────────────────────────
PATTERN_LABELS = {
    "news": "ニュース紹介型",
    "tips": "Tips型",
    "experience": "体験共有型",
    "data": "データ型",
}
PLATFORM_LABELS = {"x": "X（Twitter）", "instagram": "Instagram"}
CHART_COLOR = px.colors.qualitative.Pastel

# ─────────────────────────────────────────
# ページ設定
# ─────────────────────────────────────────
st.set_page_config(
    page_title="ソバーキュリアスBot ダッシュボード",
    page_icon="🍵",
    layout="wide",
)

repository.init_db()

# ─────────────────────────────────────────
# データ読み込み
# ─────────────────────────────────────────
@st.cache_data(ttl=30)
def load_stats() -> pd.DataFrame:
    rows = repository.list_post_stats_with_posts()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["pattern_label"] = df["pattern"].map(PATTERN_LABELS).fillna(df["pattern"])
    df["platform_label"] = df["platform"].map(PLATFORM_LABELS).fillna(df["platform"])
    df["recorded_at"] = pd.to_datetime(df["recorded_at"])
    df["hour"] = df["recorded_at"].dt.hour
    df["week"] = df["recorded_at"].dt.isocalendar().week.astype(int)
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


# ─────────────────────────────────────────
# サイドバー フィルター
# ─────────────────────────────────────────
st.sidebar.title("🍵 ソバーキュリアスBot")
st.sidebar.markdown("---")

platform_options = ["すべて", "X（Twitter）", "Instagram"]
platform_filter = st.sidebar.selectbox("プラットフォーム", platform_options)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 データを更新"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("""
**使い方**
1. `python3 main.py generate post` で投稿生成
2. `python3 main.py stats add <id>` でエンゲージメント入力
3. `python3 redirect_server.py` でクリック計測開始
""")

# ─────────────────────────────────────────
# メインコンテンツ
# ─────────────────────────────────────────
st.title("📊 ソバーキュリアスBot ダッシュボード")

df_stats = load_stats()
df_clicks = load_clicks()

# プラットフォームフィルター適用
if not df_stats.empty and platform_filter != "すべて":
    platform_map = {"X（Twitter）": "x", "Instagram": "instagram"}
    df_stats = df_stats[df_stats["platform"] == platform_map[platform_filter]]

# ─── KPI カード ───
col1, col2, col3, col4 = st.columns(4)

total_posts     = len(repository.list_posts())
total_likes     = int(df_stats["likes"].sum())        if not df_stats.empty else 0
total_impressions = int(df_stats["impressions"].sum()) if not df_stats.empty else 0
total_clicks    = len(df_clicks)

col1.metric("総投稿数",           f"{total_posts} 件")
col2.metric("累計いいね",         f"{total_likes:,}")
col3.metric("累計インプレッション", f"{total_impressions:,}")
col4.metric("アフィリエイトクリック", f"{total_clicks:,}")

st.markdown("---")

# ─────────────────────────────────────────
# データなし時のメッセージ
# ─────────────────────────────────────────
if df_stats.empty:
    st.info("""
    📭 **エンゲージメントデータがまだありません**

    以下の手順でデータを追加してください：
    1. `python3 main.py generate post` で投稿を生成
    2. `python3 main.py stats posts` で投稿IDを確認
    3. `python3 main.py stats add <post_id>` でエンゲージメントを入力
    """)

    # クリックデータだけあれば商品ランキングは表示
    if not df_clicks.empty:
        st.subheader("🛒 商品別クリック数ランキング")
        click_rank = df_clicks.groupby("product_name").size().reset_index(name="clicks")
        click_rank = click_rank.sort_values("clicks", ascending=False)
        fig = px.bar(click_rank, x="product_name", y="clicks",
                     color="product_name", color_discrete_sequence=CHART_COLOR,
                     labels={"product_name": "商品名", "clicks": "クリック数"})
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.stop()

# ─────────────────────────────────────────
# チャート Row 1: 投稿タイプ別 / 人気投稿ランキング
# ─────────────────────────────────────────
row1_left, row1_right = st.columns([3, 2])

with row1_left:
    st.subheader("📈 投稿タイプ別 エンゲージメント比較")
    pattern_agg = (
        df_stats.groupby("pattern_label")[["likes", "reposts", "comments", "impressions"]]
        .sum()
        .reset_index()
    )
    fig_pattern = go.Figure()
    for metric, color in zip(
        ["likes", "reposts", "comments"],
        ["#FF6B6B", "#4ECDC4", "#45B7D1"]
    ):
        label = {"likes": "いいね", "reposts": "リポスト", "comments": "コメント"}[metric]
        fig_pattern.add_trace(go.Bar(
            name=label,
            x=pattern_agg["pattern_label"],
            y=pattern_agg[metric],
            marker_color=color,
        ))
    fig_pattern.update_layout(
        barmode="group",
        xaxis_title="投稿タイプ",
        yaxis_title="件数",
        legend_title="指標",
        height=350,
    )
    st.plotly_chart(fig_pattern, use_container_width=True)

with row1_right:
    st.subheader("🏆 人気投稿ランキング TOP5")
    top_posts = (
        df_stats.groupby(["post_id", "pattern_label", "x_content"])["engagement"]
        .sum()
        .reset_index()
        .sort_values("engagement", ascending=False)
        .head(5)
        .reset_index(drop=True)
    )
    top_posts.index += 1
    top_posts["x_content_short"] = top_posts["x_content"].str[:40] + "..."
    top_posts["エンゲージメント合計"] = top_posts["engagement"]

    for i, row in top_posts.iterrows():
        medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i - 1]
        st.markdown(
            f"{medal} **[{row['pattern_label']}]** {row['x_content_short']}  "
            f"&nbsp; `{row['エンゲージメント合計']:,}`"
        )

st.markdown("---")

# ─────────────────────────────────────────
# チャート Row 2: 商品クリック / 時間帯別
# ─────────────────────────────────────────
row2_left, row2_right = st.columns(2)

with row2_left:
    st.subheader("🛒 商品別クリック数ランキング")
    if df_clicks.empty:
        st.info("クリックデータがありません。`python3 redirect_server.py` を起動してリンクをテストしてください。")
    else:
        click_rank = df_clicks.groupby("product_name").size().reset_index(name="クリック数")
        click_rank = click_rank.sort_values("クリック数", ascending=False)
        fig_clicks = px.bar(
            click_rank, x="product_name", y="クリック数",
            color="product_name", color_discrete_sequence=CHART_COLOR,
            labels={"product_name": "商品名"},
        )
        fig_clicks.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig_clicks, use_container_width=True)

with row2_right:
    st.subheader("🕐 時間帯別 エンゲージメント")
    hourly = df_stats.groupby("hour")["engagement"].sum().reset_index()
    # 0〜23時すべての行を補完
    all_hours = pd.DataFrame({"hour": range(24)})
    hourly = all_hours.merge(hourly, on="hour", how="left").fillna(0)
    fig_hourly = px.line(
        hourly, x="hour", y="engagement",
        markers=True,
        labels={"hour": "時間帯", "engagement": "エンゲージメント合計"},
        color_discrete_sequence=["#4ECDC4"],
    )
    fig_hourly.update_layout(height=300, xaxis=dict(tickmode="linear", tick0=0, dtick=3))
    st.plotly_chart(fig_hourly, use_container_width=True)

st.markdown("---")

# ─────────────────────────────────────────
# チャート Row 3: 週次トレンド
# ─────────────────────────────────────────
st.subheader("📅 週次トレンド推移")

weekly = (
    df_stats.groupby(["week", "pattern_label"])[["likes", "reposts", "comments"]]
    .sum()
    .reset_index()
)

if len(weekly["week"].unique()) < 2:
    st.info("週次トレンドは2週間以上のデータが必要です。データが蓄積されると自動表示されます。")
else:
    weekly["engagement"] = weekly["likes"] + weekly["reposts"] + weekly["comments"]
    fig_weekly = px.line(
        weekly, x="week", y="engagement", color="pattern_label",
        markers=True,
        labels={"week": "週番号", "engagement": "エンゲージメント合計", "pattern_label": "投稿タイプ"},
        color_discrete_sequence=CHART_COLOR,
    )
    fig_weekly.update_layout(height=300)
    st.plotly_chart(fig_weekly, use_container_width=True)

st.markdown("---")

# ─────────────────────────────────────────
# 投稿戦略インサイト
# ─────────────────────────────────────────
st.subheader("💡 投稿戦略インサイト")

if not df_stats.empty:
    ins_col1, ins_col2, ins_col3 = st.columns(3)

    # 最高パフォーマンスパターン
    best_pattern = (
        df_stats.groupby("pattern_label")["engagement"].sum().idxmax()
        if not df_stats.empty else "—"
    )
    ins_col1.metric("最高エンゲージメント パターン", best_pattern)

    # 最高パフォーマンス時間帯
    if not hourly.empty and hourly["engagement"].sum() > 0:
        best_hour = int(hourly.loc[hourly["engagement"].idxmax(), "hour"])
        ins_col2.metric("最高エンゲージメント 時間帯", f"{best_hour}:00〜{best_hour+1}:00")
    else:
        ins_col2.metric("最高エンゲージメント 時間帯", "—")

    # 最高クリック商品
    if not df_clicks.empty:
        best_product = df_clicks["product_name"].value_counts().idxmax()
        ins_col3.metric("最多クリック 商品", best_product)
    else:
        ins_col3.metric("最多クリック 商品", "—")
