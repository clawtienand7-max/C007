"""
YouTube 整合模組 — YouTube Data API v3 + OAuth + yt-dlp
功能：搜尋 / 上載 / 下載 / 頻道管理 / 自動操控
"""
import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

import aiofiles
import httpx
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.config import get_settings

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
TOKEN_FILE = Path("memory/youtube_token.json")
CREDS_FILE = Path("memory/youtube_oauth_creds.json")


class YouTubeClient:
    """YouTube Data API v3 + yt-dlp 整合客戶端"""

    def __init__(self):
        self.settings = get_settings()
        self._service = None
        self._creds: Optional[Credentials] = None

    # ─── 認證 ──────────────────────────────────────────────────────────────

    def _load_token(self) -> Optional[Credentials]:
        if TOKEN_FILE.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
                if creds and creds.valid:
                    return creds
            except Exception:
                pass
        return None

    def authenticate_oauth(self) -> str:
        """啟動 OAuth 流程，返回授權 URL（需要授權，跳過）"""
        if not CREDS_FILE.exists():
            return "缺少 OAuth 憑證檔案（memory/youtube_oauth_creds.json）— 請先設定"
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
        flow.run_local_server(port=8765, open_browser=False)
        creds = flow.credentials
        TOKEN_FILE.parent.mkdir(exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json())
        self._creds = creds
        return "YouTube OAuth 認證成功"

    def _get_service(self):
        if self._service:
            return self._service
        self._creds = self._load_token()
        if not self._creds:
            raise RuntimeError("YouTube 未認證 — 請先完成 OAuth 授權")
        self._service = build("youtube", "v3", credentials=self._creds)
        return self._service

    def is_authenticated(self) -> bool:
        try:
            creds = self._load_token()
            return creds is not None and creds.valid
        except Exception:
            return False

    # ─── 搜尋 ──────────────────────────────────────────────────────────────

    async def search(self, query: str, max_results: int = 10,
                     video_type: str = "video") -> list[dict]:
        """搜尋 YouTube 影片"""
        api_key = self.settings.youtube_api_key
        if not api_key:
            raise ValueError("缺少 YOUTUBE_API_KEY")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": query,
                    "type": video_type,
                    "maxResults": max_results,
                    "key": api_key,
                    "relevanceLanguage": "zh-HK",
                },
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
        return [
            {
                "id": item.get("id", {}).get("videoId", ""),
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "published": item["snippet"]["publishedAt"],
                "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
                "description": item["snippet"]["description"][:200],
                "url": f"https://www.youtube.com/watch?v={item.get('id', {}).get('videoId', '')}",
            }
            for item in items
        ]

    async def get_video_info(self, video_id: str) -> dict:
        """取得單一影片詳細資訊"""
        api_key = self.settings.youtube_api_key
        if not api_key:
            raise ValueError("缺少 YOUTUBE_API_KEY")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,statistics,contentDetails",
                    "id": video_id,
                    "key": api_key,
                },
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
        if not items:
            return {}
        item = items[0]
        return {
            "id": video_id,
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
            "description": item["snippet"]["description"],
            "published": item["snippet"]["publishedAt"],
            "views": item["statistics"].get("viewCount", "0"),
            "likes": item["statistics"].get("likeCount", "0"),
            "comments": item["statistics"].get("commentCount", "0"),
            "duration": item["contentDetails"]["duration"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }

    async def list_my_uploads(self, max_results: int = 20) -> list[dict]:
        """列出自己頻道的已上載影片（需要 OAuth）"""
        svc = self._get_service()
        channels = svc.channels().list(part="contentDetails", mine=True).execute()
        playlist_id = (
            channels["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        )
        playlist_items = (
            svc.playlistItems()
            .list(part="snippet", playlistId=playlist_id, maxResults=max_results)
            .execute()
        )
        return [
            {
                "id": item["snippet"]["resourceId"]["videoId"],
                "title": item["snippet"]["title"],
                "published": item["snippet"]["publishedAt"],
                "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
            }
            for item in playlist_items.get("items", [])
        ]

    # ─── 上載 ──────────────────────────────────────────────────────────────

    async def upload_video(
        self,
        file_path: str,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        privacy: str = "private",
        progress_callback=None,
    ) -> dict:
        """上載影片到 YouTube（需要 OAuth + 授權確認）"""
        svc = self._get_service()
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": "22",
                "defaultLanguage": "zh-HK",
            },
            "status": {"privacyStatus": privacy},
        }
        media = MediaFileUpload(
            file_path,
            mimetype="video/*",
            resumable=True,
            chunksize=1024 * 1024 * 10,
        )
        request = svc.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status and progress_callback:
                progress_callback(int(status.progress() * 100))
        return {"video_id": response["id"], "url": f"https://youtu.be/{response['id']}"}

    # ─── 下載（yt-dlp）─────────────────────────────────────────────────────

    async def download_video(
        self,
        url: str,
        output_dir: str = "downloads",
        format: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
        audio_only: bool = False,
        progress_callback=None,
    ) -> str:
        """用 yt-dlp 下載影片"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        cmd = ["yt-dlp", "--no-playlist", "-o", f"{output_dir}/%(title)s.%(ext)s"]
        if audio_only:
            cmd += ["-x", "--audio-format", "mp3"]
        else:
            cmd += ["-f", format]
        cmd.append(url)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"yt-dlp 下載失敗: {stderr.decode()[:500]}")
        last_line = stdout.decode().strip().split("\n")[-1]
        return last_line

    async def get_download_info(self, url: str) -> dict:
        """取得影片下載資訊（不下載）"""
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--dump-json", "--no-playlist", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"yt-dlp 查詢失敗: {stderr.decode()[:300]}")
        info = json.loads(stdout.decode())
        return {
            "id": info.get("id"),
            "title": info.get("title"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "formats": [
                {"format_id": f["format_id"], "ext": f.get("ext"), "quality": f.get("quality")}
                for f in info.get("formats", [])[-5:]
            ],
        }

    # ─── 播放清單管理 ───────────────────────────────────────────────────────

    async def create_playlist(self, title: str, description: str = "",
                               privacy: str = "private") -> dict:
        svc = self._get_service()
        result = svc.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": title, "description": description},
                "status": {"privacyStatus": privacy},
            },
        ).execute()
        return {"playlist_id": result["id"], "title": result["snippet"]["title"]}

    async def add_to_playlist(self, playlist_id: str, video_id: str) -> bool:
        svc = self._get_service()
        svc.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        ).execute()
        return True


_client: Optional[YouTubeClient] = None


def get_youtube_client() -> YouTubeClient:
    global _client
    if _client is None:
        _client = YouTubeClient()
    return _client
