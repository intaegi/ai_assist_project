from fastapi import FastAPI
from pydantic import BaseModel
import pickle

# インスタンス化
app = FastAPI()

# 入力するデータ型の定義
class Iris(BaseModel):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float

# 学習済みのモデルの読み込み
model = pickle.load(open('./model/model_iris.pkl', 'rb'))

# トップページ
@app.get('/')
def index():
    return {"Iris": 'iris_prediction'}
    
# POST が送信された時（入力）と予測値（出力）の定義
@app.post('/make_predictions')
def make_predictions(features: Iris):
    sepal_length = features.sepal_length
    sepal_width = features.sepal_width
    petal_length = features.petal_length
    petal_width = features.petal_width    
    prediction = model.predict([[sepal_length, sepal_width, petal_length, petal_width]])[0]
    return {"prediction":str(prediction)}