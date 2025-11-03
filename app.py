import os
import re
import uuid
import requests
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

# ✅ コンテナー名
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
# 📸 Instagram投稿データ取得＆Blobアップロード
# -------------------------------
@app.post("/api/fetch-instagram-post")
async def fetch_instagram_post(post: PostURL):
    try:
        # ✅ Instagram URLから shortcode 抽出
        shortcode_match = re.search(r"/p/([^/?#&]+)", post.url)
        if not shortcode_match:
            return JSONResponse(status_code=400, content={"error": "URLが正しくありません"})
        shortcode = shortcode_match.group(1)

        # ✅ 公開APIを利用して投稿情報取得（非ログイン対応）
        api_url = f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(api_url, headers=headers)
        res.raise_for_status()
        data = res.json()

        # ✅ JSON構造から画像URLや本文などを取得
        media = data.get("graphql", {}).get("shortcode_media", {})
        image_url = media.get("display_url")
        caption = media.get("edge_media_to_caption", {}).get("edges", [{}])[0].get("node", {}).get("text", "")
        likes = media.get("edge_media_preview_like", {}).get("count", 0)
        comments = media.get("edge_media_to_parent_comment", {}).get("count", 0)

        if not image_url:
            raise Exception("Instagramデータが取得できませんでした")

        # ✅ 画像をダウンロード
        img_data = requests.get(image_url, headers=headers).content
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
            "caption": caption,
            "likes": likes,
            "comments": comments,
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
