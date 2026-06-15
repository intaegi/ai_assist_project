# Decision RAG Assistant

Azure OpenAI、Azure AI Search、Blob Storageを利用して、決裁申請書の下書き、
不足書類、文書間の金額・取引先・期間差異を確認するStreamlit/FastAPIアプリです。
現在の設定では履歴と設定を`data/database.json`へ保存します。

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
python -m scripts.check_azure_connections --config-only
python -m scripts.bootstrap_azure
python -m scripts.check_azure_connections
$env:APP_STORAGE_MODE="azure"
uvicorn backend.app.main:app --reload --port 8000
streamlit run frontend/app.py --server.port 8501
```

`bootstrap_azure`はAzureアカウント自体を作成せず、接続確認とアプリ専用データ構造の作成だけを行います。

Cosmos DBアカウントの作成を後回しにする場合は、`.env`へ次を設定します。

```dotenv
APP_STORAGE_MODE=azure
AZURE_COSMOS_ENABLED=false
```

この構成ではAzure OpenAI、Azure AI Search、Blob Storageを利用し、決裁設定と作成履歴だけを
`data/database.json`へ自動保存します。Cosmos DBを利用開始するときはアカウントを作成し、
EndpointとKeyを設定して`AZURE_COSMOS_ENABLED=true`へ変更します。

環境変数名は研修例と同じ`AZURE_SEARCH_ENDPOINT`です。`AZURE_SEARCH_ENDPOIN`では認識されません。
本アプリ専用のインデックス名は`AZURE_SEARCH_INDEX_NAME`で指定します。現在の環境では`lim-rag`を使用します。

Blob Storageは`AZURE_STORAGE_CONNECTION_STRING`で指定したStorage Accountを使用します。
ユーザーがアップロードした原本は次のパスへ保存されます。
`uploaded-documents/cases/{case_id}/original/{file_id}_{file_name}`

Blob Storage内の保存先:

- `config-materials`: 初期設定の基準資料
- `uploaded-documents`: 新規作成でアップロードした原本
- `extracted-texts`: PDFから抽出したページ別テキストJSON
- `generated-outputs`: AI生成・再生成したバージョン別JSON
- `lim-pbl-search-knowledge`: Indexerへ渡す基準資料・過去決裁の正規化JSON

Storage Account、Blobコンテナ、AI Searchリソースはそれぞれ独立したAzureリソース名です。
そのためBlob側に`lim`というコンテナがなくても問題ありません。現在は
Data source `lim-decision-rag-blob-datasource`がコンテナ`lim-pbl-search-knowledge`の
`documents/`プレフィックスを参照します。接続先は`python -m scripts.check_azure_connections`
で確認できます。

Azureモードの既定値はPull Indexer方式です。`bootstrap_azure`がBlob Data source、
Text SplitとAzure OpenAI Embeddingを行うSkillset、5分間隔のIndexerを作成します。
`POST /settings/reindex`は検索対象を`lim-pbl-search-knowledge/documents/`へ同期してIndexerを即時実行します。

当初の直接登録方式は、小規模MVPでアプリが既に抽出・正規化した短い文書を同期的に登録するには
単純で、Data sourceやIndexerが不要という利点がありました。一方、Blob変更検知、長文分割、
再試行、運用状態確認はIndexer方式が適しています。緊急時の互換用として
`AZURE_SEARCH_INGESTION_MODE=direct`を設定すると`SearchClient.upload_documents()`方式へ戻せます。

Cosmos DBを無効にした場合、BlobとSearchはAzureに保存されますが、案件・設定・履歴メタデータは
実行ホストの`data/database.json`に残ります。本番運用では複数インスタンス共有、バックアップ、
同時更新のためCosmos DBを有効にする構成を推奨します。

## 4. Test

```powershell
pytest
```

UIテスト資料を生成する場合:

```powershell
python -m scripts.generate_test_documents
```

- [UIテスト項目書（韓国語）](docs/ui_test_cases_ko.md)
- [主要ソースコード説明書（韓国語）](docs/source_code_guide_ko.md)
- [UIテストデータ一覧](sample_data/test_documents/README.md)

研修用コードは `examples/training/` に保管しています。
