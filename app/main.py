from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from dotenv import load_dotenv

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

# CORS middleware configuration - MUST come before router inclusion
origins = ["https://codedocgen-frontend.vercel.app"]

# Add localhost origins for development
dev_origins = [
    "http://localhost:3000",
    "localhost:3000",
    "http://127.0.0.1:3000",
    "127.0.0.1:3000",
]
origins.extend(dev_origins)

# Add any additional origins from environment variable
if os.getenv("ALLOW_ORIGINS"):
    additional_origins = os.getenv("ALLOW_ORIGINS").split(",")
    origins.extend(additional_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Ensures OPTIONS requests are handled
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to CodeDocGen API"}

@app.get("/.health")
async def health_check():
    return {"status": "healthy"}

# Include routers - AFTER middleware setup
from .routers import repo
app.include_router(repo.router)

# Placeholder for future routers
# from .routers import repo_analyzer, confluence_publisher
# app.include_router(repo_analyzer.router)
# app.include_router(confluence_publisher.router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True) 