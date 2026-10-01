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
from controllers.businesses import router as BusinessRouter
from controllers.branches import router as BranchRouter
from controllers.queues import router as QueueRouter
from controllers.queue_entries import router as QueueEntryRouter
from controllers.realtime import router as RealtimeRouter
from controllers.notifications import router as NotificationRouter
from controllers.admin_suspicious_activity import router as SuspiciousActivityRouter
from controllers.admin_monitoring import router as AdminMonitoringRouter
from controllers.bookings import router as BookingRouter
from controllers.reviews import router as ReviewRouter
from controllers.favorites import router as FavoriteRouter

app = FastAPI(
    title="QLess API",
    description=(
        "**Real-time (WebSocket, not shown below):** "
        "`ws://127.0.0.1:8000/api/ws/queues/{queue_id}?token=<JWT>` "
        "sends live updates when someone joins, leaves, is called, or the queue status changes."
    ),
)

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
app.include_router(BusinessRouter, prefix=API_PREFIX)
app.include_router(BranchRouter, prefix=API_PREFIX)
app.include_router(QueueRouter, prefix=API_PREFIX)
app.include_router(QueueEntryRouter, prefix=API_PREFIX)
app.include_router(RealtimeRouter, prefix=API_PREFIX)
app.include_router(NotificationRouter, prefix=API_PREFIX)
app.include_router(SuspiciousActivityRouter, prefix=API_PREFIX)
app.include_router(AdminMonitoringRouter, prefix=API_PREFIX)
app.include_router(BookingRouter, prefix=API_PREFIX)
app.include_router(ReviewRouter, prefix=API_PREFIX)
app.include_router(FavoriteRouter, prefix=API_PREFIX)


@app.get("/health", tags=["Health"])
def health_check():
    return {"message": "Api is running"}