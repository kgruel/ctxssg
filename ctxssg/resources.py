"""Resource loading and management for ctxssg."""

import shutil
from pathlib import Path
from typing import List


class ResourceLoader:
    """Smart resource loading with fallback handling for package resources."""
    
    def __init__(self, package_name: str = 'ctxssg'):
        self.package = package_name
        self.package_path = Path(__file__).parent
        
    def load_resource(self, resource_path: str, fallback: str = '') -> str:
        """Load a resource file from the package with optional fallback."""
        full_path = self.package_path / resource_path
        
        if full_path.exists():
            try:
                return full_path.read_text(encoding='utf-8')
            except Exception as e:
                if fallback:
                    return fallback
                raise RuntimeError(f"Failed to read resource {resource_path}: {e}")
        elif fallback:
            return fallback
        else:
            raise FileNotFoundError(f"Resource not found: {resource_path}")
    
    def resource_exists(self, resource_path: str) -> bool:
        """Check if a resource exists in the package."""
        return (self.package_path / resource_path).exists()
    
    def copy_resource(self, resource_path: str, destination: Path, 
                     overwrite: bool = False) -> bool:
        """Copy a single resource file to destination."""
        source_path = self.package_path / resource_path
        
        if not source_path.exists():
            return False
            
        if destination.exists() and not overwrite:
            return False
            
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
            return True
        except Exception:
            return False
    
    def copy_tree(self, source_dir: str, destination: Path, 
                  overwrite: bool = False) -> List[Path]:
        """Copy a directory tree from package resources."""
        source_path = self.package_path / source_dir
        copied_files: List[Path] = []
        
        if not source_path.exists() or not source_path.is_dir():
            return copied_files
            
        for source_file in source_path.rglob('*'):
            if source_file.is_file():
                relative_path = source_file.relative_to(source_path)
                dest_file = destination / relative_path
                
                if not dest_file.exists() or overwrite:
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_file, dest_file)
                    copied_files.append(dest_file)
                    
        return copied_files
        
    def format_template(self, template_content: str, **kwargs) -> str:
        """Format a template string with the provided kwargs."""
        try:
            return template_content.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")