import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from datetime import datetime, timedelta

# Supabase初期化
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase_url"]
    key = st.secrets["supabase_key"]
    return create_client(url, key)

# パスワード認証
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        st.markdown("## 🔐 ログイン")
        password = st.text_input("パスワードを入力してください", type="password")
        
        if st.button("ログイン"):
            if password == st.secrets["password"]:
                st.session_state.password_correct = True
                st.experimental_rerun()
            else:
                st.error("パスワードが違います")
        return False

    return True

def main():
    st.set_page_config(
        page_title="売上分析ダッシュボード",
        page_icon="📊",
        layout="wide"
    )

    if not check_password():
        return

    st.title("📊 売上分析ダッシュボード")

    # データ取得
    try:
        supabase = init_supabase()
        response = supabase.table('sales').select('*').execute()
        df = pd.DataFrame(response.data)

        if len(df) == 0:
            st.warning("データが存在しません")
            return

        # タイムスタンプをdatetime型に変換
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # 基本統計
        st.header("📈 基本統計")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("総取引数", f"{len(df):,}件")
        with col2:
            st.metric("総売上", f"¥{df['final_price'].sum():,}")
        with col3:
            st.metric("平均落札価格", f"¥{df['final_price'].mean():,.0f}")

        # 日次推移グラフ
        st.header("📅 日次推移")
        daily_sales = df.groupby(df['timestamp'].dt.date).agg({
            'final_price': 'sum',
            'id': 'count'
        }).reset_index()
        
        fig = px.line(daily_sales, 
                     x='timestamp', 
                     y='final_price',
                     title="日次売上推移")
        st.plotly_chart(fig, use_container_width=True)

        # 出品者別集計
        st.header("👥 出品者別集計")
        seller_stats = df.groupby('seller').agg({
            'final_price': ['sum', 'mean', 'count']
        }).round(0)
        seller_stats.columns = ['総売上', '平均価格', '取引数']
        st.dataframe(seller_stats.sort_values('総売上', ascending=False))

    except Exception as e:
        st.error(f"エラーが発生しました: {str(e)}")

if __name__ == "__main__":
    main()