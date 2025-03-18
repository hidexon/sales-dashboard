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
    template_csv = """タイムスタンプ,タイトル,開始価格,落札価格,入札数,落札者,出品者,商品URL
03/16 00:06,商品名,1000,1500,5,buyer_name,seller_name,https://example.com"""
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
                    supabase.table('sales').delete().neq('id', 0).execute()
                
                # 現在の年を取得
                current_year = datetime.now().year
                
                # データの整形と登録
                success_count = 0
                error_count = 0
                
                for row in csv_data:
                    try:
                        # タイムスタンプの変換（MM/DD HH:mm形式から）
                        date_str = row['タイムスタンプ']
                        month, day = map(int, date_str.split()[0].split('/'))
                        hour, minute = map(int, date_str.split()[1].split(':'))
                        
                        # 日付を作成（現在の年を使用）
                        timestamp = datetime(current_year, month, day, hour, minute)
                        
                        # 数値データの変換
                        start_price = int(row['開始価格'])
                        final_price = int(row['落札価格'])
                        bid_count = int(row['入札数'])
                        
                        # データの登録
                        supabase.table('sales').insert({
                            'timestamp': timestamp.isoformat(),
                            'title': row['タイトル'],
                            'start_price': start_price,
                            'final_price': final_price,
                            'bid_count': bid_count,
                            'buyer': row['落札者'],
                            'seller': row['出品者'],
                            'product_url': row['商品URL']
                        }).execute()
                        
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        st.error(f"データの登録中にエラーが発生しました: {str(e)}")
                        st.error(f"問題のある行: {row}")
                        continue
                
                # キャッシュをクリア
                load_data.clear()
                st.success(f"データ登録完了: 成功 {success_count}件, 失敗 {error_count}件")
                if success_count > 0:
                    st.markdown("ダッシュボードで確認するには、左のメニューから「ダッシュボード」を選択してください。")
        
        except Exception as e:
            st.error(f"エラーが発生しました: {str(e)}")
            st.markdown("CSVファイルの形式が正しいか確認してください。")

def show_data_management():
    """データ管理画面"""
    st.title("🗑️ データ管理")
    st.markdown("---")

    # データの読み込み
    df = load_data()
    
    # 現在のデータ件数を表示
    st.info(f"現在のデータ件数: {len(df):,}件")
    
    # データ削除セクション
    st.subheader("データの削除")
    col1, col2 = st.columns(2)
    
    with col1:
        # 全データ削除
        st.markdown("##### 全データの削除")
        delete_all = st.button("全データを削除", type="primary")
        confirm_all = st.checkbox("本当に全データを削除しますか？")
        
        if delete_all and confirm_all:
            try:
                supabase = init_connection()
                # 全データを削除
                result = supabase.table('sales').delete().neq('id', 0).execute()
                
                # 削除結果の確認
                if hasattr(result, 'data'):
                    deleted_count = len(result.data)
                    st.success(f"{deleted_count}件のデータを削除しました！")
                else:
                    st.success("データを削除しました！")
                
                # キャッシュをクリア
                load_data.clear()
                # ページを再読み込み
                st.rerun()
            except Exception as e:
                st.error(f"削除中にエラーが発生しました: {str(e)}")
                st.error("エラーの詳細:")
                st.code(str(e))
    
    with col2:
        # 期間指定削除
        st.markdown("##### 期間を指定して削除")
        if len(df) > 0:
            date_range = st.date_input(
                "削除する期間を選択",
                value=(df['timestamp'].min().date(), df['timestamp'].max().date()),
                min_value=df['timestamp'].min().date(),
                max_value=df['timestamp'].max().date()
            )
            
            if len(date_range) == 2:
                start_date, end_date = date_range
                delete_period = st.button("指定期間のデータを削除")
                confirm_period = st.checkbox("指定した期間のデータを削除しますか？")
                
                if delete_period and confirm_period:
                    try:
                        supabase = init_connection()
                        # ISO形式の文字列に変換
                        start_str = start_date.isoformat()
                        end_str = (end_date + timedelta(days=1)).isoformat()
                        
                        result = supabase.table('sales').delete().gte(
                            'timestamp', start_str
                        ).lt(
                            'timestamp', end_str
                        ).execute()
                        
                        # 削除結果の確認
                        if hasattr(result, 'data'):
                            deleted_count = len(result.data)
                            st.success(f"{deleted_count}件のデータを削除しました！")
                        else:
                            st.success(f"{start_date}から{end_date}までのデータを削除しました！")
                        
                        # キャッシュをクリア
                        load_data.clear()
                        # ページを再読み込み
                        st.rerun()
                    except Exception as e:
                        st.error(f"削除中にエラーが発生しました: {str(e)}")
                        st.error("エラーの詳細:")
                        st.code(str(e))

    # データ確認セクション
    st.subheader("現在のデータ")
    if len(df) > 0:
        # 日付でグループ化したデータ件数
        st.markdown("##### 日付別データ件数")
        daily_counts = df.groupby(df['timestamp'].dt.date).size().reset_index()
        daily_counts.columns = ['日付', 'データ件数']
        
        fig = px.bar(
            daily_counts,
            x='日付',
            y='データ件数',
            labels={'日付': '日付', 'データ件数': '件数'}
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # データの詳細表示
        st.markdown("##### データ一覧")
        st.dataframe(
            df.sort_values('timestamp', ascending=False),
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
                "bid_count": "入札数",
                "buyer": "購入者",
                "seller": "出品者",
                "product_url": st.column_config.LinkColumn("商品URL")
            },
            hide_index=True
        )
    else:
        st.warning("データが登録されていません。")

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
            "seller": "出品者",
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
    st.sidebar.header("メニュー")
    menu = st.sidebar.selectbox(
        "機能を選択",
        ["ダッシュボード", "データ登録", "データ管理"]
    )

    if menu == "データ登録":
        show_data_upload()
    elif menu == "データ管理":
        show_data_management()
    else:
        show_dashboard()

if __name__ == "__main__":
    main()