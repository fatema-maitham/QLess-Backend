import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Controllers
from controllers.auth import router as AuthRouter
from controllers.users import router as UsersRouter
from controllers.categories import router as CategoryRouter
from controllers.browse import router as BrowseRouter
from controllers.queues import router as QueueRouter
from controllers.queue_entries import router as QueueEntryRouter
from controllers.businesses import router as BusinessRouter

app = FastAPI(title="QLess API")

# Allow the React dev server(s) listed in CORS_ORIGINS to call the API
origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api"

app.include_router(AuthRouter, prefix=API_PREFIX)
app.include_router(UsersRouter, prefix=API_PREFIX)
app.include_router(CategoryRouter, prefix=API_PREFIX)
app.include_router(BrowseRouter, prefix=API_PREFIX)
app.include_router(QueueRouter, prefix=API_PREFIX)
app.include_router(QueueEntryRouter, prefix=API_PREFIX)
app.include_router(BusinessRouter, prefix=API_PREFIX)


@app.get("/health", tags=["Health"])
def health_check():
    return {"message": "Api is running"}