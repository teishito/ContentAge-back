# ====================================
# 🚀 Instagram → Azure Blob アップロード専用 FastAPI
# ====================================

import os
import re
import uuid
import requests
import instaloader
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv

# ====================================
# 🔧 初期設定
# ====================================
load_dotenv()  # .env 読み込み

app = FastAPI()

# ✅ CORS設定（必要に応じて追加）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Next.jsなどから呼び出す場合
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================================
# ☁️ Azure Blob Storage 設定
# ====================================
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if not AZURE_STORAGE_CONNECTION_STRING:
    raise ValueError("❌ AZURE_STORAGE_CONNECTION_STRING が設定されていません")

CONTAINER_NAME = "instagram"  # Blobコンテナー名
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

# ====================================
# 📥 リクエストモデル
# ====================================
class PostURL(BaseModel):
    url: str

# ====================================
# 🖼 Instagram投稿データ取得＆アップロード
# ====================================
@app.post("/api/fetch-instagram-post")
async def fetch_instagram_post(post: PostURL):
    try:
        # Instagram投稿URLから shortcode 抽出
        shortcode_match = re.search(r"/p/([^/?#&]+)", post.url)
        if not shortcode_match:
            return JSONResponse(status_code=400, content={"error": "URLが正しくありません"})
        shortcode = shortcode_match.group(1)

        # Instaloaderで投稿データ取得
        loader = instaloader.Instaloader()
        post_data = instaloader.Post.from_shortcode(loader.context, shortcode)

        # 画像URLを取得
        image_url = post_data.url

        # 画像をダウンロード
        img_data = requests.get(image_url).content
        filename = f"{shortcode}_{uuid.uuid4().hex}.jpg"

        # Blobにアップロード
        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=filename)
        blob_client.upload_blob(
            img_data,
            overwrite=True,
            blob_type="BlockBlob",
            content_settings=ContentSettings(content_type="image/jpeg"),
        )

        # 公開URLを生成
        uploaded_image_url = (
            f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{filename}"
        )

        # 結果を返す
        result = {
            "image_url": uploaded_image_url,
            "caption": post_data.caption,
            "likes": post_data.likes,
            "comments": post_data.comments,
        }
        return result

    except Exception as e:
        print("❌ エラー:", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})
        
# ======================
# ▶️ ローカル実行（開発用）
# ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting FastAPI on port {PORT} with DB {MYSQL_DB_NAME}")
    uvicorn.run(app, host="0.0.0.0", port=port)
