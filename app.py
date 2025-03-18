import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from datetime import datetime, timedelta

# ページ設定
st.set_page_config(
    page_title="売上ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Supabaseクライアントの初期化
@st.cache_resource
def init_connection():
    """Supabaseクライアントの初期化と接続"""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"データベース接続エラー: {str(e)}")
        return None

def check_password():
    """パスワード認証機能"""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        password = st.text_input("パスワードを入力してください:", type="password")
        if password == st.secrets["password"]:
            st.session_state.password_correct = True
            st.rerun()
        return False
    
    return True

def format_currency(value):
    """通貨のフォーマット関数"""
    return f"¥{value:,.0f}"

def main():
    """メイン関数"""
    try:
        # パスワード認証
        if not check_password():
            return

        # Supabaseクライアントの取得
        supabase = init_connection()
        if supabase is None:
            return

        # データの取得
        @st.cache_data(ttl=600)
        def load_data():
            """データベースからデータを取得し、前処理を行う"""
            try:
                # データの取得
                response = supabase.table('sales').select('*').execute()
                if not response.data:
                    st.warning("データが見つかりませんでした。")
                    return pd.DataFrame()

                # データフレームに変換
                df = pd.DataFrame(response.data)
                
                # 日付型への変換
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                elif 'created_at' in df.columns:
                    df['date'] = pd.to_datetime(df['created_at'])
                    
                return df

            except Exception as e:
                st.error(f"データ取得エラー: {str(e)}")
                return pd.DataFrame()

        # データの読み込み
        df = load_data()
        if df.empty:
            st.warning("表示するデータがありません。")
            return

        # ヘッダー
        st.title("📊 売上ダッシュボード")
        st.markdown("---")

        # サイドバー - 期間選択
        st.sidebar.header("期間選択")
        min_date = df['date'].min().date()
        max_date = df['date'].max().date()
        date_range = st.sidebar.date_input(
            "期間を選択",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

        # 選択された期間でデータをフィルタリング
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = df[(df['date'].dt.date >= start_date) & 
                           (df['date'].dt.date <= end_date)]
        else:
            filtered_df = df

        # メインコンテンツ
        # KPI概要
        col1, col2, col3 = st.columns(3)
        
        # 金額カラムの特定（'price'または'amount'）
        amount_column = 'price' if 'price' in df.columns else 'amount'
        
        with col1:
            total_sales = filtered_df[amount_column].sum()
            st.metric("総売上", format_currency(total_sales))
        
        with col2:
            avg_sales = filtered_df[amount_column].mean()
            st.metric("平均売上", format_currency(avg_sales))
        
        with col3:
            total_orders = len(filtered_df)
            st.metric("総注文数", f"{total_orders:,}")

        # グラフ
        st.markdown("### 売上推移")
        daily_sales = filtered_df.groupby(filtered_df['date'].dt.date)[amount_column].sum().reset_index()
        fig = px.line(
            daily_sales, 
            x='date', 
            y=amount_column,
            title='日次売上推移',
            labels={'date': '日付', amount_column: '売上'}
        )
        fig.update_layout(
            xaxis_title="日付",
            yaxis_title="売上",
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)

        # データテーブル
        st.markdown("### 売上データ")
        
        # カラム設定の準備
        column_config = {
            "date": st.column_config.DatetimeColumn(
                "日付",
                format="YYYY-MM-DD HH:mm"
            ),
            amount_column: st.column_config.NumberColumn(
                "売上",
                format="¥%d"
            )
        }
        
        # 商品名カラムが存在する場合は設定を追加
        if 'name' in df.columns:
            column_config["name"] = "商品名"
        
        # データテーブルの表示
        display_df = filtered_df.sort_values('date', ascending=False)
        st.dataframe(
            display_df,
            column_config=column_config,
            hide_index=True
        )

    except Exception as e:
        st.error(f"予期せぬエラーが発生しました: {str(e)}")

if __name__ == "__main__":
    main()