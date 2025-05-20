import logging
import requests
import json
import base64
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

class ConfluencePublisher:
    """Class for publishing documentation to Confluence."""
    
    def __init__(self, base_url: str, username: str, api_token: str):
        """
        Initialize the Confluence Publisher.
        
        Args:
            base_url: The base URL of the Confluence instance (e.g., 'https://mycompany.atlassian.net/wiki')
            username: The username for Confluence (typically an email)
            api_token: The API token for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.auth = (username, api_token)
        self.api_url = f"{self.base_url}/rest/api/content"
        
    def _get_auth_header(self) -> Dict[str, str]:
        """Create the authentication header for Confluence API."""
        auth_str = f"{self.auth[0]}:{self.auth[1]}"
        encoded = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json"
        }
        
    def page_exists(self, space_key: str, title: str) -> Optional[str]:
        """
        Check if a page with the given title exists in the specified space.
        
        Returns:
            The page ID if found, None otherwise
        """
        try:
            params = {
                "spaceKey": space_key,
                "title": title,
                "expand": "version"
            }
            response = requests.get(
                self.api_url, 
                params=params,
                headers=self._get_auth_header()
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("results") and len(data["results"]) > 0:
                    return data["results"][0]["id"]
            
            return None
        except Exception as e:
            logger.error(f"Error checking if page exists: {str(e)}")
            return None
            
    def create_page(self, space_key: str, title: str, content: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new page in Confluence.
        
        Args:
            space_key: The space key where the page should be created
            title: The title of the page
            content: The HTML content of the page
            parent_id: Optional parent page ID for hierarchical structure
            
        Returns:
            Response data from Confluence API
        """
        try:
            page_data = {
                "type": "page",
                "title": title,
                "space": {"key": space_key},
                "body": {
                    "storage": {
                        "value": content,
                        "representation": "storage"
                    }
                }
            }
            
            # Add parent reference if provided
            if parent_id:
                page_data["ancestors"] = [{"id": parent_id}]
            
            response = requests.post(
                self.api_url,
                json=page_data,
                headers=self._get_auth_header()
            )
            
            if response.status_code in (200, 201):
                return {
                    "status": "success",
                    "message": "Page created successfully",
                    "data": response.json()
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to create page: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            logger.error(f"Error creating page: {str(e)}")
            return {
                "status": "error",
                "message": f"Exception: {str(e)}"
            }
            
    def update_page(self, page_id: str, title: str, content: str, version: int, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Update an existing page in Confluence.
        
        Args:
            page_id: The ID of the page to update
            title: The title of the page
            content: The HTML content of the page
            version: The current version number of the page
            parent_id: Optional parent page ID to move the page
            
        Returns:
            Response data from Confluence API
        """
        try:
            page_data = {
                "id": page_id,
                "type": "page",
                "title": title,
                "body": {
                    "storage": {
                        "value": content,
                        "representation": "storage"
                    }
                },
                "version": {
                    "number": version + 1
                }
            }
            
            # Add parent reference if provided
            if parent_id:
                page_data["ancestors"] = [{"id": parent_id}]
            
            response = requests.put(
                f"{self.api_url}/{page_id}",
                json=page_data,
                headers=self._get_auth_header()
            )
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "message": "Page updated successfully",
                    "data": response.json()
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to update page: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            logger.error(f"Error updating page: {str(e)}")
            return {
                "status": "error",
                "message": f"Exception: {str(e)}"
            }
            
    def publish_content(self, space_key: str, title: str, content: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Publish content to Confluence. Creates a new page or updates existing one.
        
        Args:
            space_key: The space key where the page should be published
            title: The title of the page
            content: The HTML content of the page
            parent_id: Optional parent page ID for hierarchical structure
            
        Returns:
            Response data with status and details
        """
        try:
            # Check if the page exists
            page_id = self.page_exists(space_key, title)
            
            if page_id:
                # Get the current version
                response = requests.get(
                    f"{self.api_url}/{page_id}?expand=version",
                    headers=self._get_auth_header()
                )
                
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"Failed to get page version: {response.status_code}"
                    }
                    
                version = response.json().get("version", {}).get("number", 0)
                
                # Update the page
                return self.update_page(page_id, title, content, version, parent_id)
            else:
                # Create a new page
                return self.create_page(space_key, title, content, parent_id)
                
        except Exception as e:
            logger.error(f"Error publishing content: {str(e)}")
            return {
                "status": "error",
                "message": f"Exception: {str(e)}"
            } 