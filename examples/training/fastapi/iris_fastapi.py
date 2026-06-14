# 基本ライブラリ
import streamlit as st
import pandas as pd
import requests
import json

# タイトル
st.title('Iris Classifier')

# サイドバー
st.sidebar.header('Input Features')
sepal_length = st.sidebar.slider('sepal length (cm)', min_value=0.0, max_value=10.0, step=0.1)
sepal_width = st.sidebar.slider('sepal width (cm)', min_value=0.0, max_value=10.0, step=0.1)
petal_length = st.sidebar.slider('petal length (cm)', min_value=0.0, max_value=10.0, step=0.1)
petal_width = st.sidebar.slider('petal width (cm)', min_value=0.0, max_value=10.0, step=0.1)


# 予測ボタン
if st.sidebar.button("Predict"):
    # メインパネル
    st.write('## Input Value')
    
    # インプットデータ（1行のデータフレーム）
    value_df = pd.DataFrame([],columns=['data','sepal length (cm)','sepal width (cm)','petal length (cm)','petal width (cm)'])
    record = pd.Series(['data',sepal_length, sepal_width, petal_length, petal_width], index=value_df.columns)
    value_df = pd.concat([value_df, record.to_frame().T], ignore_index=True)
    value_df.set_index('data',inplace=True)

    # 入力値の値
    st.write(value_df)

    # 予測の実行
    # エンドポイント
    url = 'http://localhost:8000/make_predictions'

    # ヘッダー
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    # ボディ
    data = {
        "sepal_length": sepal_length,
        "sepal_width": sepal_width,
        "petal_length": petal_length,
        "petal_width": petal_width
    }

    # リクエストを送信しレスポンスを受け取る
    response = requests.post(url, headers=headers, data=json.dumps(data))
    prediction = response.json()["prediction"]

    # ターゲットのリスト
    targets = ['setosa', 'versicolor', 'virginica']
    
    # 予測結果の表示
    st.write('## Prediction')
    st.write(prediction)
    # 予測結果の出力
    st.write('## Result')
    st.write('このアイリスはきっと',str(targets[int(prediction)]),'です!')