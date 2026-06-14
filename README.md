# Decision RAG Assistant

Azure OpenAI、Azure AI Search、Cosmos DB、Blob Storageを利用して、決裁申請書の下書きと不足チェックを生成するStreamlit/FastAPIアプリです。

## 1. Setup

```powershell
lecture\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`へAzure Portalで確認した値を設定してください。リポジトリに含まれていた旧キーは使用せず、再発行したキーを利用してください。

## 2. Local mode

Azureへ接続せず画面とAPIを確認する場合:

```powershell
$env:APP_STORAGE_MODE="local"
uvicorn backend.app.main:app --reload --port 8000
```

別のターミナル:

```powershell
streamlit run frontend/app.py --server.port 8501
```

- Streamlit: http://localhost:8501
- FastAPI docs: http://localhost:8000/docs

## 3. Azure mode

`.env`を設定した後、既存リソース内に本アプリ専用のコンテナとインデックスを作成します。

```powershell
python -m scripts.bootstrap_azure
$env:APP_STORAGE_MODE="azure"
uvicorn backend.app.main:app --reload --port 8000
streamlit run frontend/app.py --server.port 8501
```

`bootstrap_azure`はAzureアカウント自体を作成せず、接続確認とアプリ専用データ構造の作成だけを行います。

## 4. Test

```powershell
pytest
```

研修用コードは `examples/training/` に保管しています。
