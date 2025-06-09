"""Build cache system for incremental building."""

import hashlib
import json
import re
import shutil
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import logging

logger = logging.getLogger(__name__)

CACHE_VERSION = 1


class CacheJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for cache data."""
    
    def default(self, obj):
        # Check datetime first since it's a subclass of date
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


def decode_cache_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Decode cached data, converting ISO strings back to date/datetime objects."""
    # Convert date strings back to date/datetime objects
    if 'date' in data and isinstance(data['date'], str):
        try:
            # Try parsing as date first (YYYY-MM-DD format)
            if len(data['date']) == 10 and data['date'].count('-') == 2:
                data['date'] = date.fromisoformat(data['date'])
            else:
                # Parse as datetime
                data['date'] = datetime.fromisoformat(data['date'])
        except ValueError:
            pass  # Keep as string if conversion fails
    
    return data


class TemplateAnalyzer:
    """Analyzes Jinja2 templates to extract dependencies."""
    
    # Regex patterns for Jinja2 template parsing
    EXTENDS_PATTERN = re.compile(r'{%\s*extends\s+["\']([^"\']+)["\']\s*%}')
    INCLUDE_PATTERN = re.compile(r'{%\s*include\s+["\']([^"\']+)["\']\s*%}')
    
    @classmethod
    def analyze_template(cls, template_path: Path) -> Dict[str, List[str]]:
        """Analyze a template file for dependencies.
        
        Args:
            template_path: Path to the template file
            
        Returns:
            Dictionary with 'extends' and 'includes' lists
        """
        if not template_path.exists():
            return {"extends": [], "includes": []}
            
        try:
            content = template_path.read_text(encoding='utf-8')
            
            # Find extends directive (should be only one)
            extends_matches = cls.EXTENDS_PATTERN.findall(content)
            extends = extends_matches[0] if extends_matches else None
            
            # Find include directives (can be multiple)
            includes = cls.INCLUDE_PATTERN.findall(content)
            
            return {
                "extends": [extends] if extends else [],
                "includes": includes
            }
            
        except OSError as e:
            logger.warning(f"Failed to analyze template {template_path}: {e}")
            return {"extends": [], "includes": []}
            
    @classmethod
    def build_dependency_graph(cls, template_dir: Path) -> Dict[str, Dict[str, List[str]]]:
        """Build complete dependency graph for all templates.
        
        Args:
            template_dir: Directory containing templates
            
        Returns:
            Dictionary mapping template names to their dependencies
        """
        dependency_graph = {}
        
        # Find all HTML templates
        for template_path in template_dir.rglob("*.html"):
            template_name = template_path.name
            dependencies = cls.analyze_template(template_path)
            
            dependency_graph[template_name] = {
                "path": str(template_path),
                "extends": dependencies["extends"],
                "includes": dependencies["includes"],
                "extended_by": [],  # Will be populated below
                "included_by": []   # Will be populated below
            }
            
        # Build reverse relationships
        for template_name, info in dependency_graph.items():
            # For extends relationships
            for extended_template in info["extends"]:
                if extended_template in dependency_graph:
                    dependency_graph[extended_template]["extended_by"].append(template_name)
                    
            # For include relationships  
            for included_template in info["includes"]:
                if included_template in dependency_graph:
                    dependency_graph[included_template]["included_by"].append(template_name)
                    
        return dependency_graph


class CacheCorruptionError(Exception):
    """Raised when cache data is corrupted or invalid."""
    pass


class BuildCache:
    """Manages the build cache for incremental building.
    
    The cache tracks file hashes, dependencies, and output mappings to enable
    intelligent incremental rebuilds that only process changed files and their
    dependencies.
    """
    
    def __init__(self, cache_dir: Path, max_memory_cache_mb: int = 50):
        self.cache_dir = Path(cache_dir)
        self.max_memory_cache_mb = max_memory_cache_mb
        self.manifest_file = self.cache_dir / "manifest.json"
        
        # Initialize cache directory structure
        self._init_cache_dir()
        
        # Load manifest (lightweight - kept in memory)
        self.manifest = self._load_manifest()
        
        # In-memory LRU cache for content (heavy data loaded on-demand)
        self._content_cache: Dict[str, Dict[str, Any]] = {}
        self._content_cache_size = 0  # Track memory usage
        
        # Template dependency graph (loaded on demand)
        self._template_graph: Optional[Dict[str, Dict[str, List[str]]]] = None
        
    def _init_cache_dir(self) -> None:
        """Initialize cache directory structure."""
        self.cache_dir.mkdir(exist_ok=True)
        (self.cache_dir / "content").mkdir(exist_ok=True)
        (self.cache_dir / "conversions").mkdir(exist_ok=True)
        
    def _load_manifest(self) -> Dict[str, Any]:
        """Load the build manifest from disk."""
        if not self.manifest_file.exists():
            return self._create_empty_manifest()
            
        try:
            with open(self.manifest_file, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
                
            # Validate manifest version
            if manifest.get('version') != CACHE_VERSION:
                logger.warning(f"Cache version mismatch. Expected {CACHE_VERSION}, got {manifest.get('version')}. Clearing cache.")
                return self._create_empty_manifest()
                
            return manifest
            
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load cache manifest: {e}. Creating new cache.")
            return self._create_empty_manifest()
            
    def _create_empty_manifest(self) -> Dict[str, Any]:
        """Create an empty manifest structure."""
        return {
            "version": CACHE_VERSION,
            "last_build": None,
            "files": {},
            "templates": {}
        }
        
    def _save_manifest(self) -> None:
        """Save the manifest to disk atomically."""
        try:
            # Write to temporary file first for atomic operation
            temp_file = self.manifest_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.manifest, f, indent=2, separators=(',', ': '), cls=CacheJSONEncoder)
            
            # Atomic move
            temp_file.replace(self.manifest_file)
            
        except OSError as e:
            logger.error(f"Failed to save cache manifest: {e}")
            
    def get_file_hash(self, file_path: Path) -> str:
        """Compute content-based hash for a file.
        
        Args:
            file_path: Path to the file to hash
            
        Returns:
            16-character hex hash of file content
        """
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            return hashlib.sha256(content).hexdigest()[:16]
        except OSError as e:
            logger.error(f"Failed to hash file {file_path}: {e}")
            raise
            
    def is_file_changed(self, file_path: Path) -> bool:
        """Check if a file has changed since last build.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file has changed or is new, False if unchanged
        """
        if not file_path.exists():
            return True
            
        file_key = str(file_path)
        if file_key not in self.manifest["files"]:
            return True
            
        current_hash = self.get_file_hash(file_path)
        cached_hash = self.manifest["files"][file_key].get("hash")
        
        return current_hash != cached_hash
        
    def get_cached_content(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached content using lazy loading.
        
        Args:
            file_hash: Hash of the content to retrieve
            
        Returns:
            Cached content data or None if not found
        """
        # Check in-memory cache first
        if file_hash in self._content_cache:
            return self._content_cache[file_hash]
            
        # Load from disk
        cache_file = self.cache_dir / "content" / f"{file_hash}.json"
        if not cache_file.exists():
            return None
            
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
                
            # Decode datetime objects
            content = decode_cache_data(content)
                
            # Add to memory cache (with size management)
            self._add_to_memory_cache(file_hash, content)
            
            return content
            
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load cached content {file_hash}: {e}")
            return None
            
    def cache_content(self, file_hash: str, content: Dict[str, Any]) -> None:
        """Store processed content in cache.
        
        Args:
            file_hash: Hash key for the content
            content: Content data to cache
        """
        # Ensure content has version
        content["version"] = CACHE_VERSION
        content["cached_at"] = time.time()
        
        # Save to disk
        cache_file = self.cache_dir / "content" / f"{file_hash}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, separators=(',', ': '), cls=CacheJSONEncoder)
                
            # Add to memory cache
            self._add_to_memory_cache(file_hash, content)
            
        except (OSError, TypeError) as e:
            logger.error(f"Failed to cache content {file_hash}: {e}")
            # Log the problematic content for debugging
            if isinstance(e, TypeError):
                logger.debug(f"Content that failed serialization: {type(content)} - {content}")
            
    def _add_to_memory_cache(self, file_hash: str, content: Dict[str, Any]) -> None:
        """Add content to in-memory cache with size management."""
        # Estimate content size (rough approximation)
        content_size = len(json.dumps(content, cls=CacheJSONEncoder)) / (1024 * 1024)  # MB
        
        # Simple LRU: remove oldest if we exceed memory limit
        while (self._content_cache_size + content_size > self.max_memory_cache_mb and 
               self._content_cache):
            # Remove oldest entry (first in dict)
            oldest_hash = next(iter(self._content_cache))
            old_content = self._content_cache.pop(oldest_hash)
            old_size = len(json.dumps(old_content, cls=CacheJSONEncoder)) / (1024 * 1024)
            self._content_cache_size -= old_size
            
        # Add new content
        self._content_cache[file_hash] = content
        self._content_cache_size += content_size
        
    def update_file_info(self, file_path: Path, file_hash: str, **kwargs) -> None:
        """Update file information in the manifest.
        
        Args:
            file_path: Path to the file
            file_hash: Content hash
            **kwargs: Additional metadata (layout, templates, outputs, etc.)
        """
        file_key = str(file_path)
        
        file_info = {
            "hash": file_hash,
            "last_built": time.time(),
            **kwargs
        }
        
        self.manifest["files"][file_key] = file_info
        self._save_manifest()
        
    def get_dependencies(self, file_path: Path) -> List[str]:
        """Get template dependencies for a file.
        
        Args:
            file_path: Path to the content file
            
        Returns:
            List of template names this file depends on
        """
        file_key = str(file_path)
        file_info = self.manifest["files"].get(file_key, {})
        return file_info.get("templates", [])
        
    def update_template_dependencies(self, template_dir: Path) -> None:
        """Update template dependency information.
        
        Args:
            template_dir: Directory containing templates
        """
        logger.debug(f"Updating template dependencies from {template_dir}")
        
        # Build dependency graph
        dependency_graph = TemplateAnalyzer.build_dependency_graph(template_dir)
        
        # Update manifest with template information
        for template_name, info in dependency_graph.items():
            template_path = Path(info["path"])
            if template_path.exists():
                template_hash = self.get_file_hash(template_path)
                self.manifest["templates"][template_name] = {
                    "hash": template_hash,
                    "path": str(template_path),
                    "extends": info["extends"],
                    "includes": info["includes"],
                    "extended_by": info["extended_by"],
                    "included_by": info["included_by"]
                }
                
        # Cache the dependency graph
        self._template_graph = dependency_graph
        self._save_manifest()
        
    def get_template_graph(self, template_dir: Path = None) -> Dict[str, Dict[str, List[str]]]:
        """Get the template dependency graph.
        
        Args:
            template_dir: Directory to analyze if graph needs rebuilding
            
        Returns:
            Template dependency graph
        """
        if self._template_graph is None and template_dir:
            self.update_template_dependencies(template_dir)
            
        return self._template_graph or {}
        
    def track_template(self, template_path: Path, includes: List[str] = None, 
                       extended_by: List[str] = None) -> None:
        """Track template dependencies.
        
        Args:
            template_path: Path to the template
            includes: List of templates this template includes
            extended_by: List of templates that extend this template
        """
        template_key = str(template_path)
        template_hash = self.get_file_hash(template_path)
        
        self.manifest["templates"][template_key] = {
            "hash": template_hash,
            "includes": includes or [],
            "extended_by": extended_by or []
        }
        
        self._save_manifest()
        
    def get_template_dependents(self, template_path: Path) -> Set[Path]:
        """Find all content files that depend on a template.
        
        Args:
            template_path: Path to the changed template
            
        Returns:
            Set of content file paths that need rebuilding
        """
        template_name = template_path.name
        dependents = set()
        
        # Find content files that use this template directly
        for file_path_str, file_info in self.manifest["files"].items():
            templates = file_info.get("templates", [])
            if template_name in templates:
                dependents.add(Path(file_path_str))
        
        # Find all templates that depend on this template (transitive)
        affected_templates = self._get_all_template_dependents(template_name)
        
        # Find content files that use any of the affected templates
        for affected_template in affected_templates:
            for file_path_str, file_info in self.manifest["files"].items():
                templates = file_info.get("templates", [])
                if affected_template in templates:
                    dependents.add(Path(file_path_str))
                    
        return dependents
        
    def _get_all_template_dependents(self, template_name: str, visited: Set[str] = None) -> Set[str]:
        """Get all templates that transitively depend on the given template.
        
        Args:
            template_name: Name of the template
            visited: Set of already visited templates (for cycle detection)
            
        Returns:
            Set of template names that depend on this template
        """
        if visited is None:
            visited = set()
            
        if template_name in visited:
            return set()  # Avoid cycles
            
        visited.add(template_name)
        dependents = set()
        
        # Check manifest for template dependencies
        if template_name in self.manifest["templates"]:
            template_info = self.manifest["templates"][template_name]
            
            # Templates that extend this template
            extended_by = template_info.get("extended_by", [])
            dependents.update(extended_by)
            
            # Templates that include this template
            included_by = template_info.get("included_by", [])
            dependents.update(included_by)
            
            # Recursively find dependents of dependents
            for dependent in list(dependents):
                dependents.update(self._get_all_template_dependents(dependent, visited.copy()))
                
        return dependents
        
    def track_output(self, source_file: Path, output_files: List[Path]) -> None:
        """Track output files for cleanup.
        
        Args:
            source_file: Source file that generated the outputs
            output_files: List of generated output files
        """
        file_key = str(source_file)
        if file_key in self.manifest["files"]:
            self.manifest["files"][file_key]["outputs"] = [str(f) for f in output_files]
            self._save_manifest()
            
    def get_orphaned_outputs(self, all_source_files: Set[Path]) -> List[Path]:
        """Find output files whose source no longer exists.
        
        Args:
            all_source_files: Set of all current source files
            
        Returns:
            List of orphaned output file paths
        """
        orphaned = []
        source_files_str = {str(f) for f in all_source_files}
        
        for file_path_str, file_info in self.manifest["files"].items():
            if file_path_str not in source_files_str:
                # Source file no longer exists, outputs are orphaned
                outputs = file_info.get("outputs", [])
                orphaned.extend(Path(output) for output in outputs)
                
        return orphaned
        
    def remove_file(self, file_path: Path) -> None:
        """Remove a file from the cache.
        
        Args:
            file_path: Path of the file to remove
        """
        file_key = str(file_path)
        if file_key in self.manifest["files"]:
            file_info = self.manifest["files"][file_key]
            
            # Remove cached content if it exists
            file_hash = file_info.get("hash")
            if file_hash:
                cache_file = self.cache_dir / "content" / f"{file_hash}.json"
                if cache_file.exists():
                    cache_file.unlink()
                    
                # Remove from memory cache
                self._content_cache.pop(file_hash, None)
                
            # Remove from manifest
            del self.manifest["files"][file_key]
            self._save_manifest()
            
    def get_changed_files(self, source_files: Set[Path]) -> Set[Path]:
        """Get all files that have changed since last build.
        
        Args:
            source_files: Set of all current source files
            
        Returns:
            Set of changed file paths
        """
        changed = set()
        
        for file_path in source_files:
            if self.is_file_changed(file_path):
                changed.add(file_path)
                
        return changed
        
    def get_affected_files(self, changed_files: Set[Path], template_dir: Path = None) -> Set[Path]:
        """Get all files affected by changes (including dependencies).
        
        Args:
            changed_files: Set of files that have changed
            template_dir: Template directory for dependency analysis
            
        Returns:
            Set of all files that need rebuilding
        """
        affected = set(changed_files)
        
        for changed_file in changed_files:
            if changed_file.suffix == '.html' and 'templates' in str(changed_file):
                # Template changed - find all dependent content
                affected.update(self.get_template_dependents(changed_file))
            elif changed_file.name in ('config.toml', 'config.yaml'):
                # Config changed - rebuild everything
                return set(self.manifest["files"].keys())
                
        return affected
        
    def is_template_changed(self, template_names: List[str]) -> bool:
        """Check if any of the given templates have changed.
        
        Args:
            template_names: List of template names to check
            
        Returns:
            True if any template has changed
        """
        for template_name in template_names:
            if template_name in self.manifest["templates"]:
                template_info = self.manifest["templates"][template_name]
                template_path = Path(template_info["path"])
                
                if template_path.exists():
                    current_hash = self.get_file_hash(template_path)
                    cached_hash = template_info.get("hash")
                    
                    if current_hash != cached_hash:
                        return True
                else:
                    # Template no longer exists
                    return True
                    
        return False
        
    def clean_old_entries(self, max_age_days: int = 30) -> int:
        """Clean cache entries older than specified age.
        
        Args:
            max_age_days: Maximum age in days before cleanup
            
        Returns:
            Number of entries cleaned
        """
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        cleaned_count = 0
        
        # Clean file entries
        files_to_remove = []
        for file_path_str, file_info in self.manifest["files"].items():
            last_built = file_info.get("last_built", 0)
            if last_built < cutoff_time:
                files_to_remove.append(file_path_str)
                
        for file_path_str in files_to_remove:
            self.remove_file(Path(file_path_str))
            cleaned_count += 1
            
        # Clean orphaned cache files
        content_dir = self.cache_dir / "content"
        if content_dir.exists():
            all_hashes = {info.get("hash") for info in self.manifest["files"].values()}
            all_hashes.discard(None)
            
            for cache_file in content_dir.glob("*.json"):
                file_hash = cache_file.stem
                if file_hash not in all_hashes:
                    cache_file.unlink()
                    cleaned_count += 1
                    
        self._save_manifest()
        return cleaned_count
        
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        stats = {
            "version": CACHE_VERSION,
            "files_tracked": len(self.manifest["files"]),
            "templates_tracked": len(self.manifest["templates"]),
            "memory_cache_size_mb": self._content_cache_size,
            "memory_cache_entries": len(self._content_cache),
            "last_build": self.manifest.get("last_build")
        }
        
        # Calculate disk usage
        total_size = 0
        if self.cache_dir.exists():
            for file_path in self.cache_dir.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    
        stats["disk_cache_size_mb"] = total_size / (1024 * 1024)
        
        return stats
        
    def clear(self) -> None:
        """Clear all cache data."""
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            
        self._init_cache_dir()
        self.manifest = self._create_empty_manifest()
        self._content_cache.clear()
        self._content_cache_size = 0
        
    def validate(self) -> bool:
        """Validate cache integrity.
        
        Returns:
            True if cache is valid, False if corrupted
        """
        try:
            # Check version
            if self.manifest.get("version") != CACHE_VERSION:
                return False
                
            # Check directory structure
            required_dirs = ["content", "conversions"]
            for dir_name in required_dirs:
                if not (self.cache_dir / dir_name).exists():
                    return False
                    
            # Check manifest structure
            required_keys = ["version", "files", "templates"]
            for key in required_keys:
                if key not in self.manifest:
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Cache validation failed: {e}")
            return False