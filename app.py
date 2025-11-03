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
    allow_origins=["*"],
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

        # ✅ Instaloaderの初期化とログイン処理
        loader = instaloader.Instaloader()
        username = os.getenv("INSTAGRAM_USERNAME")
        password = os.getenv("INSTAGRAM_PASSWORD")

        if username and password:
            try:
                loader.login(username, password)
                print(f"✅ Instagram ログイン成功: {username}")
            except Exception as e:
                print(f"⚠️ Instagramログイン失敗: {e}")
        else:
            print("⚠️ 未ログイン状態で実行しています。非公開アカウントは取得できません。")

        # ✅ 投稿情報取得
        post_data = instaloader.Post.from_shortcode(loader.context, shortcode)

        # ✅ 画像 or 動画を判定
        is_video = post_data.is_video
        ext = "mp4" if is_video else "jpg"
        content_type = "video/mp4" if is_video else "image/jpeg"

        # ✅ メディアURL取得
        media_url = post_data.video_url if is_video else post_data.url

        # ✅ バイナリデータ取得
        response = requests.get(media_url)
        response.raise_for_status()
        media_data = response.content

        filename = f"{shortcode}_{uuid.uuid4().hex}.{ext}"

        # ✅ Azure Blob Storageへアップロード
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        blob_client.upload_blob(
            media_data,
            overwrite=True,
            blob_type="BlockBlob",
            content_settings=ContentSettings(content_type=content_type)
        )

        # ✅ 公開URL生成
        uploaded_media_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{filename}"

        result = {
            "media_url": uploaded_media_url,
            "caption": post_data.caption,
            "likes": post_data.likes,
            "comments": post_data.comments,
            "is_video": is_video
        }
        return result

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ エラー詳細:\n", error_details)
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
