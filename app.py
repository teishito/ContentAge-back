# ====================================
# 🔧 ライブラリと初期設定の読み込み
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

# 環境変数読み込み
load_dotenv()

# ====================================
# 🚀 FastAPI アプリケーション作成
# ====================================
app = FastAPI()

# ====================================
# 🌐 CORS 設定
# ====================================
origins = [
    "*",  # 一旦全許可（フロント確認用）
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ====================================
# 🔐 Azure Blob Storage 接続
# ====================================
azure_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if not azure_connection_string:
    raise ValueError("❌ AZURE_STORAGE_CONNECTION_STRING が設定されていません")

blob_service_client = BlobServiceClient.from_connection_string(azure_connection_string)
container_name = "instagram"

print("✅ Azure Blob Storage 接続成功:", blob_service_client.account_name)

# ====================================
# 📦 リクエストモデル定義
# ====================================
class PostURL(BaseModel):
    url: str

# ====================================
# 🧪 動作確認用エンドポイント
# ====================================
@app.get("/api/hello")
async def hello_world():
    return JSONResponse(content={"message": "Hello World"})


# ====================================
# 🖼 Instagram投稿データ取得＆アップロード
# ====================================
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
        print("❌ エラー:", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})


# ====================================
# ▶️ ローカル実行（開発用）
# ====================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting FastAPI on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
