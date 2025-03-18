import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import random
import pytz

# ページ設定
st.set_page_config(
    page_title="売上ダッシュボード",
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

def insert_test_data():
    """テストデータの挿入"""
    supabase = init_connection()
    if not supabase:
        return "データベース接続エラー"

    try:
        # 30日分のテストデータを生成
        test_data = []
        current_date = datetime.now(pytz.timezone('Asia/Tokyo'))
        
        # 商品名のリスト
        products = [
            "Nintendo Switch",
            "PlayStation 5",
            "iPad Pro",
            "MacBook Air",
            "AirPods Pro"
        ]
        
        # 販売者と購入者のリスト
        sellers = ["seller_A", "seller_B", "seller_C"]
        buyers = ["buyer_X", "buyer_Y", "buyer_Z"]

        for i in range(30):
            date = current_date - timedelta(days=i)
            # 1日あたり3〜7件のデータを生成
            for _ in range(random.randint(3, 7)):
                product = random.choice(products)
                start_price = random.randint(10000, 50000)
                bid_count = random.randint(1, 10)
                final_price = start_price + (random.randint(1000, 5000) * bid_count)
                
                data = {
                    "timestamp": date.isoformat(),
                    "title": product,
                    "start_price": start_price,
                    "final_price": final_price,
                    "bid_count": bid_count,
                    "buyer": random.choice(buyers),
                    "seller": random.choice(sellers),
                    "product_url": f"https://example.com/item{random.randint(1000, 9999)}"
                }
                test_data.append(data)
        
        # データの挿入
        response = supabase.table('sales').insert(test_data).execute()
        return f"{len(test_data)}件のテストデータを追加しました。"
    
    except Exception as e:
        st.error(f"詳細なエラー情報: {str(e)}")
        return f"エラーが発生しました: {str(e)}"

# メイン処理
st.title("テストデータ追加")

if st.button("テストデータを追加"):
    result = insert_test_data()
    st.write(result)

# 現在のデータを確認
if st.button("現在のデータを確認"):
    supabase = init_connection()
    if supabase:
        try:
            response = supabase.table('sales').select('*').order_by('timestamp', desc=True).execute()
            df = pd.DataFrame(response.data)
            if not df.empty:
                st.write("データ件数:", len(df))
                # タイムスタンプを日本時間に変換
                df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('Asia/Tokyo')
                # 表示するカラムの順序を指定
                columns = [
                    'timestamp', 'title', 'start_price', 'final_price', 
                    'bid_count', 'buyer', 'seller', 'product_url'
                ]
                st.dataframe(
                    df[columns],
                    column_config={
                        "timestamp": st.column_config.DatetimeColumn(
                            "日時",
                            format="YYYY-MM-DD HH:mm"
                        ),
                        "title": "商品名",
                        "start_price": st.column_config.NumberColumn(
                            "開始価格",
                            format="¥%d"
                        ),
                        "final_price": st.column_config.NumberColumn(
                            "最終価格",
                            format="¥%d"
                        ),
                        "bid_count": "入札数",
                        "buyer": "購入者",
                        "seller": "販売者",
                        "product_url": st.column_config.LinkColumn("商品URL")
                    }
                )
            else:
                st.write("データが存在しません")
        except Exception as e:
            st.error(f"データ確認エラー: {str(e)}")