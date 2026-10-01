import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Controllers
from controllers.auth import router as AuthRouter

app = FastAPI(title="QLess API")

# Allow the React dev server(s) listed in CORS_ORIGINS to call the API
origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

app.include_router(AuthRouter, prefix=API_PREFIX)


@app.get("/health")
def health_check():
    return {"message": "Api is running"}