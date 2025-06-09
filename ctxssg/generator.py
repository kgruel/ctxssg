"""Core static site generator functionality."""

import shutil
from pathlib import Path
from typing import Dict, List, Any
import yaml
import frontmatter
from jinja2 import Environment, FileSystemLoader, select_autoescape
import pypandoc
from datetime import datetime
import re
from bs4 import BeautifulSoup
import sys

# TOML support for configuration
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


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
        copied_files = []
        
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


class Site:
    """Represents a static site with its configuration and structure."""
    
    def __init__(self, root_path: Path):
        self.root = root_path
        self.config = self._load_config()
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
        
    def _load_config(self) -> Dict[str, Any]:
        """Load site configuration from config.toml or config.yaml."""
        # Try TOML first (preferred), then YAML for backward compatibility
        toml_path = self.root / "config.toml"
        yaml_path = self.root / "config.yaml"
        
        if toml_path.exists():
            with open(toml_path, 'rb') as f:
                config = tomllib.load(f)
                return self._normalize_config(config)
        elif yaml_path.exists():
            with open(yaml_path, 'r') as f:
                config = yaml.safe_load(f) or {}
                return self._normalize_config(config)
        
        return self._get_default_config()
    
    def _normalize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize configuration to internal format."""
        # Handle TOML nested structure vs flat YAML structure
        if 'site' in config:
            # TOML format with sections
            normalized = {}
            # Flatten site section to root
            normalized.update(config.get('site', {}))
            # Add build settings
            normalized.update(config.get('build', {}))
            # Add template settings
            if 'templates' in config:
                normalized['template_config'] = config['templates']
            # Add format-specific settings
            if 'formats' in config:
                normalized['format_config'] = config['formats']
            # Add CSS settings
            if 'css' in config:
                normalized['css'] = config['css']
            return normalized
        else:
            # YAML format (flat) or legacy TOML
            return config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration when no config file exists."""
        return {
            'title': 'My Site',
            'url': 'http://localhost:8000',
            'description': 'A static site generated with ctxssg',
            'author': 'Your Name',
            'output_dir': '_site',
            'output_formats': ['html'],
        }
    
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
            page_data = self._process_content(content_file)
            
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
                self._generate_format(page_data, content_file, output_base, fmt)
        
        # Generate index page
        self._generate_index(posts, pages)
    
    def _generate_format(self, page_data: Dict[str, Any], source_file: Path, output_base: Path, fmt: str) -> None:
        """Generate output file for a specific format using templates."""
        # Ensure output directory exists
        output_base.parent.mkdir(parents=True, exist_ok=True)
        
        if fmt == 'html':
            # Use existing HTML rendering with templates
            html = self._render_page(page_data)
            output_path = output_base.with_suffix('.html')
            output_path.write_text(html)
        
        elif fmt in ['plain', 'txt']:
            # Use template-based plain text generation
            post = frontmatter.load(source_file)
            
            # Get format-specific configuration
            plain_config = self.config.get('format_config', {}).get('plain', {})
            wrap_width = plain_config.get('wrap_width', 0)  # 0 means no wrap
            include_metadata = plain_config.get('include_metadata', True)
            
            # Generate plain text content using pandoc
            try:
                extra_args = []
                if wrap_width > 0:
                    extra_args.append('--wrap=auto')  # Pandoc expects 'auto', 'none', or 'preserve'
                else:
                    extra_args.append('--wrap=none')
                
                plain_content = pypandoc.convert_text(
                    post.content,
                    'plain',
                    format='markdown',
                    extra_args=extra_args
                )
            except OSError as e:
                if "pandoc" in str(e).lower():
                    raise RuntimeError("Pandoc is not installed. Please install pandoc: https://pandoc.org/installing.html")
                raise
            except Exception as e:
                raise RuntimeError(f"Failed to convert markdown to plain text: {e}")
            
            # Prepare metadata for template
            metadata = {}
            if include_metadata:
                for key, value in page_data.items():
                    if key not in ['content', 'url'] and value is not None:
                        if hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        metadata[key] = value
            
            # Render using template
            template = self.env.get_template('formats/document.txt.j2')
            content = template.render(
                metadata=metadata if include_metadata else {},
                plain_content=plain_content,
                include_metadata=include_metadata
            )
            
            output_path = output_base.with_suffix('.txt')
            output_path.write_text(content)
        
        elif fmt == 'xml':
            # Use template-based XML generation
            # Get format-specific configuration
            xml_config = self.config.get('format_config', {}).get('xml', {})
            include_namespaces = xml_config.get('include_namespaces', False)
            
            # Parse HTML content into structured format
            content_structure = self._parse_content_structure(page_data['content'])
            
            # Prepare metadata for template
            metadata = {}
            for key, value in page_data.items():
                if key not in ['content', 'url'] and value is not None:
                    if hasattr(value, 'isoformat'):
                        value = value.isoformat()
                    metadata[key] = value
            
            # Render using template
            template = self.env.get_template('formats/document.xml.j2')
            content = template.render(
                metadata=metadata,
                content=content_structure,
                include_namespaces=include_namespaces
            )
            
            output_path = output_base.with_suffix('.xml')
            output_path.write_text(content)
        
        elif fmt == 'json':
            # Use template-based JSON generation
            # Get format-specific configuration
            json_config = self.config.get('format_config', {}).get('json', {})
            pretty_print = json_config.get('pretty_print', True)
            include_metadata = json_config.get('include_metadata', True)
            
            # Parse HTML content into structured format
            content_structure = self._parse_content_structure(page_data['content'])
            
            # Prepare metadata for template
            metadata = {}
            if include_metadata:
                for key, value in page_data.items():
                    if key not in ['content', 'url'] and value is not None:
                        if hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        metadata[key] = value
            
            # Render using template
            template = self.env.get_template('formats/document.json.j2')
            content = template.render(
                metadata=metadata if include_metadata else {},
                content=content_structure,
                pretty_print=pretty_print,
                include_metadata=include_metadata
            )
            
            output_path = output_base.with_suffix('.json')
            output_path.write_text(content)
        
        else:
            # Generic pandoc conversion for other formats
            post = frontmatter.load(source_file)
            try:
                converted_content = pypandoc.convert_text(
                    post.content,
                    fmt,
                    format='markdown'
                )
            except OSError as e:
                if "pandoc" in str(e).lower():
                    raise RuntimeError("Pandoc is not installed. Please install pandoc: https://pandoc.org/installing.html")
                raise
            except Exception as e:
                raise RuntimeError(f"Failed to convert markdown to {fmt} format: {e}")
            
            output_path = output_base.with_suffix(f'.{fmt}')
            output_path.write_text(converted_content)
        
    def _process_content(self, file_path: Path) -> Dict[str, Any]:
        """Process a markdown file with frontmatter."""
        post = frontmatter.load(file_path)
        
        # Convert markdown to HTML using pandoc
        try:
            html_content = pypandoc.convert_text(
                post.content,
                'html',
                format='markdown',
                extra_args=['--highlight-style=pygments']
            )
            
            # Remove automatically generated header IDs for cleaner HTML
            import re
            html_content = re.sub(r'(<h[1-6])\s+id="[^"]*"', r'\1', html_content)
        except OSError as e:
            if "pandoc" in str(e).lower():
                raise RuntimeError("Pandoc is not installed. Please install pandoc: https://pandoc.org/installing.html")
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to convert markdown to HTML: {e}")
        
        # Build page data
        page_data = {
            'title': post.get('title', file_path.stem),
            'content': html_content,
            'date': post.get('date', datetime.now()),
            'layout': post.get('layout', 'default'),
            'url': self._get_url(file_path),
            **post.metadata
        }
        
        return page_data
    
    def _get_url(self, file_path: Path) -> str:
        """Generate URL for a content file."""
        relative_path = file_path.relative_to(self.content_dir).with_suffix('.html')
        return f"/{relative_path.as_posix()}"
    
    def _parse_content_structure(self, html_content: str) -> Dict[str, Any]:
        """Parse HTML content into structured data for templating."""
        soup = BeautifulSoup(html_content, 'html.parser')
        sections = []
        current_section = None
        
        for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'pre', 'blockquote']):
            if element.name.startswith('h'):
                # Start new section
                if current_section:
                    sections.append(current_section)
                
                level = int(element.name[1])
                section_id = element.get('id') or self._generate_id(element.get_text())
                
                current_section = {
                    'id': section_id,
                    'level': level,
                    'title': element.get_text().strip(),
                    'content': []
                }
            elif current_section:
                # Add content to current section
                if element.name == 'p':
                    current_section['content'].append({
                        'type': 'paragraph',
                        'text': self._clean_html(element)
                    })
                elif element.name in ['ul', 'ol']:
                    list_items = [self._clean_html(li) for li in element.find_all('li')]
                    current_section['content'].append({
                        'type': 'list',
                        'list_type': 'ordered' if element.name == 'ol' else 'bullet',
                        'items': list_items
                    })
                elif element.name == 'pre':
                    code_element = element.find('code')
                    if code_element:
                        language = None
                        if code_element.get('class'):
                            for cls in code_element.get('class'):
                                if cls.startswith('sourceCode'):
                                    continue
                                if cls.startswith('language-'):
                                    language = cls[9:]
                                else:
                                    language = cls
                                break
                        
                        current_section['content'].append({
                            'type': 'code',
                            'language': language,
                            'text': code_element.get_text()
                        })
                    else:
                        current_section['content'].append({
                            'type': 'code',
                            'language': None,
                            'text': element.get_text()
                        })
                elif element.name == 'blockquote':
                    current_section['content'].append({
                        'type': 'quote',
                        'text': self._clean_html(element)
                    })
        
        # Add the last section
        if current_section:
            sections.append(current_section)
        
        # If no sections were found, create a default section
        if not sections:
            sections.append({
                'id': 'content',
                'level': 1,
                'title': 'Content',
                'content': [{
                    'type': 'paragraph',
                    'text': self._clean_html(soup)
                }]
            })
        
        return {'sections': sections}
    
    
    def _generate_id(self, text: str) -> str:
        """Generate a URL-safe ID from text."""
        # Convert to lowercase and replace spaces/special chars with hyphens
        id_text = re.sub(r'[^\w\s-]', '', text.lower())
        id_text = re.sub(r'[-\s]+', '-', id_text)
        return id_text.strip('-')
    
    def _clean_html(self, element) -> str:
        """Extract clean text from HTML element, preserving basic formatting."""
        if hasattr(element, 'get_text'):
            return element.get_text().strip()
        return str(element).strip()
    
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
