from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from routes.recommend import router
from routes.chat import router as chat_router

app = FastAPI(
    title="AI Recommendation Engine",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

IMAGE_DIR = os.path.abspath(
    os.path.join(BASE_DIR, "..", "server", "dataset", "images")
)

app.mount(
    "/images",
    StaticFiles(directory=IMAGE_DIR),
    name="images"
)

app.include_router(router)
app.include_router(chat_router)

@app.get("/")
def home():
    return {
        "success": True,
        "message": "AI Recommendation Engine Running 🚀"
    }