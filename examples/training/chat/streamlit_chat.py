# 必要なモジュールのインポート
import streamlit as st
import requests
import json

# Streamlit アプリの設定
st.title("Simple Chat App")
st.sidebar.title("モード選択")

# チャットのモードの切り替え
endpoints = {
    "フリーチャット": 'free_chat',
    "RAGチャット": 'rag_chat'
}

# ラジオボタンでモードを選択
choice = st.sidebar.radio("どちらかを選択してください", list(endpoints.keys()))
endpoint = 'http://localhost:8000/' + endpoints[choice]


# フォームを作成し、サブミットボタンでメッセージを送信
with st.form("chat_form"):
    user_input = st.text_input("質問を入力してください:")
    submit_button = st.form_submit_button("Submit")
    
# サブミットボタンが押されたときに応答を取得して表示
if submit_button and user_input:
    # ヘッダー
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    # リクエストを送信しレスポンスを受け取る
    response = requests.post(
        endpoint, 
        headers=headers, 
        data=json.dumps({"user_id": "XXXX", "message": user_input})
    )
    res_json = response.json()
    st.write(res_json['content'])