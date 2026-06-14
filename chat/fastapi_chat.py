from fastapi import FastAPI
from pydantic import BaseModel
import os
from langchain_openai import AzureChatOpenAI
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores.azuresearch import AzureSearch
from langchain_core.prompts import PromptTemplate

# インスタンス化
app = FastAPI()

# 入力するデータ型の定義
class UserInput(BaseModel):
    user_id: str
    message: str

# トップページ
@app.get('/')
def index():
    return {'message': 'chat'}

# Azure リソースへの接続設定
# AOAI を使うために環境変数を設定
os.environ["AZURE_OPENAI_API_KEY"] = 'DYtn18AGRugHbIMGV9M9hgfO3yGwVaUAgsgCQQewFURsEotHGMWRJQQJ99CEACYeBjFXJ3w3AAABACOG9Blt'
os.environ["AZURE_OPENAI_ENDPOINT"] = 'https://20260526-python.openai.azure.com/'
os.environ["OPENAI_API_TYPE"] = 'azure'
os.environ["OPENAI_API_VERSION"] = '2024-02-15-preview'

# AI Search への接続情報
vector_store_address = 'https://20260526-python.search.windows.net'
vector_store_password = 'DWb4xLp5yRS7MFaVGh7vzR9Jx2RA40JRAHM6q7x1A7AzSeBNXy5h'
index_name = '20260526python'

# Chat モデルの定義
llm = AzureChatOpenAI(
    azure_deployment='gpt-4o-mini',
    temperature=0.2
)

# Embedding モデルの定義
embeddings = AzureOpenAIEmbeddings(
    model="text-embedding-ada-002",
    deployment="text-embedding-ada-002",
    chunk_size=1
)

# Azure Search の定義
vector_store = AzureSearch(
    azure_search_endpoint=vector_store_address,
    azure_search_key=vector_store_password,
    index_name=index_name,
    embedding_function=embeddings.embed_query,
)


# chain の実装
"""
フリーチャット
"""
free_chat_template = "あなたは優秀なアシスタントです。以下のメッセージに対して自然な会話を生成しなさい。\n\n{message}"
free_chat_prompt = PromptTemplate(
    template=free_chat_template,
    input_variables=["message"]
)

def free_chat(message):
    free_chat_chain = free_chat_prompt | llm
    res = free_chat_chain.invoke({"message": message})
    return res

# フリーチャットのエンドポイント
@app.post('/free_chat')
def free_chat_endpoint(user_input: UserInput):
    message = user_input.message    
    res = free_chat(message)
    return {
            'content': res.content, 
            'response_metadata': res.response_metadata
            }


"""
RAG チャット
"""
rag_chat_prompt_template = """

## 役割
あなたはキカガクのカスタマーサポートです。
以下の与えられた入力を前提として、顧客の問合せに対する回答を作成してください。

## 顧客からの質問
{question}

## 入力情報
顧客の質問に対して、事前に社内のデータベースからベクトル検索を行い以下の検索結果が得られています。

### 検索結果１：
{doc1}

### 検索結果２：
{doc2}

### 検索結果３：
{doc3}

## 出力
"""
# テンプレート化
rag_chat_prompt = PromptTemplate(
    template=rag_chat_prompt_template,
    input_variables=["question", "doc1", "doc2", "doc3"]
)

def rag_chat(question):
    # キーワードを元に検索（３件を指定）
    docs = vector_store.similarity_search_with_relevance_scores(
        query=question,
        k=3,
    )
    # 質問と回答のチェーン（連鎖）をつくる
    rag_chat_chain = rag_chat_prompt | llm
    res = rag_chat_chain.invoke({
        "question": question,
        "doc1": docs[0][0].page_content,
        "doc2": docs[1][0].page_content, 
        "doc3": docs[2][0].page_content,
    })
    return docs, res

# RAG チャットのエンドポイント
@app.post('/rag_chat')
def rag_chat_endpoint(user_input: UserInput):
    question = user_input.message    
    docs, res = rag_chat(question)
    docs_info = []
    for doc in docs:     
        docs_info.append({
            "content": doc[0].page_content,
            "relevance_score": doc[1]
        })
    return {
            'content': res.content,
            'response_metadata': res.response_metadata, 
            'docs': docs_info
            }