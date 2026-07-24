from fastapi import FastAPI
from routes.recommend import router
from routes.chat import router as chat_router

app = FastAPI(
    title="AI Recommendation Engine",
    version="1.0.0"
)

app.include_router(router)
app.include_router(chat_router)

@app.get("/")
def home():
    return {
        "success": True,
        "message": "AI Recommendation Engine Running 🚀"
    }