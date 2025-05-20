# CodeDocGen Backend

A FastAPI-based backend for the CodeDocGen project, designed to analyze code repositories and generate comprehensive documentation.

## Features

- Repository analysis
- API schema generation
- Flow diagram generation
- Entity relationship extraction
- Documentation export to multiple formats

## Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the development server:
   ```
   uvicorn app.main:app --reload
   ```

## API Documentation

Once running, API documentation is available at:
- Swagger UI: `/docs`
- ReDoc: `/redoc`

## Deployment

This backend is designed to be deployed to Render.com.

## Environment Variables

- `PORT`: Port to run the server on (default: 8000)
- Add other environment variables as needed 