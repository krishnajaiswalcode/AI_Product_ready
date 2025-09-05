import asyncio
import time
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Dict

from .core import CameraManager, analyze_code

# Simple in-memory per-user token bucket rate limiter
class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.timestamp = time.time()

    def consume(self, tokens: int = 1) -> bool:
        now = time.time()
        delta = now - self.timestamp
        self.tokens = min(self.capacity, self.tokens + delta * self.rate)
        self.timestamp = now
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


_buckets: Dict[str, TokenBucket] = {}

def get_bucket_for_user(user_id: str) -> TokenBucket:
    # 1 request per second, burst up to 5 by default
    if user_id not in _buckets:
        _buckets[user_id] = TokenBucket(rate=1.0, capacity=5)
    return _buckets[user_id]


class CodePayload(BaseModel):
    user_id: str
    code: str


app = FastAPI()
camera = CameraManager()


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Require user_id in header for per-user rate limiting
    user_id = request.headers.get("x-user-id")
    if not user_id:
        return JSONResponse({"detail": "x-user-id header required"}, status_code=400)
    bucket = get_bucket_for_user(user_id)
    if not bucket.consume(1):
        return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
    return await call_next(request)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(payload: CodePayload):
    res = analyze_code(payload.code)
    return res


@app.post("/camera/start")
async def camera_start(request: Request):
    await camera.start()
    return {"status": "started"}


@app.post("/camera/pause")
async def camera_pause():
    await camera.pause()
    return {"status": "paused"}


@app.post("/camera/resume")
async def camera_resume():
    await camera.resume()
    return {"status": "resumed"}


@app.post("/camera/stop")
async def camera_stop():
    await camera.stop()
    return {"status": "stopped"}


@app.get("/camera/frame")
async def camera_frame():
    frame = await camera.get_latest_frame()
    if not frame:
        raise HTTPException(404, "no frame available")
    return StreamingResponse(iter([frame]), media_type="image/jpeg")
