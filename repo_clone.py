"""
Repository Cloning Module
Handles Git repository cloning with metadata tracking and security.
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from typing import Optional, Dict, Tuple
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RepositoryCloner:
    """
    Manages Git repository cloning with metadata tracking.
    
    Architecture:
    - Clone path: ../clone_repo_local_path
    - Metadata path: ../clone_repo_metadata
    - Each repo: clone_repo_local_path/{owner}/{repo_name}
    - Each metadata: clone_repo_metadata/{repo_id}.json
    """

    def __init__(
        self,
        clone_base_dir: str = r"../clone_repo_local_path",
        metadata_dir: str = r"../clone_repo_metadata"
    ):
        """
        Initialize the repository cloner.
        
        Args:
            clone_base_dir: Base directory for cloned repositories
            metadata_dir: Directory for storing metadata JSON files
        """
        self.clone_base_dir = Path(clone_base_dir)
        self.metadata_dir = Path(metadata_dir)
        
        # Create directories if they don't exist
        self.clone_base_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Cloner initialized with base: {self.clone_base_dir}")

    @staticmethod
    def _parse_github_url(repo_url: str) -> Optional[Dict[str, str]]:
        """
        Parse GitHub URL to extract owner and repo name.
        
        Supports:
        - https://github.com/owner/repo.git
        - https://github.com/owner/repo
        - git@github.com:owner/repo.git
        
        Returns:
            Dict with 'owner' and 'repo' keys, or None if invalid
        """
        repo_url = repo_url.strip()
        
        # Handle HTTPS URLs
        if repo_url.startswith("https://"):
            try:
                parsed = urlparse(repo_url)
                path_parts = parsed.path.strip("/").split("/")
                
                if len(path_parts) >= 2:
                    owner = path_parts[0]
                    repo_name = path_parts[1].replace(".git", "")
                    
                    if owner and repo_name:
                        return {"owner": owner, "repo": repo_name}
            except Exception as e:
                logger.error(f"Failed to parse HTTPS URL: {e}")
                return None
        
        # Handle SSH URLs (git@github.com:owner/repo.git)
        elif repo_url.startswith("git@"):
            try:
                # Extract path after colon
                path_part = repo_url.split(":")[-1]
                path_parts = path_part.split("/")
                
                if len(path_parts) >= 2:
                    owner = path_parts[0]
                    repo_name = path_parts[1].replace(".git", "")
                    
                    if owner and repo_name:
                        return {"owner": owner, "repo": repo_name}
            except Exception as e:
                logger.error(f"Failed to parse SSH URL: {e}")
                return None
        
        return None

    @staticmethod
    def _sanitize_path(path: str) -> str:
        """
        Sanitize path to prevent directory traversal attacks.
        Removes .. and other suspicious patterns.
        """
        path = str(path).replace("..", "").replace("~", "")
        return path

    def _get_clone_path(self, owner: str, repo_name: str) -> Path:
        """
        Generate safe clone path for repository.
        
        Format: clone_base_dir/{owner}/{repo_name}
        """
        # Sanitize owner and repo_name
        owner = self._sanitize_path(owner)
        repo_name = self._sanitize_path(repo_name)
        
        clone_path = self.clone_base_dir / owner / repo_name
        
        return clone_path

    def _generate_repo_id(self, owner: str, repo_name: str) -> str:
        """
        Generate unique repository ID for metadata tracking.
        
        Format: owner_repo_timestamp
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        repo_id = f"{owner}_{repo_name}_{timestamp}"
        return repo_id

    def _save_metadata(
        self,
        repo_id: str,
        url: str,
        owner: str,
        repo_name: str,
        clone_path: Path,
        status: str,
        error_message: Optional[str] = None
    ) -> Path:
        """
        Save repository metadata as JSON.
        
        Metadata structure:
        {
            "repo_id": "...",
            "url": "...",
            "owner": "...",
            "repo_name": "...",
            "clone_path": "...",
            "cloned_at": "ISO timestamp",
            "status": "success|failed|pending",
            "error": null or error message,
            "file_count": number,
            "languages": []
        }
        """
        metadata = {
            "repo_id": repo_id,
            "url": url,
            "owner": owner,
            "repo_name": repo_name,
            "clone_path": str(clone_path),
            "cloned_at": datetime.now().isoformat(),
            "status": status,
            "error": error_message,
            "file_count": None,
            "languages": []
        }
        
        # If clone was successful, count files and detect languages
        if status == "success" and clone_path.exists():
            try:
                file_count = sum(1 for _ in clone_path.rglob("*") if _.is_file())
                metadata["file_count"] = file_count
                
                # Detect languages from file extensions
                extensions = set()
                for file_path in clone_path.rglob("*"):
                    if file_path.is_file():
                        extensions.add(file_path.suffix)
                
                metadata["languages"] = sorted(list(extensions))
            except Exception as e:
                logger.warning(f"Failed to count files: {e}")
        
        # Save metadata JSON
        metadata_file = self.metadata_dir / f"{repo_id}.json"
        try:
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            logger.info(f"Metadata saved: {metadata_file}")
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
        
        return metadata_file

    def clone_repository(
        self,
        repo_url: str,
        overwrite: bool = False
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Clone a Git repository and save metadata.
        
        Args:
            repo_url: GitHub repository URL
            overwrite: If True, delete existing repo and re-clone
        
        Returns:
            Tuple of (success: bool, message: str, metadata: dict|None)
            
        Example:
            success, message, metadata = cloner.clone_repository(
                "https://github.com/c0derashish/ai-code-reviewer.git"
            )
            
            if success:
                print(f"Cloned to: {metadata['clone_path']}")
            else:
                print(f"Error: {message}")
        """
        
        # Parse GitHub URL
        parsed = self._parse_github_url(repo_url)
        if not parsed:
            error_msg = f"Invalid repository URL: {repo_url}"
            logger.error(error_msg)
            return False, error_msg, None
        
        owner = parsed["owner"]
        repo_name = parsed["repo"]
        
        logger.info(f"Cloning {owner}/{repo_name}...")
        
        # Generate paths and IDs
        clone_path = self._get_clone_path(owner, repo_name)
        repo_id = self._generate_repo_id(owner, repo_name)
        
        # Check if already cloned
        if clone_path.exists() and not overwrite:
            msg = f"Repository already exists at {clone_path}. Set overwrite=True to re-clone."
            logger.warning(msg)
            
            # Still save metadata for existing repo
            metadata_file = self._save_metadata(
                repo_id, repo_url, owner, repo_name, clone_path,
                status="exists"
            )
            
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            return True, msg, metadata
        
        # Remove existing directory if overwrite is True
        if clone_path.exists() and overwrite:
            try:
                shutil.rmtree(clone_path)
                logger.info(f"Removed existing repository at {clone_path}")
            except Exception as e:
                error_msg = f"Failed to remove existing repository: {e}"
                logger.error(error_msg)
                self._save_metadata(
                    repo_id, repo_url, owner, repo_name, clone_path,
                    status="failed", error_message=error_msg
                )
                return False, error_msg, None
        
        # Perform Git clone
        try:
            clone_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Use git command for cloning
            result = subprocess.run(
                ["git", "clone", repo_url, str(clone_path)],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                error_msg = f"Git clone failed: {result.stderr}"
                logger.error(error_msg)
                self._save_metadata(
                    repo_id, repo_url, owner, repo_name, clone_path,
                    status="failed", error_message=error_msg
                )
                return False, error_msg, None
            
            # Clone successful
            success_msg = f"Successfully cloned {owner}/{repo_name} to {clone_path}"
            logger.info(success_msg)
            
            # Save metadata
            metadata_file = self._save_metadata(
                repo_id, repo_url, owner, repo_name, clone_path,
                status="success"
            )
            
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            return True, success_msg, metadata
        
        except subprocess.TimeoutExpired:
            error_msg = "Git clone timed out (60 seconds)"
            logger.error(error_msg)
            self._save_metadata(
                repo_id, repo_url, owner, repo_name, clone_path,
                status="failed", error_message=error_msg
            )
            return False, error_msg, None
        
        except FileNotFoundError:
            error_msg = "Git is not installed or not found in PATH"
            logger.error(error_msg)
            self._save_metadata(
                repo_id, repo_url, owner, repo_name, clone_path,
                status="failed", error_message=error_msg
            )
            return False, error_msg, None
        
        except Exception as e:
            error_msg = f"Unexpected error during cloning: {str(e)}"
            logger.error(error_msg)
            self._save_metadata(
                repo_id, repo_url, owner, repo_name, clone_path,
                status="failed", error_message=error_msg
            )
            return False, error_msg, None

    def list_cloned_repositories(self) -> list[Dict]:
        """
        List all cloned repositories and their metadata.
        
        Returns:
            List of metadata dictionaries
        """
        repositories = []
        
        try:
            for metadata_file in self.metadata_dir.glob("*.json"):
                try:
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        repo_meta = json.load(f)
                        repositories.append(repo_meta)
                except Exception as e:
                    logger.warning(f"Failed to read metadata file {metadata_file}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to list repositories: {e}")
        
        return repositories

    def get_repository_metadata(self, repo_id: str) -> Optional[Dict]:
        """
        Retrieve metadata for a specific repository.
        
        Args:
            repo_id: Repository ID
        
        Returns:
            Metadata dictionary or None if not found
        """
        metadata_file = self.metadata_dir / f"{repo_id}.json"
        
        if not metadata_file.exists():
            logger.warning(f"Metadata file not found for repo_id: {repo_id}")
            return None
        
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read metadata: {e}")
            return None


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Initialize cloner
    cloner = RepositoryCloner()
    
    # Example: Clone a repository
    repo_url = "https://github.com/c0derashish/benchnewz-college-news-platform/"
    
    success, message, metadata = cloner.clone_repository(repo_url)
    
    print(f"Success: {success}")
    print(f"Message: {message}")
    
    if metadata:
        print(f"\nMetadata:")
        print(json.dumps(metadata, indent=2, ensure_ascii=False))
        print(f"\nClone path: {metadata['clone_path']}")
        print(f"File count: {metadata['file_count']}")
        print(f"Languages: {metadata['languages']}")
    
    # List all cloned repositories
    print("\n" + "="*60)
    print("All cloned repositories:")
    all_repos = cloner.list_cloned_repositories()
    for repo in all_repos:
        print(f"  - {repo['owner']}/{repo['repo_name']} ({repo['status']})")