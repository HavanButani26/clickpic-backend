from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.verification import router as verification_router
from app.api.routes.password_reset import router as password_reset_router
from app.core.config import settings

app = FastAPI(title="ClickPic API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(verification_router)
app.include_router(password_reset_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
