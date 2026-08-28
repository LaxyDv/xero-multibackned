import os
import uuid
import shutil
import asyncio
import yt_dlp
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse
from rembg import remove

app = FastAPI(
    title="XeroTools Core Backend",
    description="Unified backend for Downloader, BG Remover, and Upscaler by Xeno (XQD)",
    version="2.1-Domcloud"
)

TEMP_DIR = "xero_temp"
os.makedirs(TEMP_DIR, exist_ok=True)

def cleanup(path):
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
        except Exception:
            pass

def get_temp_path():
    uid = str(uuid.uuid4())
    path = os.path.join(TEMP_DIR, uid)
    os.makedirs(path)
    return path

# ==========================================
# TOOL 1: UNIVERSAL MEDIA DOWNLOADER
# ==========================================
@app.post("/download")
async def download_media(url: str = Form(...), type: str = Form("video")):
    temp_path = get_temp_path()
    try:
        ydl_opts = {
            'outtmpl': f'{temp_path}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        if type == 'audio':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        elif type == 'video':
            ydl_opts['format'] = 'bestvideo[height<=1280]+bestaudio/best[height<=1280]'
            ydl_opts['merge_output_format'] = 'mp4'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
            files = os.listdir(temp_path)
            if not files:
                raise Exception("No file generated.")
            
            filename = files[0]
            filepath = os.path.join(temp_path, filename)
            
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
    temp_path = get_temp_path()
    input_path = os.path.join(temp_path, f"input_{file.filename}")
    output_path = os.path.join(temp_path, f"nobg_{file.filename}.png")
    
    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        with open(input_path, 'rb') as i:
            with open(output_path, 'wb') as o:
                o.write(remove(i.read()))
        
        os.remove(input_path)
        loop = asyncio.get_event_loop()
        loop.call_later(120, cleanup, temp_path)
        
        return FileResponse(output_path, filename=f"nobg_{file.filename}.png", media_type="image/png")

    except Exception as e:
        cleanup(temp_path)
        raise HTTPException(status_code=500, detail=f"BG Removal failed: {str(e)}")

# ==========================================
# TOOL 3: IMAGE UPSCALER
# ==========================================
@app.post("/upscale")
async def upscale_image(file: UploadFile = File(...), target_width: int = Form(1280)):
    temp_path = get_temp_path()
    input_path = os.path.join(temp_path, f"input_{file.filename}")
    output_path = os.path.join(temp_path, f"upscaled_{file.filename}")
    
    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        img = Image.open(input_path)
        w_percent = (target_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        
        img = img.resize((target_width, h_size), Image.Resampling.LANCZOS)
        
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        img.save(output_path, quality=95, optimize=True)
        os.remove(input_path)
        
        loop = asyncio.get_event_loop()
        loop.call_later(120, cleanup, temp_path)
        
        return FileResponse(output_path, filename=f"upscaled_{file.filename}", media_type="image/jpeg")

    except Exception as e:
        cleanup(temp_path)
        raise HTTPException(status_code=500, detail=f"Upscaling failed: {str(e)}")

@app.get("/")
async def home():
    return {
        "message": "Welcome to XeroTools Core Backend by Xeno (XQD)",
        "tools": ["/download", "/remove-bg", "/upscale"],
        "status": "Running on Domcloud"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
