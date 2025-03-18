import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import random

# Supabaseクライアントの初期化
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def insert_test_data():
    supabase = init_connection()
    
    # テストデータの生成
    current_date = datetime.now()
    test_data = []
    
    # 30日分のデータを生成
    for i in range(30):
        date = current_date - timedelta(days=i)
        # その日の3〜7件のデータを生成
        for _ in range(random.randint(3, 7)):
            data = {
                "name": f"商品{random.randint(1, 5)}",
                "price": random.randint(1000, 10000),
                "created_at": date.isoformat()
            }
            test_data.append(data)
    
    # データの挿入
    try:
        response = supabase.table('auction_items').insert(test_data).execute()
        return f"{len(test_data)}件のテストデータを追加しました。"
    except Exception as e:
        return f"エラーが発生しました: {str(e)}"

# メイン処理
st.title("テストデータ追加")

if st.button("テストデータを追加"):
    result = insert_test_data()
    st.write(result)