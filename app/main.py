from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from dotenv import load_dotenv

from .routers import repo

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(
    title="CodeDocGen API",
    description="API for CodeDocGen - Interactive Spring Boot Documentation & Testing Companion",
    version="0.1.0"
)

# CORS middleware configuration
default_origins = [
    "http://localhost:3000",  # Assuming React frontend runs on port 3000
    "localhost:3000", # Also common
    "http://127.0.0.1:3000",
    "127.0.0.1:3000"
]

# Add any additional origins from environment variable
if os.getenv("ALLOW_ORIGINS"):
    additional_origins = os.getenv("ALLOW_ORIGINS").split(",")
    origins = default_origins + additional_origins
else:
    origins = default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to CodeDocGen API"}

@app.get("/.health")
async def health_check():
    return {"status": "healthy"}

# Include routers
app.include_router(repo.router)

# Placeholder for future routers
# from .routers import repo_analyzer, confluence_publisher
# app.include_router(repo_analyzer.router)
# app.include_router(confluence_publisher.router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True) 