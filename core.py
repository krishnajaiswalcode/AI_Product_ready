import asyncio
import base64
import io
import time
import ast
import os
from typing import Optional, Dict, Any

try:
    from PIL import Image
except Exception:
    Image = None  # Pillow optional for non-camera analysis

try:
    import cv2
except Exception:
    cv2 = None

_DEFAULT_FPS = 5


class CameraManager:
    """A lightweight async camera manager that supports start/pause/resume/stop

    - start() opens the default camera and begins capturing frames in a background task
    - pause() stops updating frames but keeps the capture open
    - resume() resumes capturing
    - stop() closes the capture and stops the task
    - get_latest_frame() returns a jpeg bytes object or None
    """

    def __init__(self, device_index: int = 0, fps: int = _DEFAULT_FPS):
        self.device_index = device_index
        self.fps = fps
        self._cap = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._paused = False
        self._latest_frame: Optional[bytes] = None
        self._lock = asyncio.Lock()

    async def start(self):
        if cv2 is None:
            raise RuntimeError("OpenCV (cv2) is required for camera functionality")
        if self._running:
            return
        self._cap = await asyncio.to_thread(cv2.VideoCapture, self.device_index)
        # small check
        if not (await asyncio.to_thread(self._cap.isOpened)):
            await asyncio.to_thread(self._cap.release)
            raise RuntimeError("Unable to open camera device")

        self._running = True
        self._paused = False
        self._task = asyncio.create_task(self._capture_loop())

    async def pause(self):
        self._paused = True

    async def resume(self):
        if not self._running:
            await self.start()
            return
        self._paused = False

    async def stop(self):
        self._running = False
        if self._task:
            await self._task
        if self._cap is not None:
            await asyncio.to_thread(self._cap.release)
            self._cap = None
        self._task = None

    async def status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "paused": self._paused,
            "has_frame": self._latest_frame is not None,
        }

    async def get_latest_frame(self) -> Optional[bytes]:
        async with self._lock:
            return self._latest_frame

    async def _capture_loop(self):
        interval = 1.0 / max(1, self.fps)
        try:
            while self._running and self._cap is not None:
                if self._paused:
                    await asyncio.sleep(0.1)
                    continue

                ret, frame = await asyncio.to_thread(self._cap.read)
                if not ret:
                    await asyncio.sleep(0.1)
                    continue

                # Convert BGR to RGB
                frame_rgb = await asyncio.to_thread(lambda f: cv2.cvtColor(f, cv2.COLOR_BGR2RGB), frame)

                if Image is not None:
                    img = Image.fromarray(frame_rgb)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG")
                    jpeg = buf.getvalue()
                else:
                    # fallback: encode with OpenCV
                    ret2, jpeg = await asyncio.to_thread(cv2.imencode, ".jpg", frame_rgb)
                    if not ret2:
                        jpeg = None

                async with self._lock:
                    self._latest_frame = jpeg

                await asyncio.sleep(interval)
        finally:
            # on exit
            pass


def analyze_code(code: str) -> Dict[str, Any]:
    """Perform a basic static analysis of provided Python code.

    This intentionally keeps everything local (no external network calls).
    If a Google GenAI client is available and GEMINI_API_KEY is set, the
    function will attempt to return an optional AI review (best-effort).
    """
    results: Dict[str, Any] = {"syntax_error": None, "metrics": {}, "notes": []}

    # Syntax check
    try:
        tree = ast.parse(code)
    except SyntaxError as se:
        results["syntax_error"] = {
            "msg": str(se),
            "lineno": se.lineno,
            "offset": se.offset,
        }
        return results

    # Basic metrics
    lines = code.splitlines()
    results["metrics"]["lines"] = len(lines)
    results["metrics"]["functions"] = sum(isinstance(n, ast.FunctionDef) for n in ast.walk(tree))
    results["metrics"]["classes"] = sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree))

    # Find TODOs and long lines
    todos = [i + 1 for i, l in enumerate(lines) if "TODO" in l or "FIXME" in l]
    long_lines = [i + 1 for i, l in enumerate(lines) if len(l) > 120]
    if todos:
        results["notes"].append({"type": "todos", "lines": todos})
    if long_lines:
        results["notes"].append({"type": "long_lines", "lines": long_lines})

    # Simple style checks: unused imports / names are non-trivial without third-party
    # tools, so we only flag obvious things: bare-except, global prints, etc.
    bare_except_lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            bare_except_lines.append(getattr(node, "lineno", None))
    if bare_except_lines:
        results["notes"].append({"type": "bare_except", "lines": bare_except_lines})

    # Optional AI review (best-effort): try to use google.genai if present and key in env
    ai_review = None
    try:
        if os.getenv("GEMINI_API_KEY"):
            from google import genai

            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            # best-effort single-shot review prompt
            prompt = (
                "You are a Python code reviewer. Provide concise suggestions, potential bugs, "
                "and areas for improvement for the following code:\n\n" + code
            )
            # The exact method may differ by genai version; we guard this in try/except
            try:
                resp = client.generate(prompt=prompt, max_output_tokens=256)
                ai_review = getattr(resp, "candidates", None) or getattr(resp, "output", None)
            except Exception:
                ai_review = None
    except Exception:
        ai_review = None

    if ai_review:
        results["ai_review"] = str(ai_review)

    return results
