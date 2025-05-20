import logging
from typing import List, Dict, Any, Tuple
import os
import re
import io
import zipfile
from datetime import datetime

logger = logging.getLogger(__name__)

class FeatureBuilder:
    """
    Service to generate Gherkin feature files from parsed endpoint data.
    """
    
    def __init__(self):
        pass
    
    def extract_feature_files(self, repo_path: str) -> Dict[str, Any]:
        """
        Extract feature files data for diagram generation.
        
        Args:
            repo_path: Path to the repository directory
            
        Returns:
            Dictionary containing feature files data to be used for diagram generation
        """
        logger.info(f"Extracting feature file data from repository: {repo_path}")
        
        # Import endpoint parser to get the endpoints data
        from .endpoint_parser import EndpointParser
        endpoint_parser = EndpointParser()
        endpoints_data = endpoint_parser.parse_endpoints(repo_path)
        
        # Extract the repository name from path
        repo_name = os.path.basename(repo_path)
        
        # Get endpoints list from the parsed data
        if isinstance(endpoints_data, dict) and "endpoints" in endpoints_data:
            endpoints = endpoints_data["endpoints"]
        else:
            endpoints = []
            logger.warning(f"Expected endpoints data to contain 'endpoints' key, got: {type(endpoints_data)}")
        
        # Convert endpoints to feature files
        feature_files = self.generate_feature_files(endpoints, repo_name)
        
        # Convert feature files to format suitable for diagram generation
        features_data = {
            "features": []
        }
        
        for feature_file in feature_files:
            content = feature_file["content"]
            controller = feature_file["controller"]
            
            # Extract feature title
            title_match = re.search(r'Feature:\s*(.*?)\s*\n', content)
            feature_title = title_match.group(1) if title_match else controller
            
            # Extract scenarios
            scenarios = []
            scenario_blocks = re.findall(r'Scenario:\s*(.*?)(?=\n\s*Scenario:|$)', content, re.DOTALL)
            
            for block in scenario_blocks:
                title_match = re.search(r'(.*?)\n', block)
                scenario_title = title_match.group(1).strip() if title_match else ""
                
                steps = []
                step_matches = re.findall(r'\s*(Given|When|Then|And)\s+(.*?)(?=\n\s*(?:Given|When|Then|And)|$)', block, re.DOTALL)
                
                for step_type, step_text in step_matches:
                    steps.append({
                        "type": step_type,
                        "text": step_text.strip()
                    })
                
                scenarios.append({
                    "title": scenario_title,
                    "steps": steps
                })
            
            features_data["features"].append({
                "title": feature_title,
                "scenarios": scenarios,
                "controller": controller
            })
        
        return features_data
    
    def generate_feature_files(self, endpoints: List[Dict[str, Any]], repo_name: str) -> List[Dict[str, Any]]:
        """
        Generate Gherkin feature files for the parsed endpoints.
        
        Args:
            endpoints: List of endpoint dictionaries with controller, method, http_method, and path
            repo_name: Name of the repository for documentation purposes
            
        Returns:
            List of dictionaries with feature file information
        """
        logger.info(f"Generating feature files for {repo_name} with {len(endpoints)} endpoints")
        
        feature_files = []
        
        # Group endpoints by controller
        controllers = {}
        for endpoint in endpoints:
            # Ensure endpoint is a dictionary and has a controller key
            if not isinstance(endpoint, dict):
                logger.warning(f"Skipping invalid endpoint format: {endpoint}")
                continue
                
            if "controller" not in endpoint:
                logger.warning(f"Skipping endpoint without controller: {endpoint}")
                continue
                
            controller = endpoint["controller"]
            if controller not in controllers:
                controllers[controller] = []
            controllers[controller].append(endpoint)
        
        # Create a feature file for each controller
        for controller, ctrl_endpoints in controllers.items():
            feature_content = self._generate_controller_feature(controller, ctrl_endpoints)
            
            # Create sanitized filename
            filename = self._sanitize_filename(controller) + ".feature"
            
            feature_files.append({
                "filename": filename,
                "content": feature_content,
                "controller": controller,
                "endpoint_count": len(ctrl_endpoints)
            })
        
        return feature_files
    
    def _generate_controller_feature(self, controller: str, endpoints: List[Dict[str, Any]]) -> str:
        """
        Generate a feature file for a controller.
        
        Args:
            controller: Name of the controller
            endpoints: List of endpoints for this controller
            
        Returns:
            String containing the feature file content
        """
        # Extract a readable name from the controller class name
        feature_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', controller)
        feature_name = re.sub(r'Controller$', '', feature_name)
        
        feature_content = f"""Feature: {feature_name} API
  As an API consumer
  I want to interact with the {feature_name} endpoints
  So that I can perform operations related to {feature_name.lower()}

"""
        
        # Add a scenario for each endpoint
        for endpoint in endpoints:
            http_method = endpoint["http_method"]
            path = endpoint["path"]
            method_name = endpoint["method"]
            
            # Create a readable scenario name from the method name
            scenario_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', method_name)
            
            # Determine likely response codes based on HTTP method
            success_code = "200 OK"
            if http_method == "POST":
                success_code = "201 Created"
            elif http_method == "DELETE":
                success_code = "204 No Content"
            
            # Extract path parameters
            path_params = re.findall(r'\{([^}]+)\}', path)
            path_param_lines = ""
            if path_params:
                for param in path_params:
                    path_param_lines += f"    Given a valid {param} exists\n"
            
            # Create the scenario
            default_given = "    Given the API is available\n"
            feature_content += f"""  Scenario: {scenario_name}
{path_param_lines if path_param_lines else default_given}    When I send a {http_method} request to "{path}"
    Then I should receive a {success_code} response
    And the response should contain valid data

"""
        
        return feature_content
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string to be used as a filename."""
        # Remove Controller suffix if present
        name = re.sub(r'Controller$', '', name)
        
        # Replace any non-alphanumeric characters with underscores
        return re.sub(r'[^a-zA-Z0-9]', '_', name)
    
    def create_zip_file(self, feature_files: List[Dict[str, Any]], repo_name: str) -> Tuple[bytes, str]:
        """
        Create a zip file containing all the feature files.
        
        Args:
            feature_files: List of feature file dictionaries
            repo_name: Name of the repository
            
        Returns:
            Tuple of (zip file bytes, filename)
        """
        # Create a zip file in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for feature in feature_files:
                zip_file.writestr(feature["filename"], feature["content"])
        
        # Get the bytes from the in-memory zip file
        zip_bytes = zip_buffer.getvalue()
        
        # Generate a filename for the zip file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{repo_name}_features_{timestamp}.zip"
        
        return zip_bytes, filename 