from fastapi import FastAPI
from routes.recommend import router

app = FastAPI(
    title="AI Recommendation Engine",
    version="1.0.0"
)

app.include_router(router)

@app.get("/")
def home():
    return {
        "success": True,
        "message": "AI Recommendation Engine Running 🚀"
    }