from fastapi import FastAPI
from pydantic import BaseModel

# FastAPI のインスタンス化
app = FastAPI()

# ルートディレクトリへの GET で Hello World の表示
@app.get("/")
def root():
    return {"message": "Hello World"}