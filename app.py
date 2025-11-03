# ====================================
# 🔧 ライブラリと初期設定の読み込み
# ====================================
import os
import urllib.parse
import openai
from openai import AzureOpenAI
from fastapi import FastAPI, Request, HTTPException, Depends, APIRouter  # ← 追加　　Githubに追加！　HTTPException, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import instaloader
import re
from collections import defaultdict
from instaloader import Instaloader, Profile
from typing import List
import csv
import tempfile
from azure.storage.blob import BlobServiceClient
import requests
from urllib.parse import urlparse
import uuid
import mysql.connector
from datetime import datetime

from fastapi.responses import FileResponse  # 2025.04.22 15時　追加✅ Githubに追加！
import pymysql # 2025.04.22 15時　追加✅ Githubに追加！

# Line26～121 追加✅ Githubに追加！
from typing import Dict  # ← 追加  Githubに追加！
import bcrypt  # ← 追加  Githubに追加！ # パスワードハッシュ化のため追加
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime  # ← DateTime を追加
from sqlalchemy.ext.declarative import declarative_base # ← 追加  Githubに追加！
from sqlalchemy.orm import sessionmaker, relationship, Session  # ← Session を追加
import json # ← 追加  Githubに追加！
from passlib.context import CryptContext # ← 追加  Githubに追加！ # パスワードハッシュ化のため追加
from dotenv import load_dotenv # ← 追加  Githubに追加！
load_dotenv() # ← 追加  Githubに追加！

# =======================
# Azure 環境変数から取得
# =======================
MYSQL_DB_HOST = os.getenv("MYSQL_DB_HOST")
MYSQL_DB_USER = os.getenv("MYSQL_DB_USER")
MYSQL_DB_PASSWORD = urllib.parse.quote_plus(os.getenv("MYSQL_DB_PASSWORD"))  # URLエンコード
MYSQL_DB_NAME = os.getenv("MYSQL_DB_NAME")
MYSQL_DB_PORT = os.getenv("MYSQL_DB_PORT", "3306")
PORT = int(os.getenv("PORT", 8080))  # デフォルト 8080

print("✅ .env 読み込みチェック:")
print("MYSQL_DB_HOST:", MYSQL_DB_HOST)
print("MYSQL_DB_USER:", MYSQL_DB_USER)
print("MYSQL_DB_PASSWORD:", MYSQL_DB_PASSWORD)
print("MYSQL_DB_NAME:", MYSQL_DB_NAME)
print("MYSQL_DB_PORT:", MYSQL_DB_PORT)

# SSL 証明書のパス
SSL_CERT_PATH = os.path.join(os.path.dirname(__file__), "DigiCertGlobalRootCA.crt.pem")

# MySQL接続情報（SSL 証明書を適用）
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{MYSQL_DB_USER}:{MYSQL_DB_PASSWORD}@{MYSQL_DB_HOST}:{MYSQL_DB_PORT}/{MYSQL_DB_NAME}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"ssl": {"ssl_ca": SSL_CERT_PATH}}  # 👈 SSL 証明書を適用
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =============================
# テーブルモデル定義
# =============================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    password = Column(String(100))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    text = Column(String(255))

class Questionnaire(Base):
    __tablename__ = "questionnaires"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    store_id = Column(Integer, ForeignKey("stores.id"))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class Answer(Base):  #✅追加 再々更新！
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True, index=True)
    questionnaire_id = Column(Integer, ForeignKey("questionnaires.id"))
    question_key = Column(String(50))  # 例: "0-1"
    answer_value = Column(String(255))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class DiagnosisAnswer(Base): #✅追加
    __tablename__ = "diagnosis_answers"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    store_id = Column(Integer, ForeignKey("stores.id"))
    question_key = Column(String(20))
    answer = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

# =============================
# DB初期化
# =============================
Base.metadata.create_all(bind=engine)
# Line26～121 追加✅ Githubに追加！

# ================================
# 🚀 FastAPI アプリケーション作成
# ================================
app = FastAPI()

# Line128～132 追加✅ Githubに追加！
origins = [
    "https://tech0-gen-8-step4-richconnections-front-cmg3bsdnbwegepgk.germanywestcentral-01.azurewebsites.net",  # Next.js デフォルトポート
]
# Line128～132 追加✅ Githubに追加！

# ==================================
# 🌐 CORS（クロスオリジン）設定
# ==================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # 追加✅ Githubに追加！
    allow_methods=["*"],
    allow_headers=["*"]
)

# Line145～155 追加✅ Githubに追加！
# =============================
# DBセッションを取得する依存関数   
# =============================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# Line145～155 追加✅ Githubに追加！

# =======================
# 🔐 Azure 環境変数から取得
# =======================
# OpenAI API 関連
openai.api_type = "azure"
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.api_base = os.getenv("OPENAI_API_BASE")
openai.api_version = os.getenv("OPENAI_API_VERSION")
model = os.getenv("OPENAI_MODEL")

# Azure Blob Storage 接続
azure_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if not azure_connection_string:
    raise ValueError("❌ AZURE_STORAGE_CONNECTION_STRING が設定されていません")
blob_service_client = BlobServiceClient.from_connection_string(azure_connection_string)
container_name = "instagram-posts"

# MySQL 接続情報
MYSQL_DB_CONFIG = {
    "host": os.getenv("MYSQL_DB_HOST"),
    "port": int(os.getenv("MYSQL_DB_PORT", 3306)),
    "user": os.getenv("MYSQL_DB_USER"),
    "password": urllib.parse.quote_plus(os.getenv("MYSQL_DB_PASSWORD")),
    "database": os.getenv("MYSQL_DB_NAME"),
    "ssl_ca": os.path.join(os.path.dirname(__file__), "DigiCertGlobalRootCA.crt.pem"),
    "ssl_verify_cert": True
}

# ログ出力
print("✅ OPENAI_BASE:", openai.api_base)
print("✅ MODEL:", model)
print("✅ API_VERSION:", openai.api_version)
print("✅ AZURE_STORAGE:", blob_service_client.account_name)
print("✅ MySQL HOST:", MYSQL_DB_CONFIG["host"])

# ======================
# 📦 リクエストモデル定義
# ======================
class AnalysisRequest(BaseModel):
    prompt: str

class ImageRequest(BaseModel):
    analysis_summary: str

class PostURL(BaseModel):
    url: str

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str

# Line208～238 追加✅ Githubに追加！
class UserIn(BaseModel):
    name: str
    email: str
    password: str

class AnswerIn(BaseModel):
    question_id: int
    answer_text: str

class AnswerInput(BaseModel):
    user_id: int
    store_id: int
    answers: Dict[str, str]  # 例: { "0-1": "Yes", ... }

class QuestionnaireIn(BaseModel):
    user_id: int
    store_id: int
    answers: List[AnswerIn]

class SubmitRequest(BaseModel): #✅追加
    answers: Dict # key: "0-0", value: "Yes"など ✅追加

class DiagnosisRequest(BaseModel):  #✅追加
    user_id: int
    store_id: int
    answers: Dict[str, str]

class Answers(BaseModel):
    answers: list[str]
# Line208～238 追加✅ Githubに追加！

# ============================
# 🧪 動作確認用エンドポイント
# ============================
@app.get("/api/hello")
async def hello_world():
    return JSONResponse(content={"message": "Hello World"})

# ====================================
# 🖼 Instagram投稿データ取得＆アップロード
# ====================================
from azure.storage.blob import BlobServiceClient, ContentSettings
import requests
import uuid

@app.post("/api/fetch-instagram-post")
async def fetch_instagram_post(post: PostURL):
    try:
        # Instagram URL から shortcode を抽出
        shortcode_match = re.search(r"/p/([^/?#&]+)", post.url)
        if not shortcode_match:
            return JSONResponse(status_code=400, content={"error": "URLが正しくありません"})

        shortcode = shortcode_match.group(1)

        # Instaloaderで投稿情報取得
        loader = instaloader.Instaloader()
        post_data = instaloader.Post.from_shortcode(loader.context, shortcode)

        # 画像URL取得
        image_url = post_data.url

        # 画像を取得（バイナリ）
        img_data = requests.get(image_url).content
        filename = f"{shortcode}_{uuid.uuid4().hex}.jpg"

        # Azure Storage へアップロード
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        blob_client.upload_blob(
            img_data,
            overwrite=True,
            blob_type="BlockBlob",
            content_settings=ContentSettings(content_type="image/jpeg")
        )

        # Azure上の公開URL
        uploaded_image_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{filename}"

        # 投稿情報とアップロードした画像URLを返す
        result = {
            "image_url": uploaded_image_url,
            "caption": post_data.caption,
            "likes": post_data.likes,
            "comments": post_data.comments,
        }
        return result

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
        
# ======================
# ▶️ ローカル実行（開発用）
# ======================
        print("❌ エラー:", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})
        
# ======================
# ▶️ ローカル実行（開発用）
# ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting FastAPI on port {PORT} with DB {MYSQL_DB_NAME}") #　追加✅　Github追加
    uvicorn.run(app, host="0.0.0.0", port=port)
