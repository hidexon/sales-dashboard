import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client
import pytz
from io import StringIO
import csv
import os
import numpy as np
import time

# ページ設定
st.set_page_config(
    page_title="オークション分析ダッシュボード",
    page_icon="📊",
    layout="wide"
)

# 数値のフォーマット関数
def format_price(price):
    """価格を3桁区切りのカンマ付き文字列に変換"""
    return f"¥{price:,}"

def format_number(num):
    """数値を3桁区切りのカンマ付き文字列に変換"""
    return f"{num:,}"

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
    st.header("📤 データ登録")
    
    # CSVファイルのテンプレートをダウンロード
    st.subheader("1. CSVテンプレートのダウンロード")
    template_csv = """タイムスタンプ,カテゴリ,タイトル,開始価格,落札価格,入札数,落札者,出品者,出品者URL,商品URL
2025/3/18 23:59,その他 > アダルト > ポスター,サンプル商品,590,590,2,取得対象外,sryy4000,https://auctions.yahoo.co.jp/seller/sryy4000,https://auctions.yahoo.co.jp/jp/auction/g1177417715"""
    st.download_button(
        label="CSVテンプレートをダウンロード",
        data=template_csv,
        file_name="template.csv",
        mime="text/csv"
    )
    
    # CSVファイルのアップロード
    st.subheader("2. CSVファイルのアップロード")
    uploaded_files = st.file_uploader(
        "CSVファイルをアップロードしてください（複数ファイル可）",
        type="csv",
        accept_multiple_files=True
    )
    
    # セッション状態の初期化（ファイルアップロード後に実行）
    if 'processing_complete' not in st.session_state:
        st.session_state.processing_complete = False
    
    if uploaded_files and not st.session_state.processing_complete:
        # 重複チェック用のセット
        processed_files = set()
        
        total_rows = 0
        success_count = 0
        error_count = 0
        error_messages = []
        
        # 進捗バーを作成
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        with st.spinner("データを登録中..."):
            for uploaded_file in uploaded_files:
                try:
                    # ファイル名の重複チェック
                    if uploaded_file.name in processed_files:
                        st.warning(f"警告: {uploaded_file.name} は既に処理済みです。スキップします。")
                        continue
                    
                    # ファイル名を表示
                    st.write(f"処理中: {uploaded_file.name}")
                    
                    # CSVファイルを読み込む
                    df = pd.read_csv(uploaded_file)
                    file_rows = len(df)
                    total_rows += file_rows
                    
                    # データを登録
                    for index, row in df.iterrows():
                        try:
                            # 進捗状況を更新
                            current_progress = (success_count + error_count) / total_rows if total_rows > 0 else 0
                            progress_bar.progress(current_progress)
                            status_text.text(f"進捗: {success_count + error_count}/{total_rows} 件 (成功: {success_count}, エラー: {error_count})")
                            
                            # 日付形式の統一
                            timestamp = pd.to_datetime(row['タイムスタンプ'])
                            formatted_date = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                            
                            # 数値データの前処理
                            def clean_number(value):
                                """数値データをクリーニングして整数に変換"""
                                if isinstance(value, (int, float)):
                                    return int(value)
                                return int(float(str(value).replace(',', '').strip()))
                            
                            start_price = clean_number(row['開始価格'])
                            end_price = clean_number(row['落札価格'])
                            bids = clean_number(row['入札数'])
                            
                            # データを登録
                            data = {
                                'timestamp': formatted_date,
                                'category': str(row['カテゴリ']).strip(),
                                'title': str(row['タイトル']).strip(),
                                'start_price': start_price,
                                'final_price': end_price,
                                'bid_count': bids,
                                'buyer': str(row['落札者']).strip(),
                                'seller': str(row['出品者']).strip(),
                                'seller_url': str(row['出品者URL']).strip(),
                                'product_url': str(row['商品URL']).strip()
                            }
                            
                            # Supabaseクライアントの初期化
                            supabase = init_connection()
                            if not supabase:
                                raise Exception("データベース接続に失敗しました")
                                
                            # データを登録
                            try:
                                result = supabase.table('sales').insert(data).execute()
                                if not result.data:
                                    raise Exception("データの登録に失敗しました")
                                success_count += 1
                            except Exception as e:
                                raise Exception(f"データ登録エラー: {str(e)}")
                                
                        except Exception as e:
                            error_count += 1
                            error_messages.append(f"行 {index+1}: {str(e)}")
                            st.error(f"エラー詳細: {str(e)}")
                            st.error(f"問題のあるデータ: {row.to_dict()}")
                    
                    # 処理済みファイルとして記録
                    processed_files.add(uploaded_file.name)
                    
                except Exception as e:
                    error_count += 1
                    error_messages.append(f"ファイル {uploaded_file.name}: {str(e)}")
                    st.error(f"ファイル処理エラー: {str(e)}")
        
        # 最終的な進捗を表示
        progress_bar.progress(1.0)
        status_text.text(f"完了: {total_rows} 件中 {success_count} 件成功, {error_count} 件エラー")
        
        # 結果を表示
        st.success(f"処理完了！\n- 合計行数: {total_rows:,}\n- 成功: {success_count:,}\n- エラー: {error_count:,}")
        
        if error_messages:
            st.error("エラーが発生しました:")
            for msg in error_messages:
                st.write(f"- {msg}")
        
        # 処理完了フラグを設定
        st.session_state.processing_complete = True
        
        # キャッシュをクリア
        st.cache_data.clear()
        
        # 新しいアップロードのために画面を更新
        time.sleep(1)  # 1秒待機して状態を安定させる
        st.rerun()
    
    # 処理完了後、新しいアップロードの準備
    elif not uploaded_files:
        st.session_state.processing_complete = False

def show_data_management():
    """データ管理画面"""
    st.title("🗑️ データ管理")
    st.markdown("---")

    df = load_data()
    total_count = len(df)
    st.info(f"現在のデータ件数: {total_count:,} 件")

    # 削除プロセスの状態管理
    if 'delete_step' not in st.session_state:
        st.session_state.delete_step = 0

    # 削除ボタンと確認プロセス
    if st.session_state.delete_step == 0:
        if st.button("データを全て削除"):
            st.session_state.delete_step = 1
            st.rerun()
    
    elif st.session_state.delete_step == 1:
        st.warning("⚠️ 本当にすべてのデータを削除しますか？")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("はい、削除します"):
                st.session_state.delete_step = 2
                st.rerun()
        with col2:
            if st.button("キャンセル"):
                st.session_state.delete_step = 0
                st.rerun()
    
    elif st.session_state.delete_step == 2:
        st.error("⚠️ 最終確認: この操作は取り消せません。本当に削除しますか？")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("はい、完全に削除します"):
                if delete_all_data():
                    st.session_state.delete_step = 0
                    st.rerun()
        with col2:
            if st.button("キャンセル"):
                st.session_state.delete_step = 0
                st.rerun()

def delete_all_data():
    try:
        # 現在のデータ数を確認
        supabase = init_connection()
        response = supabase.table('sales').select('*').execute()
        current_count = len(response.data)
        
        if current_count == 0:
            st.warning("削除するデータが存在しません。")
            return False
            
        # データを削除
        result = supabase.table('sales').delete().neq('id', 0).execute()
        
        # 削除後のデータ数を確認
        after_response = supabase.table('sales').select('*').execute()
        after_count = len(after_response.data)
        
        if after_count == 0:
            st.success(f"全てのデータ（{current_count}件）を削除しました。")
            # キャッシュをクリア
            load_data.clear()
            return True
        else:
            st.error(f"データの削除が完全ではありません。（削除前: {current_count}件, 削除後: {after_count}件）")
            return False
            
    except Exception as e:
        st.error(f"データの削除中にエラーが発生しました: {str(e)}")
        return False

def show_dashboard():
    """ダッシュボード画面"""
    st.header("📊 オークション分析ダッシュボード")
    
    # データの読み込み
    df = load_data()
    
    if df.empty:
        st.warning("データが存在しません")
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

    # データテーブルの表示
    st.subheader("📋 セラー別集計データ")
    
    # セラー別の集計データを作成
    seller_stats = df.groupby('seller').agg({
        'title': 'count',  # 出品件数
        'start_price': ['mean', 'min', 'max'],  # 開始価格の統計
        'final_price': ['sum', 'mean', 'min', 'max'],  # 落札価格の統計
        'bid_count': ['mean', 'max'],  # 入札数の統計
        'seller_url': 'first'  # 出品者URL
    }).reset_index()
    
    # カラム名を設定
    seller_stats.columns = [
        '出品者', '出品件数', 
        '平均開始価格', '最小開始価格', '最大開始価格',
        '落札価格合計', '平均落札価格', '最小落札価格', '最大落札価格',
        '平均入札数', '最大入札数', '出品者URL'
    ]
    
    # 数値のフォーマット
    seller_stats['出品件数'] = seller_stats['出品件数'].apply(format_number)
    seller_stats['平均開始価格'] = seller_stats['平均開始価格'].apply(format_price)
    seller_stats['最小開始価格'] = seller_stats['最小開始価格'].apply(format_price)
    seller_stats['最大開始価格'] = seller_stats['最大開始価格'].apply(format_price)
    seller_stats['落札価格合計'] = seller_stats['落札価格合計'].apply(format_price)
    seller_stats['平均落札価格'] = seller_stats['平均落札価格'].apply(format_price)
    seller_stats['最小落札価格'] = seller_stats['最小落札価格'].apply(format_price)
    seller_stats['最大落札価格'] = seller_stats['最大落札価格'].apply(format_price)
    seller_stats['平均入札数'] = seller_stats['平均入札数'].apply(lambda x: f"{x:.1f}")
    seller_stats['最大入札数'] = seller_stats['最大入札数'].apply(format_number)
    
    # 出品者名とURLを組み合わせてリンク形式に変換
    seller_stats['出品者リンク'] = seller_stats.apply(
        lambda row: f"[{row['出品者']}]({row['出品者URL']})", axis=1
    )
    
    # 表示する列を選択
    display_columns = [
        '出品者リンク', '出品件数',
        '平均開始価格', '最小開始価格', '最大開始価格',
        '落札価格合計', '平均落札価格', '最小落札価格', '最大落札価格',
        '平均入札数', '最大入札数'
    ]
    
    # データフレームを表示
    st.dataframe(
        seller_stats[display_columns].rename(columns={'出品者リンク': '出品者'}),
        hide_index=True
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