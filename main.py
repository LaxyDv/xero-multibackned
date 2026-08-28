import os
import uuid
import shutil
import asyncio
import yt_dlp
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.responses import FileResponse
from rembg import remove

app = FastAPI(
    title="XeroTools Core Backend",
    description="Unified backend for Downloader, BG Remover, and Upscaler by Xeno (XQD)",
    version="2.0-Clean"
)

# Configuration
TEMP_DIR = "xero_temp"
os.makedirs(TEMP_DIR, exist_ok=True)

def cleanup(path):
    """Safely delete temporary folders after processing."""
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
        except Exception as e:
            print(f"Error cleaning up {path}: {e}")

def get_temp_path():
    """Create a unique temporary folder for each request."""
    uid = str(uuid.uuid4())
    path = os.path.join(TEMP_DIR, uid)
    os.makedirs(path)
    return path

# ==========================================
# TOOL 1: UNIVERSAL MEDIA DOWNLOADER
# ==========================================
@app.post("/download")
async def download_media(url: str = Form(...), type: str = Form("video")):
    """
    Downloads Video or Audio from supported platforms (YT, TikTok, Insta, X, etc.)
    type: 'video' (mp4, max 1280p) or 'audio' (mp3)
    """
    temp_path = get_temp_path()
    try:
        ydl_opts = {
            'outtmpl': f'{temp_path}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        if type == 'audio':
            # Extract MP3
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        elif type == 'video':
            # Download Video max 1280p (720p/1080p merged)
            ydl_opts['format'] = 'bestvideo[height<=1280]+bestaudio/best[height<=1280]'
            ydl_opts['merge_output_format'] = 'mp4'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            files = os.listdir(temp_path)
            
            if not files:
                raise Exception("No file generated. Link might be invalid.")
            
            filename = files[0]
            filepath = os.path.join(temp_path, filename)
            
            # Schedule auto-delete after 2 minutes (120 seconds)
            loop = asyncio.get_event_loop()
            loop.call_later(120, cleanup, temp_path)
            
            media_type = "audio/mpeg" if type == 'audio' else "video/mp4"
            return FileResponse(filepath, filename=filename, media_type=media_type)

    except Exception as e:
        cleanup(temp_path)
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

# ==========================================
# TOOL 2: BACKGROUND REMOVER
# ==========================================
@app.post("/remove-bg")
async def remove_background(file: UploadFile = File(...)):
    """
    Removes background from uploaded image using AI.
    Returns transparent PNG.
    """
    temp_path = get_temp_path()
    input_filename = f"input_{file.filename}"
    output_filename = f"nobg_{file.filename}.png"
    
    input_path = os.path.join(temp_path, input_filename)
    output_path = os.path.join(temp_path, output_filename)
    
    try:
        # Save uploaded file
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process with rembg
        with open(input_path, 'rb') as i:
            with open(output_path, 'wb') as o:
                input_data = i.read()
                output_data = remove(input_data)
                o.write(output_data)
        
        # Delete input immediately to save space
        os.remove(input_path)
        
        # Schedule folder cleanup
        loop = asyncio.get_event_loop()
        loop.call_later(120, cleanup, temp_path)
        
        return FileResponse(output_path, filename=output_filename, media_type="image/png")

    except Exception as e:
        cleanup(temp_path)
        raise HTTPException(status_code=500, detail=f"BG Removal failed: {str(e)}")

# ==========================================
# TOOL 3: IMAGE UPSCALER
# ==========================================
@app.post("/upscale")
async def upscale_image(file: UploadFile = File(...), target_width: int = Form(1280)):
    """
    Upscales image to target width (default 1280px) maintaining aspect ratio.
    Uses high-quality Lanczos resampling.
    """
    temp_path = get_temp_path()
    input_filename = f"input_{file.filename}"
    output_filename = f"upscaled_{file.filename}"
    
    input_path = os.path.join(temp_path, input_filename)
    output_path = os.path.join(temp_path, output_filename)
    
    try:
        # Save uploaded file
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Open and Calculate new dimensions
        img = Image.open(input_path)
        w_percent = (target_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        
        # Resize with High Quality (Lanczos)
        img = img.resize((target_width, h_size), Image.Resampling.LANCZOS)
        
        # Convert to RGB if necessary (for JPEG compatibility)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        img.save(output_path, quality=95, optimize=True)
        
        # Delete input
        os.remove(input_path)
        
        # Schedule folder cleanup
        loop = asyncio.get_event_loop()
        loop.call_later(120, cleanup, temp_path)
        
        return FileResponse(output_path, filename=output_filename, media_type="image/jpeg")

    except Exception as e:
        cleanup(temp_path)
        raise HTTPException(status_code=500, detail=f"Upscaling failed: {str(e)}")

# Root Endpoint
@app.get("/")
async def home():
    return {
        "message": "Welcome to XeroTools Core Backend by Xeno (XQD)",
        "tools_available": [
            "POST /download (Video/Audio from Social Media)",
            "POST /remove-bg (AI Background Removal)",
            "POST /upscale (Image Enhancer to 1280p+)"
        ],
        "status": "Ready for Deployment"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
