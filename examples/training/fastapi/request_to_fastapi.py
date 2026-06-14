import requests
import json

# エンドポイント
url = 'http://localhost:8000/make_predictions'

# ヘッダー
headers = {
    'accept': 'application/json',
    'Content-Type': 'application/json'
}

# ボディ
data = {
    'sepal_length': 0.1,
    'sepal_width': 0.2,
    'petal_length': 0.3,
    'petal_width': 0.4
}

# リクエストを送信しレスポンスを受け取る
response = requests.post(url, headers=headers, data=json.dumps(data))

# レスポンスの表示
print(response.status_code)
print(response.json())