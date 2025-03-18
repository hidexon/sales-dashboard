import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from datetime import datetime, timedelta

# ページ設定
st.set_page_config(
    page_title="売上ダッシュボード",
    page_icon="📊",
    layout="wide"
)

# Supabaseクライアントの初期化
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def check_password():
    """パスワードチェック関数"""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        password = st.text_input("パスワードを入力してください:", type="password")
        if password == st.secrets["password"]:
            st.session_state.password_correct = True
            st.rerun()
        return False
    
    return True

def main():
    """メイン関数"""
    # パスワード認証
    if not check_password():
        return

    # Supabaseクライアントの取得
    supabase = init_connection()

    # データの取得
    @st.cache_data(ttl=600)
    def load_data():
        response = supabase.table('sales').select('*').execute()
        df = pd.DataFrame(response.data)
        # created_atをdatetimeに変換
        df['created_at'] = pd.to_datetime(df['created_at'])
        return df

    # データの読み込み
    df = load_data()

    # ヘッダー
    st.title("📊 売上ダッシュボード")
    st.markdown("---")

    # サイドバー - 期間選択
    st.sidebar.header("期間選択")
    date_range = st.sidebar.date_input(
        "期間を選択",
        value=(df['created_at'].min(), df['created_at'].max()),
        min_value=df['created_at'].min().date(),
        max_value=df['created_at'].max().date()
    )

    # 選択された期間でデータをフィルタリング
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = df[(df['created_at'].dt.date >= start_date) & 
                        (df['created_at'].dt.date <= end_date)]
    else:
        filtered_df = df

    # メインコンテンツ
    # KPI概要
    col1, col2, col3 = st.columns(3)
    with col1:
        total_sales = filtered_df['price'].sum()
        st.metric("総売上", f"¥{total_sales:,.0f}")
    
    with col2:
        avg_sales = filtered_df['price'].mean()
        st.metric("平均売上", f"¥{avg_sales:,.0f}")
    
    with col3:
        total_orders = len(filtered_df)
        st.metric("総注文数", f"{total_orders:,}")

    # グラフ
    st.markdown("### 売上推移")
    daily_sales = filtered_df.groupby(filtered_df['created_at'].dt.date)['price'].sum().reset_index()
    fig = px.line(daily_sales, x='created_at', y='price',
                  title='日次売上推移',
                  labels={'created_at': '日付', 'price': '売上'})
    st.plotly_chart(fig, use_container_width=True)

    # データテーブル
    st.markdown("### 売上データ")
    st.dataframe(
        filtered_df.sort_values('created_at', ascending=False),
        column_config={
            "created_at": st.column_config.DatetimeColumn(
                "日付",
                format="YYYY-MM-DD HH:mm"
            ),
            "price": st.column_config.NumberColumn(
                "売上",
                format="¥%d"
            ),
            "name": "商品名"
        },
        hide_index=True
    )

if __name__ == "__main__":
    main()