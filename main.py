from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os, re
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

app = FastAPI(title="XAI CAM API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CAM_DIR        = Path(os.getenv("CAM_DIR", "./CAM"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
client         = genai.Client(api_key=GEMINI_API_KEY)


def parse_folder(folder: Path) -> dict:
    label_file = folder / "predicted_label.txt"
    label = label_file.read_text().strip() if label_file.exists() else "Unknown"
    frames = []
    for f in sorted(folder.glob("temp_frame_*.jpg")):
        match = re.search(r"temp_frame_(\d+)\.jpg", f.name)
        if match:
            frames.append({"x": int(match.group(1)), "filename": f.name})
    frames.sort(key=lambda f: f["x"])
    videos = list(folder.glob("*.avi"))
    return {
        "id": folder.name,
        "label": label,
        "has_importance_plot": (folder / "frame_importance_plot.png").exists(),
        "frames": frames,
        "video": videos[0].name if videos else None,
    }


@app.get("/videos")
def list_videos():
    if not CAM_DIR.exists():
        raise HTTPException(500, detail=f"CAM_DIR not found: {CAM_DIR}")
    folders = sorted(
        [f for f in CAM_DIR.iterdir() if f.is_dir() and f.name.isdigit()],
        key=lambda x: int(x.name)
    )
    return [{"id": f.name} for f in folders]


@app.get("/videos/{video_id}")
def get_video(video_id: str):
    folder = CAM_DIR / video_id
    if not folder.exists():
        raise HTTPException(404, detail=f"Video '{video_id}' not found")
    return parse_folder(folder)


@app.get("/videos/{video_id}/analyze")
def analyze_video(video_id: str):
    folder = CAM_DIR / video_id
    if not folder.exists():
        raise HTTPException(404, detail=f"Video '{video_id}' not found. CAM_DIR={CAM_DIR}")
    if not GEMINI_API_KEY:
        raise HTTPException(500, detail="GEMINI_API_KEY not set")
    data = parse_folder(folder)
    if not data["frames"]:
        raise HTTPException(400, detail="No frames found")

    frame_info = ", ".join([f"frame {f['x']}" for f in data["frames"]])
    contents = [
        f'The model predicted this action: "{data["label"]}" for a video. '
        f'I am sending you {len(data["frames"])} key frames extracted from the video '
        f'({frame_info}). '
        f'For each frame, reference its frame number in your explanation. '
        f'Describe what you see, confirm whether the label matches, explain the '
        f'reasoning behind the prediction referencing specific frames, '
        f'and rate confidence High/Medium/Low.'
    ]
    for frame in data["frames"]:
        img_bytes = (folder / frame["filename"]).read_bytes()
        contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))

    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=contents
    )
    return {
        "video_id": video_id,
        "predicted_label": data["label"],
        "frames_analyzed": [f["x"] for f in data["frames"]],
        "gemini_analysis": response.text,
    }


if CAM_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(CAM_DIR)), name="static")

from fastapi.responses import FileResponse

@app.get("/")
def serve_frontend():
    return FileResponse("frontend/index.html")

if CAM_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(CAM_DIR)), name="static")