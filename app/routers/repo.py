from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Response, Query
from pydantic import BaseModel
from ..models.repo_models import RepoCredentials, RepoResponse, ProjectTypeResponse, EndpointResponse, FlowResponse
from ..services.repo_service import RepoService
from ..services.project_analyzer import ProjectAnalyzer
from ..services.endpoint_parser import EndpointParser
from ..services.swagger_generator import SwaggerGenerator
from ..services.markdown_exporter import MarkdownExporter
from ..services.feature_builder import FeatureBuilder
from ..services.entity_parser import EntityParser
from ..services.diagram_generator import PlantUMLGenerator
from ..services.diagram_renderer import DiagramRenderer
from ..services.confluence_publisher import ConfluencePublisher
from ..services.flow_analyzer import FlowAnalyzer
from ..services.role_filter import RoleFilter
from ..services.schema_mapper import SchemaMapper
from ..services.publish_payload_builder import PublishPayloadBuilder
from ..services.markdown_to_confluence_html import MarkdownToConfluenceConverter
import logging
import git
import os
import tempfile
import json
# Import plantuml only when needed, not at the module level
# import plantuml
from pathlib import Path
from typing import Dict, Any, List, Optional

router = APIRouter(
    prefix="/api/repo",
    tags=["Repository"],
)

logger = logging.getLogger(__name__)
repo_service = RepoService()
project_analyzer = ProjectAnalyzer()
endpoint_parser = EndpointParser()
swagger_generator = SwaggerGenerator()
markdown_exporter = MarkdownExporter()
feature_builder = FeatureBuilder()
flow_analyzer = FlowAnalyzer()
role_filter = RoleFilter()
schema_mapper = SchemaMapper()
# Define REPO_BASE_DIR for entity functions
REPO_BASE_DIR = repo_service.base_dir

@router.post("/submit-repo", status_code=status.HTTP_200_OK)
async def submit_repository_details(credentials: RepoCredentials):
    """
    Accepts repository URL and credentials.
    Returns acknowledgment of receipt.
    """
    try:
        logger.info(f"Received repository submission: URL={credentials.repo_url}, Username={credentials.username}")
        # For backwards compatibility with Iteration 1
        return {"message": "Repository details received successfully", "repo_url": str(credentials.repo_url)}
    except Exception as e:
        logger.error(f"Error processing repository submission: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.post("/clone", response_model=RepoResponse, status_code=status.HTTP_200_OK)
async def clone_repository(credentials: RepoCredentials, background_tasks: BackgroundTasks):
    """
    Clones the repository from the provided URL using the provided credentials.
    """
    try:
        # Extract the repository URL and credentials
        repo_url = str(credentials.repo_url)
        username = credentials.username
        password = credentials.password
        
        logger.info(f"Attempting to clone repository: {repo_url}")
        
        # Clone the repository
        result = repo_service.clone_repository(
            repo_url=repo_url,
            username=username,
            password=password
        )
        
        # Check if cloning was successful
        if result["status"] == "error":
            logger.error(f"Failed to clone repository: {result['message']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        # Return the response
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error cloning repository: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/analyze/{repo_name}", response_model=ProjectTypeResponse, status_code=status.HTTP_200_OK)
async def analyze_repository(repo_name: str):
    """
    Analyzes the cloned repository to identify its type (Maven/Gradle) and if it's a Spring Boot project.
    """
    try:
        # First check for repos with unique suffixes 
        base_dir = repo_service.base_dir
        possible_dirs = [d for d in os.listdir(base_dir) 
                         if os.path.isdir(os.path.join(base_dir, d)) and 
                            (d.startswith(f"{repo_name}_") or d == repo_name)]
        
        if not possible_dirs:
            logger.error(f"Repository not found: {repo_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository not found: {repo_name}"
            )
        
        # Get the latest directory by modification time (newest clone)
        repo_dirs_with_mtime = [(d, os.path.getmtime(os.path.join(base_dir, d))) 
                               for d in possible_dirs]
        repo_dirs_with_mtime.sort(key=lambda x: x[1], reverse=True)
        latest_dir = repo_dirs_with_mtime[0][0]
        
        # Use the latest directory
        repo_path = os.path.join(base_dir, latest_dir)
        logger.info(f"Analyzing repository: {repo_name} using path {repo_path}")
        
        # Analyze the project
        result = project_analyzer.analyze_project(repo_path)
        
        # Check if analysis was successful
        if result["status"] == "error":
            logger.error(f"Failed to analyze repository: {result['message']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        # Enhance the result with a friendly message
        result["message"] = f"Identified as {result['project_type']} project using {result['build_system']}"
        
        # Return the response
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error analyzing repository: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        ) 

@router.get("/endpoints/{repo_name}", response_model=EndpointResponse, status_code=status.HTTP_200_OK)
async def get_repository_endpoints(repo_name: str, role: Optional[str] = Query(None, description="User role (developer, architect, product_owner, qa)")):
    """
    Parses the cloned repository to identify REST controllers and their exposed endpoint methods.
    Optionally filters endpoint data based on the specified user role.
    """
    try:
        # First check for repos with unique suffixes 
        base_dir = repo_service.base_dir
        possible_dirs = [d for d in os.listdir(base_dir) 
                         if os.path.isdir(os.path.join(base_dir, d)) and 
                            (d.startswith(f"{repo_name}_") or d == repo_name)]
        
        if not possible_dirs:
            logger.error(f"Repository not found: {repo_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository not found: {repo_name}"
            )
        
        # Get the latest directory by modification time (newest clone)
        repo_dirs_with_mtime = [(d, os.path.getmtime(os.path.join(base_dir, d))) 
                               for d in possible_dirs]
        repo_dirs_with_mtime.sort(key=lambda x: x[1], reverse=True)
        latest_dir = repo_dirs_with_mtime[0][0]
        
        # Use the latest directory
        repo_path = os.path.join(base_dir, latest_dir)
        logger.info(f"Parsing endpoints in repository: {repo_name} using path {repo_path}")
        
        # First check if this is a Spring Boot project
        project_info = project_analyzer.analyze_project(repo_path)
        
        if project_info["status"] == "error":
            return {
                "status": "error",
                "message": f"Failed to analyze repository: {project_info['message']}",
                "endpoints": []
            }
        
        # Continue even if not Spring Boot, but log a warning
        if not project_info.get("is_spring_boot", False):
            logger.warning(f"Repository {repo_name} is not identified as a Spring Boot project. Endpoint detection may be unreliable.")
        
        # Parse the endpoints
        architecture_data = endpoint_parser.parse_endpoints(repo_path)
        
        # Extract just the endpoints list from the architecture_data
        endpoints = architecture_data.get("endpoints", [])
        
        # Apply role-based filtering if a role is specified
        if role:
            logger.info(f"Filtering endpoints for role: {role}")
            endpoints = role_filter.filter_endpoints(endpoints, role)
        
        # Convert the detailed endpoint dictionaries to simplified EndpointInfo objects
        endpoint_info_list = []
        for endpoint in endpoints:
            endpoint_info_list.append({
                "controller": endpoint.get("controller", ""),
                "method": endpoint.get("method", ""),
                "http_method": endpoint.get("http_method", ""),
                "path": endpoint.get("path", "")
            })
        
        if not endpoint_info_list:
            return {
                "status": "success",
                "message": "No endpoints found in the repository",
                "endpoints": []
            }
        
        # Return the response
        return {
            "status": "success",
            "message": f"Found {len(endpoint_info_list)} endpoints in the repository" + (f" (filtered for {role} role)" if role else ""),
            "endpoints": endpoint_info_list
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error parsing endpoints: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        ) 

@router.get("/swagger/{repo_name}")
async def get_repository_openapi_spec(repo_name: str):
    """
    Generates and returns an OpenAPI 3.0 (Swagger) specification for the repository's endpoints.
    """
    try:
        # First check for repos with unique suffixes 
        base_dir = repo_service.base_dir
        possible_dirs = [d for d in os.listdir(base_dir) 
                         if os.path.isdir(os.path.join(base_dir, d)) and 
                            (d.startswith(f"{repo_name}_") or d == repo_name)]
        
        if not possible_dirs:
            logger.error(f"Repository not found: {repo_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository not found: {repo_name}"
            )
        
        # Get the latest directory by modification time (newest clone)
        repo_dirs_with_mtime = [(d, os.path.getmtime(os.path.join(base_dir, d))) 
                               for d in possible_dirs]
        repo_dirs_with_mtime.sort(key=lambda x: x[1], reverse=True)
        latest_dir = repo_dirs_with_mtime[0][0]
        
        # Use the latest directory
        repo_path = os.path.join(base_dir, latest_dir)
        
        # Get endpoints from the endpoint parser
        architecture_data = endpoint_parser.parse_endpoints(repo_path)
        endpoints_info = architecture_data.get("endpoints", [])
        
        if not endpoints_info:
            return Response(
                content=json.dumps({
                    "openapi": "3.0.0",
                    "info": {
                        "title": f"{repo_name} API",
                        "description": "No endpoints found in this repository",
                        "version": "1.0.0"
                    },
                    "paths": {}
                }),
                media_type="application/json"
            )
        
        # Generate the OpenAPI spec
        openapi_spec = swagger_generator.generate_openapi_spec(endpoints_info, repo_name)
        
        # Return the OpenAPI spec as JSON
        return Response(
            content=json.dumps(openapi_spec, indent=2),
            media_type="application/json"
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating OpenAPI spec: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        ) 

@router.get("/export/markdown/{repo_name}")
async def export_markdown_documentation(repo_name: str):
    """
    Generates and returns a Markdown document containing API documentation.
    """
    try:
        # First check for repos with unique suffixes 
        base_dir = repo_service.base_dir
        possible_dirs = [d for d in os.listdir(base_dir) 
                         if os.path.isdir(os.path.join(base_dir, d)) and 
                            (d.startswith(f"{repo_name}_") or d == repo_name)]
        
        if not possible_dirs:
            logger.error(f"Repository not found: {repo_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository not found: {repo_name}"
            )
        
        # Get the latest directory by modification time (newest clone)
        repo_dirs_with_mtime = [(d, os.path.getmtime(os.path.join(base_dir, d))) 
                               for d in possible_dirs]
        repo_dirs_with_mtime.sort(key=lambda x: x[1], reverse=True)
        latest_dir = repo_dirs_with_mtime[0][0]
        
        # Use the latest directory
        repo_path = os.path.join(base_dir, latest_dir)
        
        # Get endpoints from the endpoint parser
        architecture_data = endpoint_parser.parse_endpoints(repo_path)
        endpoints_info = architecture_data.get("endpoints", [])
        
        if not endpoints_info:
            content = f"# API Documentation for {repo_name}\n\nNo endpoints found in this repository."
            return Response(
                content=content,
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f"attachment; filename={repo_name}_api_documentation.md"
                }
            )
        
        # Generate the Markdown documentation
        markdown_content = markdown_exporter.generate_markdown(endpoints_info, repo_name)
        
        # Return the Markdown document
        return Response(
            content=markdown_content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename={repo_name}_api_documentation.md"
            }
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating Markdown documentation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        ) 

@router.get("/features/{repo_name}")
async def get_repository_feature_files(repo_name: str):
    """
    Generates and returns a list of feature files for the repository's endpoints.
    """
    try:
        # First check for repos with unique suffixes 
        base_dir = repo_service.base_dir
        possible_dirs = [d for d in os.listdir(base_dir) 
                         if os.path.isdir(os.path.join(base_dir, d)) and 
                            (d.startswith(f"{repo_name}_") or d == repo_name)]
        
        if not possible_dirs:
            logger.error(f"Repository not found: {repo_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository not found: {repo_name}"
            )
        
        # Get the latest directory by modification time (newest clone)
        repo_dirs_with_mtime = [(d, os.path.getmtime(os.path.join(base_dir, d))) 
                               for d in possible_dirs]
        repo_dirs_with_mtime.sort(key=lambda x: x[1], reverse=True)
        latest_dir = repo_dirs_with_mtime[0][0]
        
        # Use the latest directory
        repo_path = os.path.join(base_dir, latest_dir)
        
        # Get endpoints from the endpoint parser
        architecture_data = endpoint_parser.parse_endpoints(repo_path)
        endpoints_info = architecture_data.get("endpoints", [])
        
        if not endpoints_info:
            return {
                "status": "success",
                "message": "No endpoints found for feature file generation",
                "feature_files": []
            }
        
        # Generate feature files
        feature_files = feature_builder.generate_feature_files(endpoints_info, repo_name)
        
        # Add a preview snippet to each feature file
        for feature in feature_files:
            content = feature["content"]
            lines = content.split("\n")
            preview = "\n".join(lines[:5]) + "..."  # First 5 lines as preview
            feature["preview"] = preview
        
        return {
            "status": "success",
            "message": f"Generated {len(feature_files)} feature files",
            "feature_files": feature_files
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating feature files: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/features/download/{repo_name}")
async def download_feature_files(repo_name: str):
    """
    Generates and returns a ZIP file containing all feature files for the repository.
    """
    try:
        # First check for repos with unique suffixes 
        base_dir = repo_service.base_dir
        possible_dirs = [d for d in os.listdir(base_dir) 
                         if os.path.isdir(os.path.join(base_dir, d)) and 
                            (d.startswith(f"{repo_name}_") or d == repo_name)]
        
        if not possible_dirs:
            logger.error(f"Repository not found: {repo_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository not found: {repo_name}"
            )
        
        # Get the latest directory by modification time (newest clone)
        repo_dirs_with_mtime = [(d, os.path.getmtime(os.path.join(base_dir, d))) 
                               for d in possible_dirs]
        repo_dirs_with_mtime.sort(key=lambda x: x[1], reverse=True)
        latest_dir = repo_dirs_with_mtime[0][0]
        
        # Use the latest directory
        repo_path = os.path.join(base_dir, latest_dir)
        
        # Get endpoints from the endpoint parser
        architecture_data = endpoint_parser.parse_endpoints(repo_path)
        endpoints_info = architecture_data.get("endpoints", [])
        
        if not endpoints_info:
            # Return an empty zip file
            empty_zip, filename = feature_builder.create_zip_file([], repo_name)
            return Response(
                content=empty_zip,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}"
                }
            )
        
        # Generate feature files
        feature_files = feature_builder.generate_feature_files(endpoints_info, repo_name)
        
        # Create a zip file with all feature files
        zip_bytes, filename = feature_builder.create_zip_file(feature_files, repo_name)
        
        # Return the zip file
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating feature files ZIP: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        ) 

@router.get("/entities/{repo_name}", response_model=Dict[str, Any])
async def get_entities(repo_name: str, role: Optional[str] = Query(None, description="User role (developer, architect, product_owner, qa)")):
    """
    Parse the cloned repository to identify entity classes and their relationships.
    Optionally filters entity data based on the specified user role.
    """
    try:
        # Get the repository path
        repo_path = _get_repo_path(repo_name)
        if not repo_path:
            logger.error(f"Repository not found: {repo_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository not found: {repo_name}"
            )
        
        logger.info(f"Parsing entities in repository: {repo_name} using path {repo_path}")
        
        # Parse entities using the service
        entity_parser = EntityParser(repo_path)
        entities = entity_parser.parse_entities()
        
        # Apply role-based filtering if a role is specified
        if role:
            logger.info(f"Filtering entities for role: {role}")
            entities = role_filter.filter_entities(entities, role)
        
        # Return the result
        return {
            "status": "success",
            "message": f"Found {len(entities['entities']) if 'entities' in entities else 0} entities in the repository" + (f" (filtered for {role} role)" if role else ""),
            **entities
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error parsing entities: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/diagrams/entities/{repo_name}", response_model=Dict[str, Any])
async def get_entity_diagram(repo_name: str, diagram_type: str = "class"):
    """
    Generates UML diagrams for entity relationships.
    """
    try:
        # Check if the repository exists
        repo_path = _get_repo_path(repo_name)
        
        # Generate the diagram
        diagram_generator = PlantUMLGenerator(repo_path)
        
        # Use the improved diagram generator method that handles its own errors
        diagram_result = diagram_generator.generate_diagram(diagram_type)
        return diagram_result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating entity diagram: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred generating the diagram: {str(e)}"
        )

@router.get("/diagrams/use-cases/{repo_name}", response_model=Dict[str, Any])
async def get_use_case_diagram(repo_name: str):
    """
    Generates a use case diagram from parsed Gherkin features.
    """
    try:
        repo_path = _get_repo_path(repo_name)
        
        # Create diagram renderer
        renderer = DiagramRenderer(repo_path)
        
        # Generate use case diagram
        result = renderer.generate_diagram("use-case")
        
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating use case diagram: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/diagrams/comprehensive-use-cases/{repo_name}", response_model=Dict[str, Any])
async def get_comprehensive_use_case_diagram(repo_name: str):
    """
    Generates a comprehensive use case diagram showing controllers, endpoints, and actors.
    """
    try:
        repo_path = _get_repo_path(repo_name)
        
        # Create diagram renderer
        renderer = DiagramRenderer(repo_path)
        
        # Generate comprehensive use case diagram
        result = renderer.generate_diagram("comprehensive-use-case")
        
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating comprehensive use case diagram: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/diagrams/interaction/{repo_name}", response_model=Dict[str, Any])
async def get_interaction_diagram(repo_name: str):
    """
    Generates an interaction diagram showing method calls between components.
    """
    try:
        repo_path = _get_repo_path(repo_name)
        
        # Create diagram renderer
        renderer = DiagramRenderer(repo_path)
        
        # Generate interaction diagram
        result = renderer.generate_diagram("interaction")
        
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating interaction diagram: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/diagrams/comprehensive-interaction/{repo_name}", response_model=Dict[str, Any])
async def get_comprehensive_interaction_diagram(repo_name: str):
    """
    Generates a comprehensive interaction diagram showing the full system architecture.
    """
    try:
        repo_path = _get_repo_path(repo_name)
        
        # Create diagram renderer
        renderer = DiagramRenderer(repo_path)
        
        # Generate comprehensive interaction diagram
        result = renderer.generate_diagram("comprehensive-interaction")
        
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating comprehensive interaction diagram: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/diagrams/class/{repo_name}", response_model=Dict[str, Any])
async def get_class_diagram(repo_name: str):
    """
    Generates a class diagram showing entities, repositories, and services.
    """
    try:
        repo_path = _get_repo_path(repo_name)
        
        # Create diagram renderer
        renderer = DiagramRenderer(repo_path)
        
        # Generate class diagram
        result = renderer.generate_diagram("class")
        
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating class diagram: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

# Helper function to get repo path
def _get_repo_path(repo_name: str):
    base_dir = repo_service.base_dir
    possible_dirs = [d for d in os.listdir(base_dir) 
                    if os.path.isdir(os.path.join(base_dir, d)) and 
                        (d.startswith(f"{repo_name}_") or d == repo_name)]
    
    if not possible_dirs:
        logger.error(f"Repository not found: {repo_name}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_name}"
        )
    
    # Get the latest directory by modification time (newest clone)
    repo_dirs_with_mtime = [(d, os.path.getmtime(os.path.join(base_dir, d))) 
                           for d in possible_dirs]
    repo_dirs_with_mtime.sort(key=lambda x: x[1], reverse=True)
    latest_dir = repo_dirs_with_mtime[0][0]
    
    return os.path.join(base_dir, latest_dir)

class ConfluencePublishRequest(BaseModel):
    """Request model for publishing to Confluence."""
    repo_name: str
    page_title: str
    space_key: str
    confluence_url: str
    username: str
    api_token: str
    selected_sections: List[str]
    parent_page: Optional[str] = None

@router.post("/publish/confluence", response_model=Dict[str, Any])
async def publish_to_confluence(request: ConfluencePublishRequest):
    """
    Publishes selected content to a Confluence page.
    """
    try:
        repo_name = request.repo_name
        repo_path = _get_repo_path(repo_name)
        
        # Validate selected sections
        valid_sections = ["api_docs", "features", "diagrams", "flows"]
        for section in request.selected_sections:
            if section not in valid_sections:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid section: {section}. Valid options are: {', '.join(valid_sections)}"
                )
        
        # Build the documentation payload
        payload_builder = PublishPayloadBuilder(repo_path, repo_name)
        sections_content = payload_builder.build_documentation_payload(request.selected_sections)
        
        # Convert to Confluence format
        converter = MarkdownToConfluenceConverter()
        content = converter.create_page_with_toc(request.page_title, sections_content)
        
        # Initialize Confluence publisher
        publisher = ConfluencePublisher(
            base_url=request.confluence_url,
            username=request.username,
            api_token=request.api_token
        )
        
        # Publish content
        result = publisher.publish_content(
            space_key=request.space_key,
            title=request.page_title,
            content=content,
            parent_id=request.parent_page
        )
        
        if result.get("status") == "success":
            # Extract the URL from the response if available
            page_url = None
            if result.get("data") and result["data"].get("_links"):
                page_url = result["data"]["_links"].get("webui")
                
                # If it's a relative URL, prepend the base Confluence URL
                if page_url and not page_url.startswith("http"):
                    page_url = f"{request.confluence_url}{page_url}"
            
            return {
                "status": "success",
                "message": "Documentation published successfully to Confluence",
                "url": page_url
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to publish to Confluence: {result.get('message', 'Unknown error')}"
            }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error publishing to Confluence: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/flows/{repo_name}", response_model=FlowResponse, status_code=status.HTTP_200_OK)
async def get_endpoint_flows(repo_name: str, role: Optional[str] = Query(None, description="User role (developer, architect, product_owner, qa)")):
    """
    Analyzes method call flows starting from controller endpoints, following through services to repositories.
    Optionally filters flow data based on the specified user role.
    """
    try:
        # Get repository path
        repo_path = _get_repo_path(repo_name)
        if not repo_path:
            logger.error(f"Repository not found: {repo_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository not found: {repo_name}"
            )
        
        logger.info(f"Analyzing endpoint flows in repository: {repo_name} using path {repo_path}")
        
        # First check if this is a Spring Boot project
        project_info = project_analyzer.analyze_project(repo_path)
        
        if project_info["status"] == "error":
            return {
                "status": "error",
                "message": f"Failed to analyze repository: {project_info['message']}",
                "flows": []
            }
        
        # Continue even if not Spring Boot, but log a warning
        if not project_info.get("is_spring_boot", False):
            logger.warning(f"Repository {repo_name} is not identified as a Spring Boot project. Flow analysis may be unreliable.")
        
        # First get all endpoints
        architecture_data = endpoint_parser.parse_endpoints(repo_path)
        
        # Check if architecture_data is a dictionary with endpoints key (new format)
        if isinstance(architecture_data, dict) and "endpoints" in architecture_data:
            endpoints = architecture_data.get("endpoints", [])
        else:
            # Backward compatibility for old format where endpoints was returned directly
            endpoints = architecture_data
            
        if not endpoints:
            return {
                "status": "success",
                "message": "No endpoints found in the repository",
                "flows": []
            }
        
        # Analyze flows for each endpoint
        flows = flow_analyzer.analyze_flows(repo_path)
        
        # Apply role-based filtering if a role is specified
        if role:
            # For flows, we might just want to filter out certain parts of the flow that are
            # not relevant for the role (like implementation details for product owners)
            filtered_flows = []
            for flow in flows:
                if role == "developer" or role == "architect":
                    # Developers and architects see everything
                    filtered_flows.append(flow)
                elif role == "product_owner":
                    # Product owners just see a simplified version (controller -> service) without details
                    simple_flow = {
                        "controller": flow["controller"],
                        "endpoint": flow["endpoint"],
                        "http_method": flow["http_method"],
                        "flow": []
                    }
                    # Include only first level of flow (controller -> service)
                    for entry in flow["flow"]:
                        if entry["class_type"] in ["controller", "service"]:
                            simple_entry = {
                                "class_name": entry["class_name"],
                                "class_type": entry["class_type"],
                                "method": entry["method"],
                                "parameters": entry.get("parameters", []),
                                "return_type": entry.get("return_type", "void"),
                                "calls": []  # No detailed calls for product owners
                            }
                            simple_flow["flow"].append(simple_entry)
                    filtered_flows.append(simple_flow)
                elif role == "qa":
                    # QA sees full flow but without implementation details
                    qa_flow = flow.copy()
                    for entry in qa_flow["flow"]:
                        # Simplify rather than remove required fields
                        entry["parameters"] = []  # Empty list instead of removing
                        entry["return_type"] = "simplified"  # Simplified value instead of removing
                    filtered_flows.append(qa_flow)
            
            flows = filtered_flows
        
        return {
            "status": "success",
            "message": f"Successfully analyzed flows for {len(flows)} endpoints" + (f" (filtered for {role} role)" if role else ""),
            "flows": flows
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error analyzing endpoint flows: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        ) 

@router.get("/schema-overview/{repo_name}", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_schema_overview(repo_name: str, role: Optional[str] = Query(None, description="User role (developer, architect, product_owner, qa)")):
    """
    Provides a comprehensive overview of the database schema, mapping entities to tables, and showing their relationships and usage.
    """
    try:
        # Get repository path
        repo_path = _get_repo_path(repo_name)
        if not repo_path:
            logger.error(f"Repository not found: {repo_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository not found: {repo_name}"
            )
        
        logger.info(f"Generating schema overview for repository: {repo_name} using path {repo_path}")
        
        # First get all entities
        entity_parser_instance = EntityParser(repo_path)
        entities = entity_parser_instance.parse_entities()
        
        if not entities.get("entities"):
            return {
                "status": "success",
                "message": "No entities found in the repository",
                "tables": {}
            }
        
        # Get all endpoints
        architecture_data = endpoint_parser.parse_endpoints(repo_path)
        endpoints = architecture_data.get("endpoints", [])
        
        # Map the schema
        schema = schema_mapper.map_schema(repo_path, entities, endpoints)
        
        # Apply role-based filtering if a role is specified
        if role:
            # For schema overview, we might want to simplify for product owners or QA
            if role == "product_owner":
                # Simplify table names and relationships
                simplified_tables = {}
                for table_name, table_data in schema.get("tables", {}).items():
                    business_name = table_data.get("entity", "").replace("Entity", "")
                    # Add spaces before capital letters, except the first letter
                    business_name = ''.join([' ' + c if c.isupper() and i > 0 else c for i, c in enumerate(business_name)])
                    
                    simplified_tables[table_name] = {
                        "business_name": business_name.strip(),
                        "used_by": table_data.get("used_by", []),
                        "relations": [rel.replace("_", " ") for rel in table_data.get("relations", [])]
                    }
                schema["tables"] = simplified_tables
                # Remove detailed entity data
                schema.pop("entities", None)
            elif role == "qa":
                # Focus on tables used by endpoints
                qa_tables = {}
                for table_name, table_data in schema.get("tables", {}).items():
                    if table_data.get("used_by"):
                        qa_tables[table_name] = table_data
                schema["tables"] = qa_tables
                # Remove detailed entity data
                schema.pop("entities", None)
            elif role == "architect":
                # Architects get the full schema but without field details
                for entity_name, entity_data in schema.get("entities", {}).items():
                    entity_data.pop("fields", None)
        
        return {
            "status": "success",
            "message": f"Generated schema overview with {len(schema.get('tables', {}))} tables" + (f" (filtered for {role} role)" if role else ""),
            "tables": schema.get("tables", {}),
            "entities": schema.get("entities", {}) if role != "product_owner" and role != "qa" else {}
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating schema overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        ) 