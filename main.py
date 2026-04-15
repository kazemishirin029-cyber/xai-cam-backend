from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os, re, zipfile
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

app = FastAPI(title="XAI CAM API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CAM_DIR        = Path(os.getenv("CAM_DIR", "./CAM"))
EXTRACTED_DIR  = Path(os.getenv("EXTRACTED_DIR", "./CAM_extracted"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_API_KEY)

def get_base_dir():
    if EXTRACTED_DIR.exists() and any(EXTRACTED_DIR.iterdir()):
        return EXTRACTED_DIR
    return CAM_DIR

def parse_folder(folder):
    label_file = folder / "predicted_label.txt"
    label = label_file.read_text().strip() if label_file.exists() else "Unknown"
    frames = []
    for f in sorted(folder.glob("temp_frame_*.jpg")):
        match = re.search(r"temp_frame_(\d+)\.jpg", f.name)
        if match:
            frames.append({"x": int(match.group(1)), "filename": f.name})
    frames.sort(key=lambda f: f["x"])
    videos = list(folder.glob("*.avi"))
    return {"id": folder.name, "label": label, "has_importance_plot": (folder / "frame_importance_plot.png").exists(), "frames": frames, "video": videos[0].name if videos else None}

@app.get("/videos")
def list_videos():
    base = get_base_dir()
    folders = sorted([f for f in base.iterdir() if f.is_dir() and f.name.isdigit()], key=lambda x: int(x.name))
    return [{"id": f.name} for f in folders]

@app.get("/videos/{video_id}")
def get_video(video_id: str):
    folder = get_base_dir() / video_id
    if not folder.exists():
        raise HTTPException(404, detail="Not found")
    return parse_folder(folder)

@app.get("/videos/{video_id}/analyze")
def analyze_video(video_id: str):
    folder = get_base_dir() / video_id
    if not folder.exists():
        raise HTTPException(404, detail="Not found")
    data = parse_folder(folder)
    if not data["frames"]:
        raise HTTPException(400, detail="No frames found")
    contents = [f'The model predicted this action: "{data["label"]}". Describe what you see in the frames, confirm if the label matches, and rate confidence High/Medium/Low.']
    for frame in data["frames"]:
        img_bytes = (folder / frame["filename"]).read_bytes()
        contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
    response = client.models.generate_content(model="gemini-2.5-flash", contents=contents)
    return {"video_id": video_id, "predicted_label": data["label"], "frames_analyzed": [f["x"] for f in data["frames"]], "gemini_analysis": response.text}

_static_dir = EXTRACTED_DIR if EXTRACTED_DIR.exists() else CAM_DIR
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
