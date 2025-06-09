"""Core static site generator functionality."""

import shutil
from pathlib import Path
from typing import Dict, List, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime

from .resources import ResourceLoader
from .config import ConfigLoader
from .content import ContentProcessor
from .formats import FormatGenerator


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
        
    
    def build(self) -> None:
        """Build the entire site."""
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
        posts.sort(key=lambda x: x.get('date', datetime.min), reverse=True)
        
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
