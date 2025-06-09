"""Core static site generator functionality."""

import shutil
from pathlib import Path
from typing import Dict, List, Any, Set, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime, date
import logging

from .resources import ResourceLoader
from .config import ConfigLoader
from .content import ContentProcessor
from .formats import FormatGenerator
from .cache import BuildCache, CacheCorruptionError

logger = logging.getLogger(__name__)


def check_dependencies() -> None:
    """Check that all required dependencies are available."""
    try:
        import pypandoc
        pypandoc.get_pandoc_version()
    except OSError:
        raise RuntimeError(
            "Pandoc is required but not installed.\n"
            "Please install from: https://pandoc.org/installing.html"
        )
    except Exception as e:
        raise RuntimeError(f"Error checking pandoc installation: {e}")


class Site:
    """Represents a static site with its configuration and structure."""
    
    def __init__(self, root_path: Path):
        self.root = root_path
        
        # Initialize configuration
        config_loader = ConfigLoader(root_path)
        self.config = config_loader.load_config()
        
        # Set up directories
        self.content_dir = self.root / "content"
        self.templates_dir = self.root / "templates"
        self.static_dir = self.root / "static"
        self.output_dir = self.root / self.config.get("output_dir", "_site")
        
        # Initialize Jinja2 environment
        # Add both site templates and package templates
        template_paths = [str(self.templates_dir)]
        
        # Add package templates as fallback (formats and CSS)
        package_templates_dir = Path(__file__).parent / "templates"
        if package_templates_dir.exists():
            template_paths.append(str(package_templates_dir))
        
        self.env = Environment(
            loader=FileSystemLoader(template_paths),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Initialize processors
        self.content_processor = ContentProcessor(self.content_dir)
        self.format_generator = FormatGenerator(self.env, self.config)
        
    
    def build(self, incremental: bool = True, clean: bool = False, show_stats: bool = False) -> Dict[str, Any]:
        """Build the entire site with optional incremental building.
        
        Args:
            incremental: Use incremental building if True
            clean: Force clean rebuild (removes cache)
            show_stats: Return build statistics
            
        Returns:
            Build statistics if show_stats=True, otherwise empty dict
        """
        stats = {
            "total_files": 0,
            "rebuilt_files": 0,
            "cached_files": 0,
            "start_time": datetime.now(),
            "cache_enabled": incremental and not clean
        }
        
        if clean or not incremental:
            return self._full_build(stats, show_stats)
        else:
            try:
                return self._incremental_build(stats, show_stats)
            except (CacheCorruptionError, Exception) as e:
                logger.warning(f"Incremental build failed: {e}. Falling back to full rebuild.")
                return self._full_build(stats, show_stats)
    
    def _full_build(self, stats: Dict[str, Any], show_stats: bool) -> Dict[str, Any]:
        """Perform a full rebuild of the site."""
        # Clean output directory
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True)
        
        # Copy static files first (but we'll override CSS)
        if self.static_dir.exists():
            shutil.copytree(self.static_dir, self.output_dir / "static")
        
        # Process CSS with priority system (may override copied CSS)
        self._process_css()
        
        # Get output formats from config (default to HTML only)
        output_formats = self.config.get('output_formats', ['html'])
        
        # Process content files
        pages = []
        posts = []
        
        for content_file in self.content_dir.rglob("*.md"):
            stats["total_files"] += 1
            stats["rebuilt_files"] += 1
            
            page_data = self.content_processor.process_content(content_file)
            
            # Determine output path base
            relative_path = content_file.relative_to(self.content_dir)
            if relative_path.parts[0] == "posts":
                posts.append(page_data)
                # Remove the 'posts' part since we want posts/<filename>, not posts/posts/<filename>
                post_relative = Path(*relative_path.parts[1:])
                output_base = self.output_dir / "posts" / post_relative.with_suffix('')
            else:
                pages.append(page_data)
                output_base = self.output_dir / relative_path.with_suffix('')
            
            # Generate files for each output format
            for fmt in output_formats:
                if fmt == 'html':
                    # Use existing HTML rendering with templates
                    html = self._render_page(page_data)
                    output_path = output_base.with_suffix('.html')
                    # Ensure directory exists
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(html)
                else:
                    # Use format generator for other formats
                    self.format_generator.generate_format(
                        page_data, content_file, output_base, fmt, self.content_processor
                    )
        
        # Generate index page
        self._generate_index(posts, pages)
        stats["rebuilt_files"] += 1  # Count index page
        
        if show_stats:
            stats["end_time"] = datetime.now()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            return stats
        return {}
    
    def _incremental_build(self, stats: Dict[str, Any], show_stats: bool) -> Dict[str, Any]:
        """Perform an incremental rebuild of the site."""
        # Initialize cache
        cache_dir = self.root / '.ctxssg-cache'
        cache = BuildCache(cache_dir)
        
        # Update template dependencies
        cache.update_template_dependencies(self.templates_dir)
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all content files
        content_files = set(self.content_dir.rglob("*.md"))
        stats["total_files"] = len(content_files)
        
        # Determine which files need rebuilding
        changed_files = cache.get_changed_files(content_files)
        
        # Add template changes to changed files
        for template_file in self.templates_dir.rglob("*.html"):
            if cache.is_file_changed(template_file):
                changed_files.add(template_file)
        
        # Get all affected files (including dependencies)
        affected_files = cache.get_affected_files(changed_files, self.templates_dir)
        
        # Filter to only content files for rebuilding
        affected_content = {f for f in affected_files if f.suffix == '.md' and f in content_files}
        
        # Clean orphaned outputs
        orphaned_outputs = cache.get_orphaned_outputs(content_files)
        for orphaned_file in orphaned_outputs:
            if orphaned_file.exists():
                orphaned_file.unlink()
                logger.debug(f"Removed orphaned output: {orphaned_file}")
        
        # Handle static files and CSS
        self._process_static_incremental(cache)
        
        # Get output formats from config
        output_formats = self.config.get('output_formats', ['html'])
        
        # Process affected content files
        pages = []
        posts = []
        
        for content_file in content_files:
            if content_file in affected_content:
                # Rebuild this file
                stats["rebuilt_files"] += 1
                page_data = self._process_content_file_cached(content_file, cache, output_formats)
            else:
                # Use cached data if available
                stats["cached_files"] += 1
                page_data = self._get_cached_content_data(content_file, cache)
                if page_data is None:
                    # Cache miss - rebuild
                    stats["rebuilt_files"] += 1
                    stats["cached_files"] -= 1
                    page_data = self._process_content_file_cached(content_file, cache, output_formats)
            
            # Collect for index generation
            relative_path = content_file.relative_to(self.content_dir)
            if relative_path.parts[0] == "posts":
                posts.append(page_data)
            else:
                pages.append(page_data)
        
        # Always regenerate index (for now - could be optimized)
        self._generate_index(posts, pages)
        stats["rebuilt_files"] += 1
        
        if show_stats:
            stats["end_time"] = datetime.now()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            cache_hit_rate = (stats["cached_files"] / stats["total_files"] * 100) if stats["total_files"] > 0 else 0
            stats["cache_hit_rate"] = cache_hit_rate
            return stats
        return {}
    
    def _generate_format(self, page_data: Dict[str, Any], source_file: Path, output_base: Path, fmt: str) -> None:
        """Generate output file for a specific format - wrapper for CLI compatibility."""
        if fmt == 'html':
            # Use existing HTML rendering with templates
            html = self._render_page(page_data)
            output_path = output_base.with_suffix('.html')
            # Ensure directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html)
        else:
            # Use format generator for other formats
            self.format_generator.generate_format(
                page_data, source_file, output_base, fmt, self.content_processor
            )
    
    def _process_content(self, file_path: Path) -> Dict[str, Any]:
        """Process a markdown file with frontmatter - wrapper for CLI compatibility."""
        return self.content_processor.process_content(file_path)
    
    def _render_page(self, page_data: Dict[str, Any]) -> str:
        """Render a page using Jinja2 templates."""
        layout = page_data.get('layout', 'default')
        template = self.env.get_template(f"{layout}.html")
        
        # Build context
        context = {
            'site': self.config,
            'page': page_data,
        }
        
        return template.render(**context)
    
    def _generate_index(self, posts: List[Dict[str, Any]], pages: List[Dict[str, Any]]) -> None:
        """Generate the index page."""
        # Sort posts by date (newest first)
        # Normalize all dates to datetime objects for consistent comparison
        def get_sort_date(post):
            post_date = post.get('date')
            if post_date is None:
                return datetime.min
            elif isinstance(post_date, date) and not isinstance(post_date, datetime):
                # Convert date to datetime (at start of day)
                return datetime.combine(post_date, datetime.min.time())
            elif isinstance(post_date, datetime):
                return post_date
            else:
                # Fallback for unexpected types
                return datetime.min
                
        posts.sort(key=get_sort_date, reverse=True)
        
        index_data = {
            'title': self.config.get('title', 'Home'),
            'layout': 'index',
            'posts': posts[:10],  # Show latest 10 posts
            'pages': pages,
        }
        
        html = self._render_page(index_data)
        (self.output_dir / 'index.html').write_text(html)
    
    def _process_css(self) -> None:
        """Simple CSS processing: user CSS > default CSS."""
        css_output_dir = self.output_dir / "static" / "css"
        css_output_dir.mkdir(parents=True, exist_ok=True)
        output_css_path = css_output_dir / "style.css"
        
        # Priority 1: User's CSS file (if it exists)
        user_css_path = self.static_dir / "css" / "style.css"
        if user_css_path.exists():
            shutil.copy2(user_css_path, output_css_path)
            return
        
        # Priority 2: Use default CSS
        self._use_default_css(output_css_path)
    
    def _use_default_css(self, output_path: Path) -> None:
        """Use the enhanced default CSS as fallback."""
        loader = ResourceLoader()
        
        # Try to load from package assets
        if loader.copy_resource('assets/css/default.css', output_path):
            return
        
        # Fallback to basic CSS if default.css is missing
        self._create_fallback_css(output_path)
    
    def _create_fallback_css(self, output_path: Path) -> None:
        """Create a basic fallback CSS if all else fails."""
        basic_css = '''/* Basic fallback CSS for ctxssg */
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6;
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem 1rem;
    color: #333;
}

h1, h2, h3, h4, h5, h6 {
    margin-top: 2rem;
    margin-bottom: 1rem;
    line-height: 1.3;
}

a {
    color: #0066cc;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

pre {
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 4px;
    padding: 1rem;
    overflow-x: auto;
}

code {
    font-family: monospace;
    background: #f8f9fa;
    padding: 0.2em 0.4em;
    border-radius: 3px;
}
'''
        output_path.write_text(basic_css)
    
    def _process_static_incremental(self, cache: BuildCache) -> None:
        """Process static files incrementally."""
        if not self.static_dir.exists():
            return
            
        output_static_dir = self.output_dir / "static"
        output_static_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy changed static files
        for static_file in self.static_dir.rglob("*"):
            if static_file.is_file():
                relative_path = static_file.relative_to(self.static_dir)
                output_path = output_static_dir / relative_path
                
                # Skip CSS files - they're handled separately
                if relative_path.parts[0] == "css" and relative_path.name == "style.css":
                    continue
                    
                # Check if file has changed
                if cache.is_file_changed(static_file):
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(static_file, output_path)
                    logger.debug(f"Copied static file: {relative_path}")
        
        # Process CSS separately
        self._process_css()
        
    def _process_content_file_cached(self, content_file: Path, cache: BuildCache, output_formats: List[str]) -> Dict[str, Any]:
        """Process a content file with caching support."""
        # Get file hash
        file_hash = cache.get_file_hash(content_file)
        
        # Try to get from cache first
        cached_content = cache.get_cached_content(file_hash)
        if cached_content and not self._templates_changed_for_content(cached_content, cache):
            # Cache hit - generate outputs from cached data
            page_data = cached_content
        else:
            # Cache miss or templates changed - process content
            page_data = self.content_processor.process_content(content_file)
            
            # Store template dependencies
            layout = page_data.get('layout', 'default')
            templates_used = self._get_template_chain(layout)
            
            # Cache the processed content
            cache_data = {
                **page_data,
                "templates_used": templates_used
            }
            cache.cache_content(file_hash, cache_data)
        
        # Generate output files
        self._generate_outputs_for_content(content_file, page_data, output_formats, cache)
        
        # Update file info in cache
        output_files = self._get_output_files_for_content(content_file, output_formats)
        cache.update_file_info(
            content_file, 
            file_hash,
            layout=page_data.get('layout', 'default'),
            templates=page_data.get("templates_used", []),
            outputs=[str(f) for f in output_files]
        )
        
        return page_data
        
    def _get_cached_content_data(self, content_file: Path, cache: BuildCache) -> Optional[Dict[str, Any]]:
        """Get cached content data if valid."""
        file_hash = cache.get_file_hash(content_file)
        cached_content = cache.get_cached_content(file_hash)
        
        if cached_content and not self._templates_changed_for_content(cached_content, cache):
            return cached_content
        return None
        
    def _templates_changed_for_content(self, content_data: Dict[str, Any], cache: BuildCache) -> bool:
        """Check if any templates used by this content have changed."""
        templates_used = content_data.get("templates_used", [])
        return cache.is_template_changed(templates_used)
        
    def _get_template_chain(self, layout: str) -> List[str]:
        """Get the full chain of templates used for a layout."""
        templates = []
        current_layout = layout
        
        while current_layout:
            template_name = f"{current_layout}.html"
            templates.append(template_name)
            
            # Check if this template extends another
            try:
                template_path = self.templates_dir / template_name
                if template_path.exists():
                    from .cache import TemplateAnalyzer
                    deps = TemplateAnalyzer.analyze_template(template_path)
                    extends = deps.get("extends", [])
                    current_layout = extends[0].replace('.html', '') if extends else None
                else:
                    break
            except Exception:
                break
                
        return templates
        
    def _generate_outputs_for_content(self, content_file: Path, page_data: Dict[str, Any], output_formats: List[str], cache: BuildCache) -> None:
        """Generate all output files for a piece of content."""
        # Determine output path base
        relative_path = content_file.relative_to(self.content_dir)
        if relative_path.parts[0] == "posts":
            post_relative = Path(*relative_path.parts[1:])
            output_base = self.output_dir / "posts" / post_relative.with_suffix('')
        else:
            output_base = self.output_dir / relative_path.with_suffix('')
        
        # Generate files for each output format
        for fmt in output_formats:
            if fmt == 'html':
                # Use existing HTML rendering with templates
                html = self._render_page(page_data)
                output_path = output_base.with_suffix('.html')
                # Ensure directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(html)
            else:
                # Use format generator for other formats
                self.format_generator.generate_format(
                    page_data, content_file, output_base, fmt, self.content_processor
                )
                
    def _get_output_files_for_content(self, content_file: Path, output_formats: List[str]) -> List[Path]:
        """Get list of output files that would be generated for a content file."""
        relative_path = content_file.relative_to(self.content_dir)
        if relative_path.parts[0] == "posts":
            post_relative = Path(*relative_path.parts[1:])
            output_base = self.output_dir / "posts" / post_relative.with_suffix('')
        else:
            output_base = self.output_dir / relative_path.with_suffix('')
            
        output_files = []
        for fmt in output_formats:
            if fmt == 'html':
                output_files.append(output_base.with_suffix('.html'))
            else:
                # Map format to file extension
                format_extensions = {
                    'plain': '.txt',
                    'json': '.json',
                    'xml': '.xml'
                }
                ext = format_extensions.get(fmt, f'.{fmt}')
                output_files.append(output_base.with_suffix(ext))
                
        return output_files


class SiteGenerator:
    """Main interface for generating static sites."""
    
    @staticmethod
    def init_site(path: Path, title: str = "My Site") -> None:
        """Initialize a new site structure using package resources."""
        loader = ResourceLoader()
        
        # Create directory structure
        (path / "content").mkdir(parents=True, exist_ok=True)
        (path / "content" / "posts").mkdir(exist_ok=True)
        (path / "templates").mkdir(exist_ok=True)
        (path / "static").mkdir(exist_ok=True)
        (path / "static" / "css").mkdir(exist_ok=True)
        (path / "static" / "js").mkdir(exist_ok=True)
        
        # Create config.toml from template
        config_template = loader.load_resource(
            'templates/site/config/config.toml',
            fallback=SiteGenerator._get_fallback_config()
        )
        config_content = loader.format_template(config_template, title=title)
        (path / "config.toml").write_text(config_content)
        
        # Copy HTML templates
        loader.copy_tree('templates/site/html', path / "templates")
        
        # Copy format templates
        formats_dir = path / "templates" / "formats"
        formats_dir.mkdir(exist_ok=True)
        loader.copy_tree('templates/formats', formats_dir)
        
        # Copy sample content
        about_md = loader.load_resource(
            'templates/site/content/about.md',
            fallback=SiteGenerator._get_fallback_about()
        )
        (path / "content" / "about.md").write_text(about_md)
        
        welcome_md = loader.load_resource(
            'templates/site/content/welcome.md',
            fallback=SiteGenerator._get_fallback_welcome()
        )
        (path / "content" / "posts" / "welcome.md").write_text(welcome_md)
        
        # Copy default CSS to static directory
        css_path = path / "static" / "css" / "style.css"
        if not loader.copy_resource('assets/css/default.css', css_path):
            # Fallback CSS if package resource is missing
            SiteGenerator._create_fallback_css(css_path)
    
    @staticmethod
    def _get_fallback_config() -> str:
        """Minimal fallback config if resource loading fails."""
        return '''[site]
title = "{title}"
url = "http://localhost:8000"

[build]
output_dir = "_site"
output_formats = ["html"]'''
    
    @staticmethod
    def _get_fallback_about() -> str:
        """Minimal fallback about page."""
        return '''---
title: About
layout: default
---

# About This Site

This site was generated with ctxssg.'''
    
    @staticmethod
    def _get_fallback_welcome() -> str:
        """Minimal fallback welcome post."""
        return '''---
title: Welcome
date: 2024-01-01
layout: post
---

Welcome to your new site!'''
    
    @staticmethod
    def _create_fallback_css(output_path: Path) -> None:
        """Create basic fallback CSS as last resort."""
        css_content = '''/* Basic fallback CSS for ctxssg */
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6;
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem 1rem;
    color: #333;
}

h1, h2, h3, h4, h5, h6 {
    margin-top: 2rem;
    margin-bottom: 1rem;
    line-height: 1.3;
}

a {
    color: #0066cc;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

pre {
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 4px;
    padding: 1rem;
    overflow-x: auto;
}

code {
    font-family: monospace;
    background: #f8f9fa;
    padding: 0.2em 0.4em;
    border-radius: 3px;
}'''
        output_path.write_text(css_content)
