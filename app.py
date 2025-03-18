import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client
import pytz
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
        password = st.text_input("パスワードを入力してください", type="password", key="password_input")
        if password:
            try:
                correct_password = st.secrets["password"]
                if password == correct_password:
                    st.session_state.password_correct = True
                    st.rerun()
                else:
                    st.error("パスワードが違います")
                return False
            except Exception as e:
                st.error(f"パスワード設定エラー: {str(e)}")
                return False
        return False
    return True

@st.cache_data(ttl=600)
def load_data():
    """データの読み込みと前処理"""
    try:
        supabase = init_connection()
        if not supabase:
            return pd.DataFrame()
        
        # ページネーションを使用して全データを取得
        all_data = []
        page_size = 1000
        start = 0
        
        while True:
            response = supabase.table('sales').select('*') \
                .order('timestamp') \
                .range(start, start + page_size - 1) \
                .execute()
            
            if not response.data:  # データがない場合はループを終了
                break
                
            all_data.extend(response.data)
            
            if len(response.data) < page_size:  # 最後のページの場合
                break
                
            start += page_size
        
        df = pd.DataFrame(all_data)
        
        if df.empty:
            return df
        
        # タイムスタンプを日本時間に変換
        jst = pytz.timezone('Asia/Tokyo')
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert(jst)
        
        return df
    except Exception as e:
        st.error(f"データ読み込みエラー: {str(e)}")
        return pd.DataFrame()

def parse_timestamp(date_str):
    """タイムスタンプを解析する補助関数"""
    try:
        date_str = date_str.strip()
        parts = date_str.split(' ')
        if len(parts) < 2:
            raise ValueError(f"日付と時刻の区切りが見つかりません: {date_str}")
            
        date_part = parts[0]
        time_part = parts[1]
        
        if '/' not in date_part:
            raise ValueError(f"日付の区切り(/)が見つかりません: {date_part}")
            
        date_elements = date_part.split('/')
        
        if len(date_elements) == 3:  # YYYY/MM/DD形式
            year = int(date_elements[0])
            month = int(date_elements[1])
            day = int(date_elements[2])
        elif len(date_elements) == 2:  # MM/DD形式
            year = datetime.now().year
            month = int(date_elements[0])
            day = int(date_elements[1])
        else:
            raise ValueError(f"日付の形式が不正です: {date_part}")
        
        time_elements = time_part.split(':')
        if len(time_elements) < 2:
            raise ValueError(f"時刻の形式が不正です: {time_part}")
            
        hour = int(time_elements[0])
        minute = int(time_elements[1])
        second = int(time_elements[2]) if len(time_elements) > 2 else 0
        
        return datetime(year, month, day, hour, minute, second)
        
    except Exception as e:
        raise ValueError(f"日付の解析に失敗しました: {date_str} - {str(e)}")

def show_data_upload():
    """データ登録画面"""
    st.title("📤 データ登録")
    st.markdown("---")

    # CSVファイルのテンプレートをダウンロード
    st.subheader("1. CSVテンプレートのダウンロード")
    template_csv = """タイムスタンプ,タイトル,開始価格,落札価格,入札数,落札者,出品者,商品URL
03/18 13:59,"NN0056【１点限り】A4 ポスター 美女 美少女 オリジナルアート 同人イラスト コスプレ 可愛い スポーツ少女",70,70,1,取得対象外,bonbobon7,"https://auctions.yahoo.co.jp/jp/auction/o1177115124"
2025/03/16 23:59:00,"別の商品例",1000,1500,5,buyer_name,seller_name,"https://example.com/item123\""""
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
            stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
            csv_data = list(csv.DictReader(stringio))
            
            if len(csv_data) == 0:
                st.error("CSVファイルにデータが含まれていません。")
                return
            
            st.subheader("3. アップロードされたデータの確認")
            df_preview = pd.DataFrame(csv_data)
            st.dataframe(df_preview)
            
            st.info("""
            対応している日付形式:
            - MM/DD HH:mm (例: 03/18 13:59)
            - YYYY/MM/DD HH:mm:ss (例: 2025/03/16 23:59:00)
            """)
            
            if st.button("データを登録", type="primary"):
                supabase = init_connection()
                
                if st.checkbox("既存データを削除してから登録する"):
                    supabase.table('sales').delete().neq('id', 0).execute()
                
                success_count = 0
                error_count = 0
                
                for row in csv_data:
                    try:
                        timestamp = parse_timestamp(row['タイムスタンプ'])
                        start_price = int(str(row['開始価格']).replace(',', '').strip())
                        final_price = int(str(row['落札価格']).replace(',', '').strip())
                        bid_count = int(str(row['入札数']).replace(',', '').strip())
                        
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

    df = load_data()
    total_count = len(df)
    st.info(f"現在のデータ件数: {total_count:,} 件")

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
                    st.rerun()
                except Exception as e:
                    st.error(f"データ削除中にエラーが発生しました: {str(e)}")

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
                    st.rerun()
                except Exception as e:
                    st.error(f"データ削除中にエラーが発生しました: {str(e)}")

def show_dashboard():
    """ダッシュボード画面"""
    st.title("📊 オークション分析ダッシュボード")
    st.markdown("---")

    df = load_data()
    if df.empty:
        st.warning("データが存在しません。左のメニューから「データ登録」を選択してデータを登録してください。")
        return

    # データの総件数を確認
    total_items = len(df)
    
    # 全体の集計を表示
    total_final_price = df['final_price'].sum()
    avg_start_price = df['start_price'].mean()
    avg_final_price = df['final_price'].mean()
    avg_bids = df['bid_count'].mean()

    # 集計値の表示（実際のデータ件数を使用）
    st.write(f"総データ件数：{total_items:,}　"
             f"落札価格の合計：¥{total_final_price:,.0f}　"
             f"開始価格の平均：¥{avg_start_price:,.2f}　"
             f"落札価格の平均：¥{avg_final_price:,.2f}　"
             f"入札件数の平均：{avg_bids:.2f}")

    # セラー別の集計表を作成
    seller_stats = df.groupby('seller').agg({
        'title': 'count',  # 件数
        'start_price': 'mean',  # 平均開始価格
        'final_price': ['sum', 'mean'],  # 落札価格合計と平均
        'bid_count': 'mean'  # 平均入札件数
    }).reset_index()

    # カラム名を設定
    seller_stats.columns = ['セラー', '件数', '平均開始価格', '落札価格合計', '平均落札価格', '平均入札件数']

    # 件数でソートして表示（上位10件に限定しない）
    seller_stats = seller_stats.sort_values('件数', ascending=False)

    # 表示用にフォーマット
    formatted_stats = seller_stats.copy()
    formatted_stats['件数'] = formatted_stats['件数'].apply(lambda x: f"{int(x):,}")
    formatted_stats['平均開始価格'] = formatted_stats['平均開始価格'].apply(lambda x: f"¥{x:,.2f}")
    formatted_stats['落札価格合計'] = formatted_stats['落札価格合計'].apply(lambda x: f"¥{int(x):,}")
    formatted_stats['平均落札価格'] = formatted_stats['平均落札価格'].apply(lambda x: f"¥{x:,.2f}")
    formatted_stats['平均入札件数'] = formatted_stats['平均入札件数'].apply(lambda x: f"{x:.2f}")

    # セラー別集計の合計を表示
    st.write(f"表示中のセラー数：{len(seller_stats):,}")
    
    # テーブルとして表示（ページネーション付き）
    st.dataframe(
        formatted_stats,
        column_config={
            'セラー': st.column_config.TextColumn('セラー'),
            '件数': st.column_config.TextColumn('件数'),
            '平均開始価格': st.column_config.TextColumn('平均開始価格'),
            '落札価格合計': st.column_config.TextColumn('落札価格合計'),
            '平均落札価格': st.column_config.TextColumn('平均落札価格'),
            '平均入札件数': st.column_config.TextColumn('平均入札件数')
        },
        hide_index=True
    )

    # データの整合性チェック
    total_items_by_seller = sum(int(x.replace(',', '')) for x in formatted_stats['件数'])
    if total_items != total_items_by_seller:
        st.warning(f"⚠️ データの不一致が検出されました。総件数: {total_items:,}, セラー別合計: {total_items_by_seller:,}")

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