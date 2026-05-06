from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os, re
import time
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_FILE = BASE_DIR / "frontend" / "index.html"
CONVERTED_DIR = BASE_DIR / "converted"

load_dotenv(BASE_DIR / ".env")
CONVERTED_DIR.mkdir(exist_ok=True)

app = FastAPI(title="XAI CAM API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def resolve_cam_dir() -> Path:
    raw_cam_dir = os.getenv("CAM_DIR", "").strip()
    candidates = []

    if raw_cam_dir:
        path = Path(raw_cam_dir)
        candidates.append(path if path.is_absolute() else (BASE_DIR / path).resolve())
    else:
        candidates.extend([
            (BASE_DIR / "CAM").resolve(),
            (BASE_DIR.parent / "CAM").resolve(),
        ])

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def get_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(500, detail="GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)


def is_gemini_configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


CAM_DIR = resolve_cam_dir()
CACHE_TTL_SECONDS = 900
GEMINI_MAX_RETRIES = 3
GEMINI_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
GEMINI_RETRY_BASE_DELAY_SECONDS = 1.0
gemini_cache: dict[tuple[str, str], dict] = {}


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


def clean_question(raw_question: str) -> str:
    sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", " ", raw_question).strip()
    sanitized = re.sub(r"\s+", " ", sanitized)
    if not sanitized:
        raise HTTPException(400, detail="Question cannot be empty")
    return sanitized


def parse_folder(folder: Path) -> dict:
    label_file = folder / "predicted_label.txt"
    label = label_file.read_text().strip() if label_file.exists() else "Unknown"
    frames = []
    for f in sorted(folder.glob("temp_frame_*.jpg")):
        match = re.search(r"temp_frame_(\d+)\.jpg", f.name)
        if match:
            frames.append({"x": int(match.group(1)), "filename": f.name})
    frames.sort(key=lambda f: f["x"])
    avi_videos = sorted(folder.glob("*.avi"))
    mp4_videos = sorted(folder.glob("*.mp4"))
    source_video = avi_videos[0].name if avi_videos else None
    converted_video = None

    if source_video:
        converted_candidate = CONVERTED_DIR / folder.name / Path(source_video).with_suffix(".mp4").name
        if converted_candidate.exists():
            converted_video = converted_candidate

    if mp4_videos:
        playback_video = mp4_videos[0].name
        playback_video_type = "mp4"
        playback_url = f"/static/{folder.name}/{playback_video}"
    elif converted_video:
        playback_video = converted_video.name
        playback_video_type = "mp4"
        playback_url = f"/converted/{folder.name}/{playback_video}"
    else:
        playback_video = source_video
        playback_video_type = "avi" if source_video else None
        playback_url = f"/static/{folder.name}/{source_video}" if source_video else None

    return {
        "id": folder.name,
        "study_name": f"Sample_{folder.name.zfill(3)}",
        "label": label,
        "has_importance_plot": (folder / "frame_importance_plot.png").exists(),
        "frame_count": len(frames),
        "frames": frames,
        "label_file": label_file.name if label_file.exists() else None,
        "video": source_video,
        "playback_video": playback_video,
        "playback_video_type": playback_video_type,
        "playback_url": playback_url,
    }


def get_cache_key(video_id: str, prompt_kind: str, question: str = "") -> tuple[str, str]:
    return (video_id, f"{prompt_kind}:{question}")


def get_cached_response(cache_key: tuple[str, str]) -> str | None:
    cached = gemini_cache.get(cache_key)
    if not cached:
        return None

    if time.time() - cached["created_at"] > CACHE_TTL_SECONDS:
        gemini_cache.pop(cache_key, None)
        return None

    return cached["text"]


def store_cached_response(cache_key: tuple[str, str], text: str) -> None:
    gemini_cache[cache_key] = {
        "text": text,
        "created_at": time.time(),
    }


def prune_expired_cache() -> None:
    now = time.time()
    expired_keys = [
        key for key, value in gemini_cache.items()
        if now - value["created_at"] > CACHE_TTL_SECONDS
    ]
    for key in expired_keys:
        gemini_cache.pop(key, None)


def get_video_folder(video_id: str) -> Path:
    folder = CAM_DIR / video_id
    if not folder.exists():
        raise HTTPException(404, detail=f"Video '{video_id}' not found. CAM_DIR={CAM_DIR}")
    return folder


def build_gemini_contents(data: dict, folder: Path, user_question: str | None = None) -> list:
    frame_info = ", ".join([f"frame {f['x']}" for f in data["frames"]])
    prompt_parts = [
        f'The model predicted this action: "{data["label"]}" for study {data["study_name"]}.',
        f'I am sending you {len(data["frames"])} key frames extracted from the video ({frame_info}).',
        "Reference specific frame numbers in your explanation.",
        "Ground your answer only in the predicted label and the supplied evidence frames.",
        "Avoid claims that cannot be supported by the visible evidence.",
    ]

    if user_question:
        prompt_parts.append(f'User question: "{user_question}"')
        prompt_parts.append(
            "Answer the user directly, using concise evidence-based reasoning and a confidence rating of High, Medium, or Low."
        )
    else:
        prompt_parts.append(
            "Describe what you see, assess whether the label matches the evidence, explain the reasoning behind the prediction, and rate confidence High, Medium, or Low."
        )

    contents = [" ".join(prompt_parts)]
    for frame in data["frames"]:
        img_bytes = (folder / frame["filename"]).read_bytes()
        contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
    return contents


def run_gemini(contents: list, cache_key: tuple[str, str] | None = None) -> tuple[str, bool]:
    if cache_key:
        cached_text = get_cached_response(cache_key)
        if cached_text is not None:
            return cached_text, True

    client = get_gemini_client()
    last_error = None

    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=contents
            )
            break
        except HTTPException:
            raise
        except errors.APIError as exc:
            last_error = exc
            if exc.code in GEMINI_RETRYABLE_STATUS_CODES and attempt < GEMINI_MAX_RETRIES:
                time.sleep(GEMINI_RETRY_BASE_DELAY_SECONDS * attempt)
                continue

            status_code = 503 if exc.code in GEMINI_RETRYABLE_STATUS_CODES else 502
            raise HTTPException(status_code, detail=f"Gemini analysis failed: {exc}") from exc
        except Exception as exc:
            last_error = exc
            raise HTTPException(502, detail=f"Gemini analysis failed: {exc}") from exc
    else:
        raise HTTPException(503, detail=f"Gemini analysis failed: {last_error}")

    response_text = response.text or ""
    if cache_key and response_text:
        store_cached_response(cache_key, response_text)
    return response_text, False


@app.get("/videos")
def list_videos():
    if not CAM_DIR.exists():
        raise HTTPException(500, detail=f"CAM_DIR not found: {CAM_DIR}")
    folders = sorted(
        [f for f in CAM_DIR.iterdir() if f.is_dir() and f.name.isdigit()],
        key=lambda x: int(x.name)
    )
    return [parse_folder(f) for f in folders]


@app.get("/status")
def app_status():
    prune_expired_cache()
    folders = []
    if CAM_DIR.exists():
        folders = [f for f in CAM_DIR.iterdir() if f.is_dir() and f.name.isdigit()]
    return {
        "cam_dir": str(CAM_DIR),
        "cam_dir_exists": CAM_DIR.exists(),
        "video_count": len(folders),
        "gemini_configured": is_gemini_configured(),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "cached_response_count": len(gemini_cache),
    }


@app.get("/videos/{video_id}")
def get_video(video_id: str):
    folder = get_video_folder(video_id)
    return parse_folder(folder)


@app.get("/videos/{video_id}/analyze")
def analyze_video(video_id: str):
    folder = get_video_folder(video_id)
    data = parse_folder(folder)
    if not data["frames"]:
        raise HTTPException(400, detail="No frames found")

    contents = build_gemini_contents(data, folder)
    response_text, cached = run_gemini(
        contents,
        cache_key=get_cache_key(video_id, "analyze"),
    )
    return {
        "video_id": video_id,
        "study_name": data["study_name"],
        "predicted_label": data["label"],
        "frames_analyzed": [f["x"] for f in data["frames"]],
        "gemini_analysis": response_text,
        "cached": cached,
    }


@app.post("/videos/{video_id}/ask")
def ask_video_question(video_id: str, payload: QuestionRequest):
    folder = get_video_folder(video_id)
    data = parse_folder(folder)
    if not data["frames"]:
        raise HTTPException(400, detail="No frames found")

    question = clean_question(payload.question)
    contents = build_gemini_contents(data, folder, user_question=question)
    response_text, cached = run_gemini(
        contents,
        cache_key=get_cache_key(video_id, "ask", question),
    )
    return {
        "video_id": video_id,
        "study_name": data["study_name"],
        "predicted_label": data["label"],
        "question": question,
        "frames_analyzed": [f["x"] for f in data["frames"]],
        "answer": response_text,
        "cached": cached,
    }


if CAM_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(CAM_DIR)), name="static")
if CONVERTED_DIR.exists():
    app.mount("/converted", StaticFiles(directory=str(CONVERTED_DIR)), name="converted")

@app.get("/")
def serve_frontend():
    return FileResponse(FRONTEND_FILE)
