# Live AI (camera + code analysis)

This small project provides:

- A FastAPI server (`live_ai_service.api`) with endpoints to control the camera (start/pause/resume/stop) and a code analyzer endpoint.
- A Streamlit UI (`streamlit_app.py`) to control the camera and submit code for analysis.

Quickstart (Windows):

1. Create a virtual environment and install requirements:

   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt

2. Start the API (in one terminal):

   uvicorn live_ai_service.api:app --host 0.0.0.0 --port 8000

3. Start Streamlit (in another terminal):

   streamlit run streamlit_app.py

Notes and limitations:

- Rate limiting is an in-memory token bucket keyed by the header `x-user-id`. For production, replace with Redis or another shared store.
- The camera manager uses OpenCV and runs in the same process as the API — for production you may want a dedicated camera process or external streaming solution.
- The AI code review portion in `core.analyze_code` will attempt to call `google.genai` only if `GEMINI_API_KEY` is set. It's optional and best-effort.
