```python
import logging
from datetime import datetime
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.database import engine, Base
from app.api.endpoints import users, patients, services, visits, labrequests, medicalrecords, reports, auth, utils
from app.dependencies import get_db
from app.core.config import settings
from app.core.redis_config import get_redis_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("fastapi_app")

app = FastAPI(
    title="Medical Clinic Management System",
    description="API for managing medical clinic operations.",
    version="1.0.0",
)

# CORS Middleware
origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    logger.info(f"Incoming Request: {request.method} {request.url} from {request.client.host}")
    response = await call_next(request)
    process_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"Outgoing Response: {request.method} {request.url} - Status: {response.status_code} - Time: {process_time:.4f}s")
    return response

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(patients.router)
app.include_router(services.router)
app.include_router(visits.router)
app.include_router(labrequests.router)
app.include_router(medicalrecords.router)
app.include_router(reports.router)
app.include_router(utils.router)

@app.on_event("startup")
async def startup_event():
    logger.info("Application startup event: Initializing Redis client...")
    get_redis_client()
    logger.info("Application startup complete.")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables checked/created.")

@app.get("/")
async def root():
    logger.info("Root endpoint accessed.")
    return {"message": "Welcome to the Medical Clinic Management System API!"}

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail} for {request.method} {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.critical(f"Unhandled Exception: {exc} for {request.method} {request.url}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred."},
    )

if __name__ == "__main__":
    logger.info("Starting FastAPI application via Uvicorn (for PyInstaller/local run).")
    uvicorn.run(app, host="0.0.0.0", port=8000)
```