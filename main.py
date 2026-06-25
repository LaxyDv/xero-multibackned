import os
import shutil
import uuid
import yt_dlp
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

# Initialize the App
app = FastAPI(
    title="XeroTools Master Backend",
    description="Multi-platform Downloader by Xeno (XQD)",
    version="2.0"
)

# --- Data Models ---
class DownloadRequest(BaseModel):
    url: str
    type: str  # Options: 'video', 'audio', 'info'

# --- Helper Functions ---

def get_temp_folder():
    """Creates a unique temporary folder for each request to ensure privacy."""
    folder_id = str(uuid.uuid4())
    path = os.path.join("temp_downloads", folder_id)
    os.makedirs(path, exist_ok=True)
    return path

def clean_up(folder_path: str):
    """Deletes the folder after the file is sent to protect user privacy."""
    if os.path.exists(folder_path):
        try:
            shutil.rmtree(folder_path)
        except Exception as e:
            print(f"Error cleaning up: {e}")

def process_download(url: str, download_type: str, output_dir: str):
    """Core logic using yt-dlp to handle all platforms."""
    
    # Common options for all downloads
    ydl_opts = {
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True, # Download single video only, not whole playlist unless requested
    }

    # 1. VIDEO DOWNLOAD (MP4)
    if download_type == 'video':
        ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        ydl_opts['merge_output_format'] = 'mp4'

    # 2. AUDIO/MUSIC DOWNLOAD (MP3)
    elif download_type == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        # Change extension to mp3 in output name
        ydl_opts['outtmpl'] = f'{output_dir}/%(title)s.mp3'

    # 3. INFO ONLY (Get Title, Thumbnail, Duration without downloading file)
    elif download_type == 'info':
        ydl_opts['skip_download'] = True
        ydl_opts['dump_single_json'] = True

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info or download
            info = ydl.extract_info(url, download=(download_type != 'info'))
            
            if download_type == 'info':
                return {"status": "success", "data": info}

            # Find the generated file in the folder
            files = os.listdir(output_dir)
            if not files:
                raise Exception("No file was generated. The link might be invalid or private.")
            
            # Get the first file found (should be the only one)
            filename = files[0]
            filepath = os.path.join(output_dir, filename)
            
            return {"filepath": filepath, "filename": filename}

    except Exception as e:
        raise Exception(f"Processing failed: {str(e)}")

# --- API Endpoints ---

@app.get("/")
async def home():
    return {
        "message": "Welcome to XeroTools Backend (Node Active)",
        "supported_platforms": ["YouTube", "TikTok", "Instagram", "X (Twitter)", "Facebook", "Reddit", "Pinterest", "Twitch", "Vimeo", "Dailymotion"],
        "modes": ["video", "audio", "info"]
    }

@app.post("/download")
async def download_tool(request: DownloadRequest, background_tasks: BackgroundTasks):
    """
    Main endpoint to handle Video, Audio, or Info requests.
    """
    if not request.url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    if request.type not in ['video', 'audio', 'info']:
        raise HTTPException(status_code=400, detail="Type must be 'video', 'audio', or 'info'")

    temp_dir = get_temp_folder()

    try:
        result = process_download(request.url, request.type, temp_dir)

        # If it's just info, return JSON and cleanup immediately
        if request.type == 'info':
            background_tasks.add_task(clean_up, temp_dir)
            return JSONResponse(content=result)

        # If it's a file, send it and schedule cleanup after sending
        file_path = result["filepath"]
        file_name = result["filename"]
        
        # Determine media type for browser
        media_type = "video/mp4" if request.type == 'video' else "audio/mpeg"
        
        background_tasks.add_task(clean_up, temp_dir)
        
        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type=media_type
        )

    except Exception as e:
        clean_up(temp_dir)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Run locally for testing
    uvicorn.run(app, host="0.0.0.0", port=8000)
