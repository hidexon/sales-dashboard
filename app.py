import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import random

# ページ設定
st.set_page_config(
    page_title="データベース設定",
    page_icon="🛠️",
    layout="wide"
)

# Supabaseクライアントの初期化
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        client = create_client(url, key)
        st.success("Supabase接続成功")
        return client
    except Exception as e:
        st.error(f"接続エラー: {str(e)}")
        return None

def create_table():
    """テーブルの作成"""
    supabase = init_connection()
    if not supabase:
        return "データベース接続エラー"

    try:
        # SQLクエリの実行
        query = """
        CREATE TABLE IF NOT EXISTS auction_items (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
        );
        """
        
        # クエリの実行
        response = supabase.table('auction_items').select('*').execute()
        st.write("テーブル作成レスポンス:", response)
        
        return "テーブルを作成しました"
    except Exception as e:
        st.error(f"テーブル作成エラー: {str(e)}")
        return f"エラーが発生しました: {str(e)}"

def insert_test_data():
    """テストデータの挿入"""
    supabase = init_connection()
    if not supabase:
        return "データベース接続エラー"

    try:
        # テストデータの作成
        test_data = {
            "name": "テスト商品",
            "price": 1000
        }
        
        # データの挿入
        response = supabase.table('auction_items').insert(test_data).execute()
        st.write("データ挿入レスポンス:", response)
        
        return "テストデータを追加しました"
    except Exception as e:
        st.error(f"データ挿入エラー: {str(e)}")
        return f"エラーが発生しました: {str(e)}"

# メイン処理
st.title("データベース設定")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. テーブル作成")
    if st.button("テーブルを作成"):
        result = create_table()
        st.write(result)

with col2:
    st.subheader("2. テストデータ追加")
    if st.button("テストデータを追加"):
        result = insert_test_data()
        st.write(result)

# テーブル構造の確認
if st.button("テーブル構造を確認"):
    supabase = init_connection()
    if supabase:
        try:
            response = supabase.table('auction_items').select('*').limit(1).execute()
            st.write("テーブル構造:", response)
        except Exception as e:
            st.error(f"テーブル構造確認エラー: {str(e)}")