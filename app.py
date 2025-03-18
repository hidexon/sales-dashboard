import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
from io import StringIO
import csv

# ページ設定
st.set_page_config(
    page_title="オークション分析ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Supabaseクライアントの初期化
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

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

@st.cache_data(ttl=600)
def load_data():
    """データの読み込みと前処理"""
    supabase = init_connection()
    response = supabase.table('sales').select('*').execute()
    df = pd.DataFrame(response.data)
    
    if len(df) == 0:
        return pd.DataFrame(columns=[
            'timestamp', 'title', 'start_price', 'final_price', 
            'bid_count', 'buyer', 'seller', 'product_url'
        ])
    
    # タイムスタンプを日本時間に変換
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('Asia/Tokyo')
    
    # 利益率の計算
    df['profit'] = df['final_price'] - df['start_price']
    df['profit_rate'] = (df['profit'] / df['start_price'] * 100).round(1)
    
    return df

def show_data_upload():
    """データ登録画面"""
    st.title("📤 データ登録")
    st.markdown("---")

    # CSVファイルのテンプレートをダウンロード
    st.subheader("1. CSVテンプレートのダウンロード")
    template_csv = """timestamp,title,start_price,final_price,bid_count,buyer,seller,product_url
2024-01-01 10:00:00,商品名,1000,1500,5,buyer_name,seller_name,https://example.com"""
    st.download_button(
        label="CSVテンプレートをダウンロード",
        data=template_csv,
        file_name="template.csv",
        mime="text/csv"
    )
    
    # CSVファイルのアップロード
    st.subheader("2. データのアップロード")
    uploaded_file = st.file_uploader("CSVファイルを選択", type="csv")
    
    if uploaded_file is not None:
        try:
            # CSVファイルの読み込み
            stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
            csv_data = list(csv.DictReader(stringio))
            
            # データの検証
            if len(csv_data) == 0:
                st.error("CSVファイルにデータが含まれていません。")
                return
            
            # データの確認
            st.subheader("3. アップロードされたデータの確認")
            df_preview = pd.DataFrame(csv_data)
            st.dataframe(df_preview)
            
            # データの登録
            if st.button("データを登録", type="primary"):
                supabase = init_connection()
                
                # 既存データの削除確認
                if st.checkbox("既存データを削除してから登録する"):
                    supabase.table('sales').delete().execute()
                
                # データの整形と登録
                for row in csv_data:
                    # タイムスタンプの変換
                    timestamp = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
                    
                    # 数値データの変換
                    start_price = int(row['start_price'])
                    final_price = int(row['final_price'])
                    bid_count = int(row['bid_count'])
                    
                    # データの登録
                    supabase.table('sales').insert({
                        'timestamp': timestamp.isoformat(),
                        'title': row['title'],
                        'start_price': start_price,
                        'final_price': final_price,
                        'bid_count': bid_count,
                        'buyer': row['buyer'],
                        'seller': row['seller'],
                        'product_url': row['product_url']
                    }).execute()
                
                st.success(f"{len(csv_data)}件のデータを登録しました！")
                st.markdown("ダッシュボードで確認するには、左のメニューから「ダッシュボード」を選択してください。")
        
        except Exception as e:
            st.error(f"エラーが発生しました: {str(e)}")
            st.markdown("CSVファイルの形式が正しいか確認してください。")

def show_dashboard():
    """ダッシュボード画面の表示"""
    # データの読み込み
    df = load_data()

    # ヘッダー
    st.title("📊 オークション分析ダッシュボード")
    st.markdown("---")

    if len(df) == 0:
        st.warning("データが登録されていません。左メニューの「データ登録」からデータを登録してください。")
        return

    # サイドバー - 期間選択
    st.sidebar.header("期間選択")
    date_range = st.sidebar.date_input(
        "期間を選択",
        value=(df['timestamp'].min().date(), df['timestamp'].max().date()),
        min_value=df['timestamp'].min().date(),
        max_value=df['timestamp'].max().date()
    )

    # データのフィルタリング
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = df[
            (df['timestamp'].dt.date >= start_date) & 
            (df['timestamp'].dt.date <= end_date)
        ]
    else:
        filtered_df = df

    # メイン画面を3列に分割
    col1, col2, col3 = st.columns(3)

    # KPI表示
    with col1:
        total_sales = filtered_df['final_price'].sum()
        st.metric("総売上", f"¥{total_sales:,.0f}")
    
    with col2:
        avg_profit_rate = filtered_df['profit_rate'].mean()
        st.metric("平均利益率", f"{avg_profit_rate:.1f}%")
    
    with col3:
        total_items = len(filtered_df)
        st.metric("取引件数", f"{total_items:,}件")

    # グラフ表示エリアを2列に分割
    graph_col1, graph_col2 = st.columns(2)

    with graph_col1:
        # 日次売上推移グラフ
        st.subheader("日次売上推移")
        daily_sales = filtered_df.groupby(filtered_df['timestamp'].dt.date)['final_price'].sum().reset_index()
        fig_sales = px.line(
            daily_sales,
            x='timestamp',
            y='final_price',
            labels={'timestamp': '日付', 'final_price': '売上'},
        )
        fig_sales.update_layout(yaxis_title="売上（円）")
        st.plotly_chart(fig_sales, use_container_width=True)

    with graph_col2:
        # 商品別売上構成
        st.subheader("商品別売上構成")
        product_sales = filtered_df.groupby('title').agg({
            'final_price': 'sum',
            'id': 'count'
        }).reset_index()
        product_sales.columns = ['商品名', '売上', '取引件数']
        fig_products = px.pie(
            product_sales,
            values='売上',
            names='商品名',
            hover_data=['取引件数']
        )
        st.plotly_chart(fig_products, use_container_width=True)

    # 詳細データ表示
    st.subheader("取引詳細")
    st.dataframe(
        filtered_df.sort_values('timestamp', ascending=False),
        column_config={
            "timestamp": st.column_config.DatetimeColumn(
                "取引日時",
                format="YYYY-MM-DD HH:mm"
            ),
            "title": "商品名",
            "start_price": st.column_config.NumberColumn(
                "開始価格",
                format="¥%d"
            ),
            "final_price": st.column_config.NumberColumn(
                "落札価格",
                format="¥%d"
            ),
            "profit": st.column_config.NumberColumn(
                "利益",
                format="¥%d"
            ),
            "profit_rate": st.column_config.NumberColumn(
                "利益率",
                format="%0.1f%%"
            ),
            "bid_count": "入札数",
            "buyer": "購入者",
            "seller": "販売者",
            "product_url": st.column_config.LinkColumn("商品URL")
        },
        hide_index=True
    )

    # 分析情報
    st.subheader("📈 分析情報")
    analysis_col1, analysis_col2 = st.columns(2)

    with analysis_col1:
        # 商品別平均利益率
        st.markdown("##### 商品別平均利益率")
        product_profit = filtered_df.groupby('title').agg({
            'profit_rate': 'mean',
            'id': 'count'
        }).sort_values('profit_rate', ascending=False).reset_index()
        
        fig_profit = px.bar(
            product_profit,
            x='title',
            y='profit_rate',
            text='profit_rate',
            labels={'title': '商品名', 'profit_rate': '利益率 (%)'},
        )
        fig_profit.update_traces(texttemplate='%{text:.1f}%')
        st.plotly_chart(fig_profit, use_container_width=True)

    with analysis_col2:
        # 入札数と最終価格の関係
        st.markdown("##### 入札数と最終価格の関係")
        fig_bids = px.scatter(
            filtered_df,
            x='bid_count',
            y='final_price',
            color='title',
            labels={'bid_count': '入札数', 'final_price': '最終価格', 'title': '商品名'},
            trendline="ols"
        )
        st.plotly_chart(fig_bids, use_container_width=True)

def main():
    """メイン関数"""
    if not check_password():
        return

    # 管理メニューの追加
    st.sidebar.markdown("---")
    st.sidebar.header("データ管理")
    menu = st.sidebar.selectbox(
        "機能を選択",
        ["ダッシュボード", "データ登録"]
    )

    if menu == "データ登録":
        show_data_upload()
    else:
        show_dashboard()

if __name__ == "__main__":
    main()