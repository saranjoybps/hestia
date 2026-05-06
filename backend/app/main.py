from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routes import users, attendance, leaves, tasks, performance, announcements, reports, departments, letters, onboarding, shifts, audit_logs

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version
)

# Configure CORS with regex support
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"(http://localhost:\d+|https://.*\.vercel\.app|https://.*\.onrender\.com|https://hr\.joyrts\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")
app.include_router(leaves.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(performance.router, prefix="/api")
app.include_router(announcements.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(departments.router, prefix="/api")
app.include_router(letters.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(shifts.router, prefix="/api")
app.include_router(audit_logs.router, prefix="/api")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "JoyHR API",
        "version": settings.api_version,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
