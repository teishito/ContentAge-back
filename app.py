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

# -------------------------------
# 🌍 環境変数読み込み
# -------------------------------
load_dotenv()

app = FastAPI()

# -------------------------------
# 🌐 CORS 設定
# -------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # フロント確認用に全許可（必要なら制限可）
    allow_methods=["*"],
    allow_headers=["*"]
)

# -------------------------------
# 🔐 Azure Blob Storage 接続
# -------------------------------
azure_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if not azure_connection_string:
    raise ValueError("❌ AZURE_STORAGE_CONNECTION_STRING が設定されていません")

blob_service_client = BlobServiceClient.from_connection_string(azure_connection_string)

# ✅ 正しいコンテナー名を使用
container_name = "instagram"

print("✅ Azure Blob Storage 接続成功:", blob_service_client.account_name)


# -------------------------------
# 📦 リクエストモデル
# -------------------------------
class PostURL(BaseModel):
    url: str


# -------------------------------
# 🧪 動作確認用
# -------------------------------
@app.get("/api/hello")
async def hello_world():
    return JSONResponse(content={"message": "Hello World"})


# -------------------------------
# 🖼 Instagram投稿データ取得＆Blobアップロード
# -------------------------------
@app.post("/api/fetch-instagram-post")
async def fetch_instagram_post(post: PostURL):
    try:
        # ✅ Instagram URLから shortcode 抽出
        shortcode_match = re.search(r"/p/([^/?#&]+)", post.url)
        if not shortcode_match:
            return JSONResponse(status_code=400, content={"error": "URLが正しくありません"})

        shortcode = shortcode_match.group(1)

        # ✅ Instaloaderで投稿情報取得
        loader = instaloader.Instaloader()
        post_data = instaloader.Post.from_shortcode(loader.context, shortcode)

        # ✅ 画像URL取得
        image_url = post_data.url

        # ✅ 画像を取得（バイナリ）
        response = requests.get(image_url)
        response.raise_for_status()
        img_data = response.content

        filename = f"{shortcode}_{uuid.uuid4().hex}.jpg"

        # ✅ Azure Blob Storageへアップロード
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        blob_client.upload_blob(
            img_data,
            overwrite=True,
            blob_type="BlockBlob",
            content_settings=ContentSettings(content_type="image/jpeg")
        )

        # ✅ アップロード後の公開URL
        uploaded_image_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{filename}"

        result = {
            "image_url": uploaded_image_url,
            "caption": post_data.caption,
            "likes": post_data.likes,
            "comments": post_data.comments,
        }
        return result

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ エラー詳細:\n", error_details)
        # 👇 Azure ログにも出す
        return JSONResponse(status_code=500, content={
            "error": str(e),
            "trace": error_details
        })


# -------------------------------
# ▶️ ローカル実行用
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting FastAPI on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
