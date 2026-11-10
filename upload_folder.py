"""
Local Project Upload Handler
Manages local folder uploads with validation and metadata tracking.
Maintains consistent metadata structure with RepositoryCloner.
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LocalProjectUploader:
    """
    Manages local project folder uploads with metadata tracking.
    
    Architecture:
    - Upload reference path: D:\sem 7th project\ai-code-reviewer\clone_repo_local_path
    - Metadata path: D:\sem 7th project\ai-code-reviewer\clone_repo_metedata
    - Each project: clone_repo_local_path/{owner}/{project_name}
    - Each metadata: clone_repo_metadata/{project_id}.json
    
    Note: "Upload reference" means we track the original path, not copy the entire folder.
    This avoids bloating storage with duplicate code.
    """

    def __init__(
        self,
        upload_base_dir: str = r"D:\sem 7th project\ai-code-reviewer\clone_repo_local_path",
        metadata_dir: str = r"D:\sem 7th project\ai-code-reviewer\clone_repo_metedata"
    ):
        """
        Initialize the local project uploader.
        
        Args:
            upload_base_dir: Base directory for upload references
            metadata_dir: Directory for storing metadata JSON files
        """
        self.upload_base_dir = Path(upload_base_dir)
        self.metadata_dir = Path(metadata_dir)
        
        # Create directories if they don't exist
        self.upload_base_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Uploader initialized with base: {self.upload_base_dir}")

    @staticmethod
    def _sanitize_path(path: str) -> str:
        """
        Sanitize path to prevent directory traversal attacks.
        Removes .. and other suspicious patterns.
        """
        path = str(path).replace("..", "").replace("~", "")
        return path

    @staticmethod
    def _validate_folder_path(folder_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that folder path exists and is readable.
        
        Returns:
            Tuple of (is_valid: bool, error_message: str|None)
        """
        folder = Path(folder_path)
        
        # Check if path exists
        if not folder.exists():
            return False, f"Folder does not exist: {folder_path}"
        
        # Check if it's a directory
        if not folder.is_dir():
            return False, f"Path is not a directory: {folder_path}"
        
        # Check if readable
        if not os.access(folder, os.R_OK):
            return False, f"Folder is not readable: {folder_path}"
        
        return True, None

    @staticmethod
    def _extract_project_name(folder_path: str) -> str:
        """
        Extract project name from folder path.
        
        Example:
            /home/user/my-project → my-project
            D:\Projects\awesome-api → awesome-api
        """
        folder = Path(folder_path)
        return folder.name

    @staticmethod
    def _extract_owner_from_path(folder_path: str) -> str:
   
        folder = Path(folder_path)
        # Use parent folder name as owner
        return folder.parent.name

    def _get_upload_reference_path(
        self,
        owner: str,
        project_name: str
    ) -> Path:
        """
        Generate path for upload reference.
        
        Format: upload_base_dir/{owner}/{project_name}
        
        This creates a structured directory similar to GitHub clones.
        """
        owner = self._sanitize_path(owner)
        project_name = self._sanitize_path(project_name)
        
        reference_path = self.upload_base_dir / owner / project_name
        
        return reference_path

    def _generate_project_id(self, owner: str, project_name: str) -> str:
        """
        Generate unique project ID for metadata tracking.
        
        Format: owner_project_timestamp
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_id = f"{owner}_{project_name}_{timestamp}"
        return project_id

    def _create_reference_symlink(
        self,
        original_path: Path,
        reference_path: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Create symlink from reference path to original folder.
        
        This avoids copying the entire project while maintaining
        a structured directory layout.
        
        Returns:
            Tuple of (success: bool, error_message: str|None)
        """
        try:
            # Create parent directories
            reference_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Remove existing symlink/folder if exists
            if reference_path.exists() or reference_path.is_symlink():
                if reference_path.is_symlink():
                    reference_path.unlink()
                elif reference_path.is_dir():
                    shutil.rmtree(reference_path)
            
            # Create symlink
            try:
                # Try creating symlink (Unix/Linux/macOS)
                os.symlink(original_path, reference_path)
                logger.info(f"Created symlink: {reference_path} → {original_path}")
                return True, None
            except OSError:
                # Fallback for Windows or if symlink fails
                # Store original path in reference file instead
                reference_info_file = reference_path.parent / f"{reference_path.name}.path"
                with open(reference_info_file, "w", encoding="utf-8") as f:
                    f.write(str(original_path))
                logger.info(f"Created path reference: {reference_info_file}")
                return True, None
        
        except Exception as e:
            error_msg = f"Failed to create reference: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def _count_files_and_extensions(
        self,
        folder_path: Path,
        max_files: int = 10000
    ) -> Tuple[int, set]:
        """
        Count files and extract file extensions.
        
        Args:
            folder_path: Path to project folder
            max_files: Limit to prevent scanning huge repositories
        
        Returns:
            Tuple of (file_count: int, extensions: set)
        """
        try:
            file_count = 0
            extensions = set()
            
            for file_path in folder_path.rglob("*"):
                if file_path.is_file():
                    file_count += 1
                    extensions.add(file_path.suffix)
                    
                    if file_count >= max_files:
                        logger.warning(
                            f"File limit reached ({max_files}). "
                            "Stopping scan to prevent performance issues."
                        )
                        break
            
            return file_count, extensions
        
        except Exception as e:
            logger.warning(f"Failed to count files: {e}")
            return 0, set()

    def _save_metadata(
        self,
        project_id: str,
        folder_path: str,
        owner: str,
        project_name: str,
        reference_path: Path,
        status: str,
        file_count: int = 0,
        extensions: Optional[set] = None,
        error_message: Optional[str] = None
    ) -> Path:
        """
        Save project metadata as JSON.
        
        Metadata structure (consistent with RepositoryCloner):
        {
            "project_id": "...",
            "source_type": "local_upload",
            "original_path": "...",
            "owner": "...",
            "project_name": "...",
            "clone_path": "...",  (for consistency with repo_clone)
            "uploaded_at": "ISO timestamp",
            "status": "success|failed|exists",
            "error": null or error message,
            "file_count": number,
            "languages": []
        }
        """
        if extensions is None:
            extensions = set()
        
        metadata = {
            "project_id": project_id,
            "source_type": "local_upload",
            "original_path": str(folder_path),
            "owner": owner,
            "project_name": project_name,
            "clone_path": str(reference_path),  # For consistency
            "uploaded_at": datetime.now().isoformat(),
            "status": status,
            "error": error_message,
            "file_count": file_count,
            "languages": sorted(list(extensions))
        }
        
        # Save metadata JSON
        metadata_file = self.metadata_dir / f"{project_id}.json"
        try:
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            logger.info(f"Metadata saved: {metadata_file}")
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
        
        return metadata_file

    def upload_local_project(
        self,
        folder_path: str,
        custom_owner: Optional[str] = None,
        custom_project_name: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Upload and register a local project folder.
        
        Args:
            folder_path: Absolute path to local project folder
            custom_owner: (Optional) Custom owner name. If None, extracted from path.
            custom_project_name: (Optional) Custom project name. If None, extracted from folder name.
        
        Returns:
            Tuple of (success: bool, message: str, metadata: dict|None)
            
        Example:
            success, message, metadata = uploader.upload_local_project(
                r"D:\my-projects\awesome-api"
            )
            
            if success:
                print(f"Uploaded to: {metadata['clone_path']}")
                print(f"Files: {metadata['file_count']}")
                print(f"Languages: {metadata['languages']}")
        """
        
        # Validate folder path
        is_valid, error = self._validate_folder_path(folder_path)
        if not is_valid:
            logger.error(error)
            return False, error, None
        
        folder = Path(folder_path)
        
        # Extract owner and project name
        owner = custom_owner or self._extract_owner_from_path(folder_path)
        project_name = custom_project_name or self._extract_project_name(folder_path)
        
        logger.info(f"Uploading project: {owner}/{project_name}")
        
        # Generate paths and IDs
        reference_path = self._get_upload_reference_path(owner, project_name)
        project_id = self._generate_project_id(owner, project_name)
        
        # Create reference (symlink or path file)
        success, error_msg = self._create_reference_symlink(folder, reference_path)
        if not success:
            self._save_metadata(
                project_id, str(folder), owner, project_name, reference_path,
                status="failed", error_message=error_msg
            )
            return False, error_msg, None
        
        # Count files and extensions
        file_count, extensions = self._count_files_and_extensions(folder)
        
        # Save metadata
        metadata_file = self._save_metadata(
            project_id,
            str(folder),
            owner,
            project_name,
            reference_path,
            status="success",
            file_count=file_count,
            extensions=extensions
        )
        
        success_msg = (
            f"Successfully uploaded {owner}/{project_name} "
            f"({file_count} files, {len(extensions)} file types)"
        )
        logger.info(success_msg)
        
        # Return metadata
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        return True, success_msg, metadata

    def list_uploaded_projects(self) -> list[Dict]:
        """
        List all uploaded projects and their metadata.
        
        Returns:
            List of metadata dictionaries
        """
        projects = []
        
        try:
            for metadata_file in self.metadata_dir.glob("*.json"):
                try:
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        project_meta = json.load(f)
                        # Only include local uploads (not GitHub clones)
                        if project_meta.get("source_type") == "local_upload":
                            projects.append(project_meta)
                except Exception as e:
                    logger.warning(f"Failed to read metadata file {metadata_file}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
        
        return projects

    def get_project_metadata(self, project_id: str) -> Optional[Dict]:
        """
        Retrieve metadata for a specific project.
        
        Args:
            project_id: Project ID
        
        Returns:
            Metadata dictionary or None if not found
        """
        metadata_file = self.metadata_dir / f"{project_id}.json"
        
        if not metadata_file.exists():
            logger.warning(f"Metadata file not found for project_id: {project_id}")
            return None
        
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read metadata: {e}")
            return None

    def get_project_files(
        self,
        project_id: str,
        filter_extension: Optional[str] = None
    ) -> Optional[list]:
        """
        Get list of files in an uploaded project.
        
        Args:
            project_id: Project ID
            filter_extension: (Optional) Filter by file extension (e.g., ".py")
        
        Returns:
            List of file paths or None if project not found
            
        Example:
            files = uploader.get_project_files("mk_awesome-api_20250101_120000")
            py_files = uploader.get_project_files(
                "mk_awesome-api_20250101_120000",
                filter_extension=".py"
            )
        """
        
        # Get metadata
        metadata = self.get_project_metadata(project_id)
        if not metadata:
            logger.error(f"Project not found: {project_id}")
            return None
        
        project_path = Path(metadata["original_path"])
        
        if not project_path.exists():
            logger.error(f"Project path no longer exists: {project_path}")
            return None
        
        try:
            files = []
            for file_path in project_path.rglob("*"):
                if file_path.is_file():
                    # Filter by extension if specified
                    if filter_extension:
                        if file_path.suffix.lower() == filter_extension.lower():
                            files.append(str(file_path))
                    else:
                        files.append(str(file_path))
            
            return sorted(files)
        
        except Exception as e:
            logger.error(f"Failed to get project files: {e}")
            return None

    # ------------------------------------------------------------------
    # NEW: folder path input and file selection
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_path_input(raw_path: str) -> str:
        """Remove spaces and quotes (Windows 'Copy as path' adds quotes)."""
        return raw_path.strip().strip('"').strip("'").strip()

    def ask_for_folder_path(self) -> Optional[str]:
        """
        Ask the user for a folder path until a valid one is entered.
        
        Returns:
            Absolute folder path, or None if the user types q to quit
        """
        while True:
            raw_path = input("Enter folder path (or q to quit): ")
            folder_path = self._clean_path_input(raw_path)

            if folder_path.lower() == "q":
                return None

            # Empty input would become "." (current folder), so block it
            if not folder_path:
                print("Please enter a folder path.")
                continue

            # A drive root like D:\ has no project name, so don't accept it
            folder = Path(folder_path)
            if folder.parent == folder:
                print("Please enter a project folder, not a drive root.")
                continue

            is_valid, error = self._validate_folder_path(folder_path)
            if not is_valid:
                print(error)
                continue

            return os.path.abspath(folder_path)

    def list_folder_contents(self, folder_path: str) -> Optional[list]:
        """
        Read the items directly inside a folder (folders first, then files).
        
        Returns:
            List of Path objects, or None if the folder can't be read
        """
        try:
            items = list(Path(folder_path).iterdir())
            items.sort(key=lambda item: (item.is_file(), item.name.lower()))
            return items
        except OSError as e:
            logger.error(f"Failed to read folder {folder_path}: {e}")
            return None

    def select_file_from_folder(self, folder_path: str) -> Optional[str]:
        """
        Show the contents of a folder and let the user pick a file by number.
        Picking a folder opens it. 0 goes back up, q quits.
        
        Returns:
            Full path of the selected file, or None if the user quits
        """
        start_folder = Path(folder_path)
        current_folder = start_folder

        while True:
            items = self.list_folder_contents(str(current_folder))

            if items is None:
                print(f"Could not read folder: {current_folder}")
                if current_folder == start_folder:
                    return None
                current_folder = current_folder.parent
                continue

            print(f"\nFolder: {current_folder.name or current_folder}\n")
            if not items:
                print("(empty folder)")
            for number, item in enumerate(items, start=1):
                suffix = "/" if item.is_dir() else ""
                print(f"{number}. {item.name}{suffix}")

            choice = input("\nSelect a number (0 = go back, q = quit): ").strip()

            if choice.lower() == "q":
                return None

            if choice == "0":
                if current_folder == start_folder:
                    print("Already at the top folder.")
                else:
                    current_folder = current_folder.parent
                continue

            if not choice.isdigit() or not 1 <= int(choice) <= len(items):
                print("Invalid choice. Enter a number from the list.")
                continue

            selected = items[int(choice) - 1]

            if selected.is_dir():
                current_folder = selected
            elif selected.is_file():
                return str(selected)
            else:
                print(f"File not found (it may have been moved): {selected}")


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Initialize uploader
    uploader = LocalProjectUploader()
    
    # Ask the user for the project folder (replaces the hardcoded path)
    local_path = uploader.ask_for_folder_path()
    if local_path is None:
        raise SystemExit("No folder given. Exiting.")
    
    success, message, metadata = uploader.upload_local_project(local_path)
    
    print(f"Success: {success}")
    print(f"Message: {message}")
    
    if metadata:
        print(f"\nMetadata:")
        print(json.dumps(metadata, indent=2, ensure_ascii=False))
        
        print(f"\nProject Details:")
        print(f"  Source Type: {metadata['source_type']}")
        print(f"  Original Path: {metadata['original_path']}")
        print(f"  Reference Path: {metadata['clone_path']}")
        print(f"  File Count: {metadata['file_count']}")
        print(f"  Languages: {metadata['languages']}")
        
        # Get files from uploaded project
        print(f"\nGetting project files...")
        project_id = metadata['project_id']
        all_files = uploader.get_project_files(project_id)
        
        if all_files:
            print(f"Total files: {len(all_files)}")
            print(f"First 5 files:")
            for file_path in all_files[:5]:
                print(f"  - {file_path}")
        
        # Get only Python files
        py_files = uploader.get_project_files(project_id, filter_extension=".py")
        if py_files:
            print(f"\nPython files: {len(py_files)}")
            for py_file in py_files[:3]:
                print(f"  - {py_file}")
    
    # Let the user pick a file to send to the code reviewer
    selected_file = uploader.select_file_from_folder(local_path)
    if selected_file:
        print(f"\nSelected file: {selected_file}")
        # selected_file is what you pass to the code review module
    else:
        print("\nNo file selected.")
    
    # List all uploaded projects
    print("\n" + "="*60)
    print("All uploaded projects:")
    all_projects = uploader.list_uploaded_projects()
    for project in all_projects:
        print(
            f"  - {project['owner']}/{project['project_name']} "
            f"({project['file_count']} files, {project['status']})"
        )