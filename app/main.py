from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from .routers import repo

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
origins = [
    "http://localhost:3000",  # Assuming React frontend runs on port 3000
    "localhost:3000", # Also common
    "http://127.0.0.1:3000",
    "127.0.0.1:3000"
]

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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 