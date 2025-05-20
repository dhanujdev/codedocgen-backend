import os
import shutil
import logging
import tempfile
import uuid
import time
from pathlib import Path
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

logger = logging.getLogger(__name__)

class RepoService:
    """Service for handling repository operations."""
    
    def __init__(self):
        # Base directory for cloned repositories
        self.base_dir = os.getenv("REPO_BASE_DIR", os.path.join(tempfile.gettempdir(), "codedocgen", "repos"))
        # Create the base directory if it doesn't exist
        os.makedirs(self.base_dir, exist_ok=True)
    
    def extract_repo_name(self, repo_url: str) -> str:
        """Extract repository name from URL."""
        # Remove .git extension if present
        clean_url = repo_url.strip().rstrip('/')
        if clean_url.endswith('.git'):
            clean_url = clean_url[:-4]
        
        # Extract the repo name from the URL
        return os.path.basename(clean_url)
    
    def get_repo_path(self, repo_name: str) -> str:
        """Get the full path to the repository directory."""
        return os.path.join(self.base_dir, repo_name)
    
    def clone_repository(self, repo_url: str, username: str = None, password: str = None) -> dict:
        """
        Clone a Git repository from the provided URL.
        
        Args:
            repo_url: The repository URL
            username: Optional username for authentication
            password: Optional password or token for authentication
            
        Returns:
            A dictionary with status information
        """
        repo_name = self.extract_repo_name(repo_url)
        
        # Create a unique directory for this clone attempt to avoid conflicts
        unique_suffix = str(uuid.uuid4())[:8]
        repo_path = os.path.join(self.base_dir, f"{repo_name}_{unique_suffix}")
        
        try:
            # Construct the git URL with credentials if provided
            if username and password:
                # Handle HTTPS URLs with authentication
                url_parts = repo_url.split('://')
                if len(url_parts) == 2 and url_parts[0].lower() == 'https':
                    auth_url = f"https://{username}:{password}@{url_parts[1]}"
                    logger.info(f"Cloning repository with authentication: {repo_url}")
                else:
                    # For non-HTTPS URLs or malformed URLs, try using the credentials directly
                    auth_url = repo_url
                    logger.warning(f"Non-HTTPS URL provided with credentials: {repo_url}")
            else:
                auth_url = repo_url
                logger.info(f"Cloning public repository: {repo_url}")
            
            # Clone the repository to the unique path
            logger.info(f"Cloning repository to {repo_path}")
            repo = Repo.clone_from(auth_url, repo_path)
            
            # Clean up any old repository with the same name if it exists
            original_repo_path = self.get_repo_path(repo_name)
            if os.path.exists(original_repo_path):
                try:
                    logger.info(f"Attempting to remove old repository at {original_repo_path}")
                    shutil.rmtree(original_repo_path, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"Could not remove old repository, but will continue: {e}")
            
            # Rename the unique directory to the standard name
            # If this fails, we'll just use the unique directory
            try:
                if os.path.exists(original_repo_path):
                    logger.warning(f"Could not rename repository directory, using unique path instead")
                else:
                    os.rename(repo_path, original_repo_path)
                    repo_path = original_repo_path
            except Exception as e:
                logger.warning(f"Error renaming repository directory, using unique path: {e}")
            
            logger.info(f"Successfully cloned repository to {repo_path}")
            return {
                "status": "success",
                "message": f"Cloned repository: {repo_name}",
                "repo_name": repo_name,
                "repo_path": repo_path
            }
            
        except GitCommandError as e:
            error_msg = str(e)
            # Avoid logging credentials if they're in the error message
            safe_error = error_msg.replace(password or "", "********") if password else error_msg
            logger.error(f"Git command error while cloning repository: {safe_error}")
            return {
                "status": "error",
                "message": f"Error cloning repository: {self._get_user_friendly_error(e)}",
                "error_details": safe_error
            }
        except Exception as e:
            logger.error(f"Unexpected error while cloning repository: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
                "error_details": str(e)
            }
    
    def _get_user_friendly_error(self, error: Exception) -> str:
        """Convert Git errors to user-friendly messages."""
        error_msg = str(error).lower()
        
        if "authentication failed" in error_msg or "could not read password" in error_msg:
            return "Authentication failed. Please check your username and password/token."
        elif "not found" in error_msg or "repository not found" in error_msg:
            return "Repository not found. Please check the URL and your access permissions."
        elif "timeout" in error_msg:
            return "Connection timed out. Please check your internet connection and try again."
        else:
            return "Failed to clone repository. Please check the URL and your credentials." 