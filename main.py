import os
import shutil
import uuid
import time
import threading
import yt_dlp
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI(
    title="XeroTools Secure Backend",
    description="Auto-cleaning Multi-tool by Xeno (XQD)",
    version="2.1-Secure"
)

# Configuration
TEMP_ROOT = "temp_downloads"
MAX_FILE_AGE_SECONDS = 120  # 2 Minutes
os.makedirs(TEMP_ROOT, exist_ok=True)

# --- Data Models ---
class DownloadRequest(BaseModel):
    url: str
    type: str  # 'video', 'audio', 'info'

# --- Security & Cleanup Logic ---

def clean_old_files():
    """Background thread that runs every 60 seconds to delete files older than 2 mins."""
    while True:
        try:
            current_time = time.time()
            if not os.path.exists(TEMP_ROOT):
                continue
            
            for folder_name in os.listdir(TEMP_ROOT):
                folder_path = os.path.join(TEMP_ROOT, folder_name)
                if os.path.isdir(folder_path):
                    # Check creation time of the folder
                    created_time = os.path.getctime(folder_path)
                    age = current_time - created_time
                    
                    if age > MAX_FILE_AGE_SECONDS:
                        print(f"[Security] Deleting old folder: {folder_name} (Age: {age:.0f}s)")
                        shutil.rmtree(folder_path, ignore_errors=True)
        except Exception as e:
            print(f"Cleanup error: {e}")
        
        # Sleep for 60 seconds before checking again
        time.sleep(60)

# Start the cleanup thread when the app launches
cleanup_thread = threading.Thread(target=clean_old_files, daemon=True)
cleanup_thread.start()

def get_temp_folder():
    """Creates a unique temporary folder."""
    folder_id = str(uuid.uuid4())
    path = os.path.join(TEMP_ROOT, folder_id)
    os.makedirs(path, exist_ok=True)
    return path

def immediate_cleanup(folder_path: str):
    """Deletes a specific folder immediately after use."""
    if os.path.exists(folder_path):
        try:
            shutil.rmtree(folder_path)
            print(f"[Cleanup] Removed folder: {os.path.basename(folder_path)}")
        except Exception as e:
            print(f"Error removing {folder_path}: {e}")

# --- Download Logic ---

def process_download(url: str, download_type: str, output_dir: str):
    ydl_opts = {
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }

    if download_type == 'video':
        ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        ydl_opts['merge_output_format'] = 'mp4'
    elif download_type == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        ydl_opts['outtmpl'] = f'{output_dir}/%(title)s.mp3'
    elif download_type == 'info':
        ydl_opts['skip_download'] = True
        ydl_opts['dump_single_json'] = True

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=(download_type != 'info'))
            
            if download_type == 'info':
                return {"status": "success", "data": info}

            files = os.listdir(output_dir)
            if not files:
                raise Exception("No file generated.")
            
            filename = files[0]
            filepath = os.path.join(output_dir, filename)
            return {"filepath": filepath, "filename": filename}

    except Exception as e:
        raise Exception(f"Processing failed: {str(e)}")

# --- API Endpoints ---

@app.get("/")
async def home():
    return {
        "message": "XeroTools Secure Node Active",
        "security_policy": "Files auto-deleted after 2 minutes",
        "supported": ["YouTube", "TikTok", "Instagram", "X", "Facebook", "Reddit"]
    }

@app.post("/download")
async def download_tool(request: DownloadRequest, background_tasks: BackgroundTasks):
    if not request.url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    temp_dir = get_temp_folder()

    try:
        result = process_download(request.url, request.type, temp_dir)

        if request.type == 'info':
            # For info, delete immediately after sending JSON
            background_tasks.add_task(immediate_cleanup, temp_dir)
            return JSONResponse(content=result)

        file_path = result["filepath"]
        file_name = result["filename"]
        media_type = "video/mp4" if request.type == 'video' else "audio/mpeg"
        
        # CRITICAL: Schedule deletion IMMEDIATELY after the file response starts
        # The background thread ensures it's gone even if the download fails halfway
        background_tasks.add_task(immediate_cleanup, temp_dir)
        
        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type=media_type,
            headers={"X-Auto-Delete": "true"} # Custom header to show security
        )

    except Exception as e:
        immediate_cleanup(temp_dir)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
