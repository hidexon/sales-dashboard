import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import random
import json

# ページ設定
st.set_page_config(
    page_title="テストデータ追加",
    page_icon="📊",
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

def insert_single_record():
    """単一のレコードを挿入してテスト"""
    supabase = init_connection()
    if not supabase:
        return "データベース接続エラー"

    try:
        # 1件のテストデータ
        test_data = {
            "name": "テスト商品",
            "price": 1000,
            "created_at": datetime.now().isoformat()
        }

        # データ構造の確認
        st.write("挿入するデータ:", test_data)
        
        # 単一レコードの挿入
        response = supabase.table('auction_items').insert(test_data).execute()
        
        # レスポンスの確認
        st.write("レスポンス:", response)
        
        return "テストレコードを追加しました"
    except Exception as e:
        st.error(f"詳細なエラー情報: {str(e)}")
        return f"エラーが発生しました: {str(e)}"

def check_table_structure():
    """テーブル構造の確認"""
    supabase = init_connection()
    if not supabase:
        return "データベース接続エラー"

    try:
        # テーブル構造の確認
        response = supabase.table('auction_items').select('*').limit(1).execute()
        st.write("テーブル構造:", response)
        return "テーブル構造を確認しました"
    except Exception as e:
        st.error(f"テーブル構造確認エラー: {str(e)}")
        return f"エラーが発生しました: {str(e)}"

# メイン処理
st.title("テストデータ追加")

# テーブル構造の確認ボタン
if st.button("テーブル構造を確認"):
    result = check_table_structure()
    st.write(result)

# 単一レコード追加のテスト
if st.button("テストレコードを1件追加"):
    result = insert_single_record()
    st.write(result)

# Secretsの確認
if st.button("接続情報を確認"):
    try:
        st.write("SUPABASE_URL:", st.secrets["SUPABASE_URL"])
        # KEYは一部のみ表示
        key = st.secrets["SUPABASE_KEY"]
        st.write("SUPABASE_KEY:", f"{key[:10]}...{key[-10:]}")
    except Exception as e:
        st.error(f"Secrets確認エラー: {str(e)}")