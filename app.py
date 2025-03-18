import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from supabase import create_client
import pytz
import numpy as np
from io import StringIO
import csv

# ページ設定
st.set_page_config(
    page_title="オークション分析ダッシュボード",
    page_icon="📊",
    layout="wide"
)

def init_connection():
    """Supabaseクライアントの初期化"""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"データベース接続エラー: {str(e)}")
        return None

def check_password():
    """パスワードチェック"""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        password = st.text_input("パスワードを入力してください", type="password")
        if password == st.secrets["APP_PASSWORD"]:
            st.session_state.password_correct = True
            st.experimental_rerun()
        else:
            if password:
                st.error("パスワードが違います")
            return False
    return True

@st.cache_data(ttl=600)
def load_data():
    """データの読み込みと前処理"""
    try:
        supabase = init_connection()
        if not supabase:
            return pd.DataFrame()
        
        response = supabase.table('sales').select('*').order('timestamp').execute()
        df = pd.DataFrame(response.data)
        
        if df.empty:
            return df
        
        # タイムスタンプを日本時間に変換
        jst = pytz.timezone('Asia/Tokyo')
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert(jst)
        
        # 利益計算
        df['profit'] = df['final_price'] - df['start_price']
        
        return df
    except Exception as e:
        st.error(f"データ読み込みエラー: {str(e)}")
        return pd.DataFrame()

def parse_timestamp(date_str):
    """タイムスタンプを解析する補助関数"""
    try:
        # 入力文字列をクリーニング
        date_str = date_str.strip()
        
        # スペースで分割して日付と時刻を取得
        parts = date_str.split(' ')
        if len(parts) < 2:
            raise ValueError(f"日付と時刻の区切りが見つかりません: {date_str}")
            
        date_part = parts[0]  # 日付部分
        time_part = parts[1]  # 時刻部分
        
        # 日付部分を処理 (MM/DD)
        if '/' not in date_part:
            raise ValueError(f"日付の区切り(/)が見つかりません: {date_part}")
            
        month_day = date_part.split('/')
        if len(month_day) != 2:
            raise ValueError(f"日付の形式が不正です: {date_part}")
            
        month = int(month_day[0])
        day = int(month_day[1])
        
        # 時刻部分を処理 (HH:mm:ss または HH:mm)
        time_elements = time_part.split(':')
        if len(time_elements) < 2:
            raise ValueError(f"時刻の形式が不正です: {time_part}")
            
        hour = int(time_elements[0])
        minute = int(time_elements[1])
        second = int(time_elements[2]) if len(time_elements) > 2 else 0
        
        # 現在の年を取得
        current_year = datetime.now().year
        
        # 日付オブジェクトを作成
        return datetime(current_year, month, day, hour, minute, second)
        
    except Exception as e:
        raise ValueError(f"日付の解析に失敗しました: {date_str} - {str(e)}")

def show_data_upload():
    """データ登録画面"""
    st.title("📤 データ登録")
    st.markdown("---")

    # CSVファイルのテンプレートをダウンロード
    st.subheader("1. CSVテンプレートのダウンロード")
    template_csv = """タイムスタンプ,タイトル,開始価格,落札価格,入札数,落札者,出品者,商品URL
03/18 13:59,"NN0056【１点限り】A4 ポスター 美女 美少女 オリジナルアート 同人イラスト コスプレ 可愛い スポーツ少女",70,70,1,取得対象外,bonbobon7,"https://auctions.yahoo.co.jp/jp/auction/o1177115124\""""
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
                
                # データの整形と登録
                success_count = 0
                error_count = 0
                
                for row in csv_data:
                    try:
                        # タイムスタンプの変換
                        timestamp = parse_timestamp(row['タイムスタンプ'])
                        
                        # 数値データの変換（カンマと空白を除去してから変換）
                        start_price = int(str(row['開始価格']).replace(',', '').strip())
                        final_price = int(str(row['落札価格']).replace(',', '').strip())
                        bid_count = int(str(row['入札数']).replace(',', '').strip())
                        
                        # データの登録
                        supabase.table('sales').insert({
                            'timestamp': timestamp.isoformat(),
                            'title': row['タイトル'].strip(),
                            'start_price': start_price,
                            'final_price': final_price,
                            'bid_count': bid_count,
                            'buyer': row['落札者'].strip(),
                            'seller': row['出品者'].strip(),
                            'product_url': row['商品URL'].strip()
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

    # データ件数の表示
    df = load_data()
    total_count = len(df)
    st.info(f"現在のデータ件数: {total_count:,} 件")

    # 全データ削除
    st.subheader("データの削除")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("全データを削除", type="primary"):
            if st.button("本当に全データを削除しますか？", type="primary"):
                try:
                    supabase = init_connection()
                    supabase.table('sales').delete().neq('id', 0).execute()
                    load_data.clear()
                    st.success("全データを削除しました")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"データ削除中にエラーが発生しました: {str(e)}")

    # 期間指定削除
    with col2:
        st.write("期間を指定して削除")
        if not df.empty:
            min_date = df['timestamp'].min()
            max_date = df['timestamp'].max()
            selected_dates = st.date_input(
                "削除する期間を選択",
                value=(min_date, max_date),
                min_value=min_date.date(),
                max_value=max_date.date()
            )
            
            if len(selected_dates) == 2 and st.button("選択期間のデータを削除"):
                try:
                    start_date, end_date = selected_dates
                    start_datetime = datetime.combine(start_date, datetime.min.time())
                    end_datetime = datetime.combine(end_date, datetime.max.time())
                    
                    supabase = init_connection()
                    supabase.table('sales').delete() \
                        .gte('timestamp', start_datetime.isoformat()) \
                        .lte('timestamp', end_datetime.isoformat()) \
                        .execute()
                    
                    load_data.clear()
                    st.success(f"{start_date}から{end_date}までのデータを削除しました")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"データ削除中にエラーが発生しました: {str(e)}")

    # データの詳細表示
    if not df.empty:
        st.subheader("データの詳細")
        st.dataframe(
            df.style.format({
                'start_price': '{:,.0f}円',
                'final_price': '{:,.0f}円',
                'profit': '{:,.0f}円'
            })
        )

def show_dashboard():
    """ダッシュボード画面"""
    st.title("📊 オークション分析ダッシュボード")
    st.markdown("---")

    df = load_data()
    if df.empty:
        st.warning("データが存在しません。左のメニューから「データ登録」を選択してデータを登録してください。")
        return

    # KPI表示
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_sales = df['final_price'].sum()
        st.metric("総売上", f"¥{total_sales:,.0f}")
    
    with col2:
        total_profit = df['profit'].sum()
        st.metric("総利益", f"¥{total_profit:,.0f}")
    
    with col3:
        avg_profit = df['profit'].mean()
        st.metric("平均利益", f"¥{avg_profit:,.0f}")
    
    with col4:
        success_rate = (df['final_price'] > df['start_price']).mean() * 100
        st.metric("利益計上率", f"{success_rate:.1f}%")

    # グラフ表示
    st.subheader("売上トレンド")
    df_daily = df.groupby(df['timestamp'].dt.date).agg({
        'final_price': 'sum',
        'profit': 'sum'
    }).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_daily['timestamp'],
        y=df_daily['final_price'],
        name='売上',
        line=dict(color='#1f77b4')
    ))
    fig.add_trace(go.Scatter(
        x=df_daily['timestamp'],
        y=df_daily['profit'],
        name='利益',
        line=dict(color='#2ca02c')
    ))
    fig.update_layout(
        xaxis_title='日付',
        yaxis_title='金額（円）',
        hovermode='x unified'
    )
    st.plotly_chart(fig, use_container_width=True)

    # 詳細データ表示
    st.subheader("取引データ")
    st.dataframe(
        df.style.format({
            'start_price': '{:,.0f}円',
            'final_price': '{:,.0f}円',
            'profit': '{:,.0f}円'
        })
    )

def main():
    """メイン関数"""
    if not check_password():
        return

    # サイドバーメニュー
    menu = st.sidebar.selectbox(
        "メニュー",
        ["ダッシュボード", "データ登録", "データ管理"]
    )

    if menu == "ダッシュボード":
        show_dashboard()
    elif menu == "データ登録":
        show_data_upload()
    elif menu == "データ管理":
        show_data_management()

if __name__ == "__main__":
    main()