import os
import re
import uuid
import ssl
import tempfile
import requests
import instaloader
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv

# ============================================================
# 🌍 環境変数読み込み（ローカル開発時のみ .env 読み込み）
# ============================================================
if os.getenv("WEBSITE_SITE_NAME") is None:  # Azure環境では自動で環境変数を読む
    load_dotenv()

# ============================================================
# 🌐 FastAPI アプリ初期化
# ============================================================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 必要に応じて制限可能
    allow_methods=["*"],
    allow_headers=["*"]
)

# ============================================================
# 🔐 Azure Blob Storage 接続
# ============================================================
azure_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if not azure_connection_string:
    raise ValueError("❌ AZURE_STORAGE_CONNECTION_STRING が設定されていません")

blob_service_client = BlobServiceClient.from_connection_string(azure_connection_string)
container_name = "instagram"

print("✅ Azure Blob Storage 接続成功:", blob_service_client.account_name, flush=True)

# ============================================================
# 📦 リクエストモデル
# ============================================================
class PostURL(BaseModel):
    url: str

# ============================================================
# 🧪 動作確認用エンドポイント
# ============================================================
@app.get("/api/hello")
async def hello_world():
    return JSONResponse(content={"message": "Hello World"})

# ============================================================
# 🖼 Instagram投稿データ取得＆Blobアップロード
# ============================================================
@app.post("/api/fetch-instagram-post")
async def fetch_instagram_post(post: PostURL):
    try:
        # ======================================================
        # 1️⃣ Instagram URL から shortcode 抽出
        # ======================================================
        shortcode_match = re.search(r"/(p|reel)/([^/?#&]+)", post.url)
        if not shortcode_match:
            return JSONResponse(status_code=400, content={"error": "URLが正しくありません"})
        shortcode = shortcode_match.group(2)

        # ======================================================
        # 2️⃣ Instaloader 初期化 & ログイン処理
        # ======================================================
        loader = instaloader.Instaloader(dirname_pattern=tempfile.gettempdir())
        username = os.getenv("INSTAGRAM_USERNAME")
        password = os.getenv("INSTAGRAM_PASSWORD")

        if username and password:
            try:
                loader.login(username, password)
                print(f"✅ Instagram ログイン成功: {username}", flush=True)
            except Exception as e:
                print(f"⚠️ Instagramログイン失敗: {e}", flush=True)
        else:
            print("⚠️ 未ログイン状態で実行しています。非公開アカウントは取得できません。", flush=True)

        # ======================================================
        # 3️⃣ 投稿情報取得
        # ======================================================
        post_data = instaloader.Post.from_shortcode(loader.context, shortcode)

        # ======================================================
        # 4️⃣ メディア（画像 or 動画）情報取得
        # ======================================================
        is_video = post_data.is_video
        ext = "mp4" if is_video else "jpg"
        content_type = "video/mp4" if is_video else "image/jpeg"
        media_url = post_data.video_url if is_video else post_data.url

        # ======================================================
        # 5️⃣ 画像／動画データを取得
        # ======================================================
        ssl._create_default_https_context = ssl._create_unverified_context
        response = requests.get(media_url)
        response.raise_for_status()
        media_data = response.content

        filename = f"{shortcode}_{uuid.uuid4().hex}.{ext}"

        # ======================================================
        # 6️⃣ Azure Blob Storage にアップロード
        # ======================================================
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
        blob_client.upload_blob(
            media_data,
            overwrite=True,
            blob_type="BlockBlob",
            content_settings=ContentSettings(content_type=content_type)
        )

        uploaded_media_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{filename}"

        # ======================================================
        # 7️⃣ 結果返却
        # ======================================================
        result = {
            "media_url": uploaded_media_url,
            "caption": post_data.caption,
            "likes": post_data.likes,
            "comments": post_data.comments,
            "is_video": is_video
        }
        print(f"✅ アップロード完了: {uploaded_media_url}", flush=True)
        return result

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ エラー詳細:\n", error_details, flush=True)
        return JSONResponse(status_code=500, content={
            "error": str(e),
            "trace": error_details
        })

# ============================================================
# ▶️ ローカル実行用エントリーポイント
# ============================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting FastAPI on port {port}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port)
