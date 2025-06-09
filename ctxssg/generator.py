"""Core static site generator functionality."""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
import frontmatter
from jinja2 import Environment, FileSystemLoader, select_autoescape
import pypandoc
from datetime import datetime


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
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
    def _load_config(self) -> Dict[str, Any]:
        """Load site configuration from config.yaml."""
        config_path = self.root / "config.yaml"
        if config_path.exists():
            with open(config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def build(self):
        """Build the entire site."""
        # Clean output directory
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True)
        
        # Copy static files
        if self.static_dir.exists():
            shutil.copytree(self.static_dir, self.output_dir / "static")
        
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
                output_base = self.output_dir / "posts" / relative_path.with_suffix('')
            else:
                pages.append(page_data)
                output_base = self.output_dir / relative_path.with_suffix('')
            
            # Generate files for each output format
            for fmt in output_formats:
                self._generate_format(page_data, content_file, output_base, fmt)
        
        # Generate index page
        self._generate_index(posts, pages)
    
    def _generate_format(self, page_data: Dict[str, Any], source_file: Path, output_base: Path, fmt: str):
        """Generate output file for a specific format."""
        # Ensure output directory exists
        output_base.parent.mkdir(parents=True, exist_ok=True)
        
        if fmt == 'html':
            # Use existing HTML rendering with templates
            html = self._render_page(page_data)
            output_path = output_base.with_suffix('.html')
            output_path.write_text(html)
        
        elif fmt == 'plain' or fmt == 'txt':
            # Generate enhanced plain text version
            post = frontmatter.load(source_file)
            plain_content = pypandoc.convert_text(
                post.content,
                'plain',
                format='markdown',
                extra_args=['--wrap=none']
            )
            
            # Build metadata section
            metadata_lines = ["METADATA:"]
            for key, value in page_data.items():
                if key not in ['content', 'url'] and value is not None:
                    metadata_lines.append(f"{key.title()}: {value}")
            
            # Combine sections
            full_content = "\n".join(metadata_lines) + "\n\nCONTENT:\n" + "="*80 + "\n\n" + plain_content
            
            output_path = output_base.with_suffix('.txt')
            output_path.write_text(full_content)
        
        elif fmt == 'xml':
            # Generate clean semantic XML version
            post = frontmatter.load(source_file)
            
            # Build metadata section
            metadata_xml = []
            for key, value in page_data.items():
                if key not in ['content', 'url'] and value is not None:
                    metadata_xml.append(f"    <{key}>{self._escape_xml(str(value))}</{key}>")
            
            # Convert content to HTML first, then parse for clean structure
            html_content = pypandoc.convert_text(
                post.content,
                'html',
                format='markdown'
            )
            
            # Parse HTML into clean XML structure
            content_xml = self._html_to_clean_xml(html_content)
            
            # Build complete XML document
            xml_doc = f'''<?xml version="1.0" encoding="UTF-8"?>
<document>
  <meta>
{chr(10).join(metadata_xml)}
  </meta>
  <content>
{content_xml}
  </content>
</document>'''
            
            output_path = output_base.with_suffix('.xml')
            output_path.write_text(xml_doc)
        
        elif fmt == 'json':
            # Generate JSON version
            import json
            post = frontmatter.load(source_file)
            
            # Build metadata
            metadata = {}
            for key, value in page_data.items():
                if key not in ['content', 'url'] and value is not None:
                    # Convert datetime objects to strings
                    if hasattr(value, 'isoformat'):
                        value = value.isoformat()
                    metadata[key] = value
            
            # Convert content to HTML first, then parse for structured data
            html_content = pypandoc.convert_text(
                post.content,
                'html',
                format='markdown'
            )
            
            # Parse HTML into structured content
            structured_content = self._html_to_structured_data(html_content)
            
            # Build JSON document
            json_doc = {
                "metadata": metadata,
                "content": structured_content
            }
            
            output_path = output_base.with_suffix('.json')
            output_path.write_text(json.dumps(json_doc, indent=2, ensure_ascii=False))
        
        else:
            # Generic pandoc conversion for other formats
            post = frontmatter.load(source_file)
            converted_content = pypandoc.convert_text(
                post.content,
                fmt,
                format='markdown'
            )
            
            output_path = output_base.with_suffix(f'.{fmt}')
            output_path.write_text(converted_content)
        
    def _process_content(self, file_path: Path) -> Dict[str, Any]:
        """Process a markdown file with frontmatter."""
        post = frontmatter.load(file_path)
        
        # Convert markdown to HTML using pandoc
        html_content = pypandoc.convert_text(
            post.content,
            'html',
            format='markdown',
            extra_args=['--highlight-style=pygments']
        )
        
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
    
    def _generate_index(self, posts: List[Dict[str, Any]], pages: List[Dict[str, Any]]):
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
    
    def _escape_xml(self, text):
        """Escape XML special characters."""
        return (str(text)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))
    
    def _html_to_clean_xml(self, html_content):
        """Convert HTML to clean semantic XML."""
        from bs4 import BeautifulSoup
        import re
        
        soup = BeautifulSoup(html_content, 'html.parser')
        xml_parts = []
        
        for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'pre', 'blockquote']):
            if element.name.startswith('h'):
                # Header element
                level = int(element.name[1])
                title = element.get_text().strip()
                # Create ID from title
                id_attr = re.sub(r'[^a-zA-Z0-9\s-]', '', title).strip().lower().replace(' ', '-')
                xml_parts.append(f'    <section id="{id_attr}" level="{level}">')
                xml_parts.append(f'      <title>{self._escape_xml(title)}</title>')
                
            elif element.name == 'p':
                text = element.get_text().strip()
                if text:
                    xml_parts.append(f'      <paragraph>{self._escape_xml(text)}</paragraph>')
                    
            elif element.name in ['ul', 'ol']:
                list_type = 'ordered' if element.name == 'ol' else 'bullet'
                xml_parts.append(f'      <list type="{list_type}">')
                for li in element.find_all('li'):
                    item_text = li.get_text().strip()
                    xml_parts.append(f'        <item>{self._escape_xml(item_text)}</item>')
                xml_parts.append('      </list>')
                
            elif element.name == 'pre':
                code_elem = element.find('code')
                if code_elem:
                    # Extract language from class if present
                    language = ''
                    if code_elem.get('class'):
                        for cls in code_elem.get('class'):
                            if cls.startswith('language-'):
                                language = cls.replace('language-', '')
                                break
                    
                    code_text = code_elem.get_text()
                    lang_attr = f' language="{language}"' if language else ''
                    xml_parts.append(f'      <code{lang_attr}>{self._escape_xml(code_text)}</code>')
                else:
                    xml_parts.append(f'      <code>{self._escape_xml(element.get_text())}</code>')
                    
            elif element.name == 'blockquote':
                text = element.get_text().strip()
                xml_parts.append(f'      <quote>{self._escape_xml(text)}</quote>')
        
        # Close any open sections
        if xml_parts and any('section' in part for part in xml_parts):
            xml_parts.append('    </section>')
        
        return '\n'.join(xml_parts)
    
    def _html_to_structured_data(self, html_content):
        """Convert HTML to structured data for JSON output."""
        from bs4 import BeautifulSoup
        import re
        
        soup = BeautifulSoup(html_content, 'html.parser')
        sections = []
        current_section = None
        
        for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'pre', 'blockquote']):
            if element.name.startswith('h'):
                # Start new section
                if current_section:
                    sections.append(current_section)
                
                level = int(element.name[1])
                title = element.get_text().strip()
                # Create ID from title
                id_attr = re.sub(r'[^a-zA-Z0-9\s-]', '', title).strip().lower().replace(' ', '-')
                
                current_section = {
                    'id': id_attr,
                    'level': level,
                    'title': title,
                    'content': []
                }
                
            elif current_section:
                if element.name == 'p':
                    text = element.get_text().strip()
                    if text:
                        current_section['content'].append({
                            'type': 'paragraph',
                            'text': text
                        })
                        
                elif element.name in ['ul', 'ol']:
                    list_type = 'ordered' if element.name == 'ol' else 'bullet'
                    items = [li.get_text().strip() for li in element.find_all('li')]
                    current_section['content'].append({
                        'type': 'list',
                        'style': list_type,
                        'items': items
                    })
                    
                elif element.name == 'pre':
                    code_elem = element.find('code')
                    if code_elem:
                        # Extract language from class if present
                        language = ''
                        if code_elem.get('class'):
                            for cls in code_elem.get('class'):
                                if cls.startswith('language-'):
                                    language = cls.replace('language-', '')
                                    break
                        
                        code_data = {
                            'type': 'code',
                            'text': code_elem.get_text()
                        }
                        if language:
                            code_data['language'] = language
                        current_section['content'].append(code_data)
                    else:
                        current_section['content'].append({
                            'type': 'code',
                            'text': element.get_text()
                        })
                        
                elif element.name == 'blockquote':
                    current_section['content'].append({
                        'type': 'quote',
                        'text': element.get_text().strip()
                    })
        
        # Add the last section
        if current_section:
            sections.append(current_section)
        
        return {'sections': sections}


class SiteGenerator:
    """Main interface for generating static sites."""
    
    @staticmethod
    def init_site(path: Path, title: str = "My Site"):
        """Initialize a new site structure."""
        # Create directory structure
        (path / "content").mkdir(parents=True, exist_ok=True)
        (path / "content" / "posts").mkdir(exist_ok=True)
        (path / "templates").mkdir(exist_ok=True)
        (path / "static").mkdir(exist_ok=True)
        (path / "static" / "css").mkdir(exist_ok=True)
        (path / "static" / "js").mkdir(exist_ok=True)
        
        # Create default config
        config = {
            'title': title,
            'url': 'http://localhost:8000',
            'description': 'A static site generated with ctxssg',
            'author': 'Your Name',
            'output_dir': '_site',
            'output_formats': ['html', 'plain', 'xml', 'json'],
        }
        
        with open(path / "config.yaml", 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        # Create default templates
        SiteGenerator._create_default_templates(path / "templates")
        
        # Create sample content
        SiteGenerator._create_sample_content(path / "content")
        
        # Copy default CSS
        SiteGenerator._create_default_css(path / "static" / "css")
        
    @staticmethod
    def _create_default_templates(templates_dir: Path):
        """Create default template files."""
        # Base template
        base_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ page.title }} - {{ site.title }}</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <header>
        <h1><a href="/">{{ site.title }}</a></h1>
        <nav>
            <a href="/">Home</a>
            <a href="/about.html">About</a>
        </nav>
    </header>
    
    <main>
        {% block content %}{% endblock %}
    </main>
    
    <footer>
        <p>&copy; {{ site.author }} - Built with ctxssg</p>
    </footer>
</body>
</html>'''
        
        (templates_dir / "base.html").write_text(base_template)
        
        # Default page template
        default_template = '''{% extends "base.html" %}

{% block content %}
<article>
    <h1>{{ page.title }}</h1>
    {{ page.content | safe }}
</article>
{% endblock %}'''
        
        (templates_dir / "default.html").write_text(default_template)
        
        # Index template
        index_template = '''{% extends "base.html" %}

{% block content %}
<div class="home">
    <h2>Recent Posts</h2>
    <ul class="post-list">
        {% for post in page.posts %}
        <li>
            <span class="post-date">{{ post.date.strftime('%Y-%m-%d') }}</span>
            <a href="{{ post.url }}">{{ post.title }}</a>
        </li>
        {% endfor %}
    </ul>
</div>
{% endblock %}'''
        
        (templates_dir / "index.html").write_text(index_template)
        
        # Post template
        post_template = '''{% extends "base.html" %}

{% block content %}
<article class="post">
    <header>
        <h1>{{ page.title }}</h1>
        <time datetime="{{ page.date }}">{{ page.date.strftime('%B %d, %Y') }}</time>
    </header>
    
    <div class="post-content">
        {{ page.content | safe }}
    </div>
</article>
{% endblock %}'''
        
        (templates_dir / "post.html").write_text(post_template)
    
    @staticmethod
    def _create_sample_content(content_dir: Path):
        """Create sample content files."""
        # About page
        about_content = '''---
title: About
layout: default
---

# About This Site

This is a static site generated with ctxssg, a pandoc-based static site generator.

## Features

- Markdown content with YAML frontmatter
- Pandoc for powerful document conversion
- Jinja2 templates
- Simple and fast
'''
        
        (content_dir / "about.md").write_text(about_content)
        
        # Sample post
        post_content = '''---
title: Welcome to ctxssg
date: 2024-01-01
layout: post
---

Welcome to your new static site! This post was generated automatically when you initialized your site.

## Getting Started

1. Add your content as Markdown files in the `content` directory
2. Customize templates in the `templates` directory
3. Add static assets to the `static` directory
4. Build your site with `ctxssg build`

Happy writing!
'''
        
        (content_dir / "posts" / "welcome.md").write_text(post_content)
    
    @staticmethod
    def _create_default_css(css_dir: Path):
        """Copy default CSS to the static directory."""
        from importlib.resources import read_text
        import ctxssg
        
        try:
            # Try to read from package resources
            css_content = read_text(ctxssg, 'default_style.css')
        except:
            # Fallback to reading from file
            css_file = Path(__file__).parent / 'default_style.css'
            if css_file.exists():
                css_content = css_file.read_text()
            else:
                # Inline minimal CSS if file not found
                css_content = '''/* Minimal default CSS */
body { font-family: -apple-system, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 1rem; }
h1, h2, h3 { margin-top: 1.5rem; }
a { color: #0066cc; }
pre { background: #f5f5f5; padding: 1rem; overflow-x: auto; }
code { font-family: monospace; background: #f5f5f5; padding: 0.2em 0.4em; }
'''
        
        (css_dir / "style.css").write_text(css_content)