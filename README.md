# XAI CAM Backend
This project is a small FastAPI application that serves a single-page evidence review UI for action-recognition outputs stored in the `CAM` directory.
The app lets you:
- Browse processed study folders
- View the predicted label for each study
- Play the source `.avi` clip
- Inspect the three salient evidence frames
- View the `frame_importance_plot.png`
- Ask Gemini for an evidence-grounded explanation of the prediction
## Project Structure
- `main.py`: FastAPI app and API routes
- `frontend/index.html`: single-page UI served by FastAPI
- `requirements.txt`: Python dependencies
- `tests/test_app.py`: lightweight regression tests
- `../CAM`: study folders containing videos, frames, labels, and plots
## Requirements
- Python 3.13 recommended
- A valid Gemini API key for AI explanations
## Environment Variables
Create a `.env` file in `xai-cam-backend/` with:
```env
# Windows:
CAM_DIR=..\CAM
# Mac/Linux:
CAM_DIR=../CAM
GEMINI_API_KEY=your_key_here
```
Notes:
- `CAM_DIR` can be absolute or relative.
- If `CAM_DIR` is omitted, the app will try `xai-cam-backend/CAM` and then the repo-level `CAM` folder automatically.
## Run Locally
From `xai-cam-backend/`:

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

**Windows:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```
Open:
```text
http://localhost:8000
```
## Main Routes
- `GET /`: serves the frontend
- `GET /status`: app status, Gemini configuration state, and cache info
- `GET /videos`: list studies and metadata
- `GET /videos/{video_id}`: load one study
- `GET /videos/{video_id}/analyze`: run the default Gemini explanation
- `POST /videos/{video_id}/ask`: ask a custom grounded question
## Caching
Gemini responses are cached in memory for 15 minutes.
- Cache key: study id + prompt type + question text
- Scope: current Python process only
- Storage: in-memory only
This improves repeated requests without changing the underlying app architecture.
## Running Tests
From `xai-cam-backend/`:

**Mac/Linux:**
```bash
venv/bin/python -m unittest tests.test_app
```

**Windows:**
```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_app
```
The tests cover:
- Status endpoint shape
- Study list metadata
- Study detail loading
- Invalid video handling
- Custom-question validation
- Frontend delivery
## Known Constraints
- If Gemini requests fail with a socket or permission error, the API key may still be correct. This usually means the local environment, firewall, or sandbox is blocking outbound network access.
- The Gemini cache is not persisted across restarts.
- The frontend is intentionally a single static page; improvements so far have preserved that architecture.
