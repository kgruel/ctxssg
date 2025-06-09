# ctxssg

[![PyPI](https://img.shields.io/pypi/v/ctxssg.svg)](https://pypi.org/project/ctxssg/)
[![Changelog](https://img.shields.io/github/v/release/kgruel/ctxssg?include_prereleases&label=changelog)](https://github.com/kgruel/ctxssg/releases)
[![Tests](https://github.com/kgruel/ctxssg/actions/workflows/test.yml/badge.svg)](https://github.com/kgruel/ctxssg/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/kgruel/ctxssg/blob/master/LICENSE)

A pandoc-based static site generator designed for technical documentation and content that requires structured output in multiple formats.

## Features

### Core Capabilities
- **Multi-format Output**: Generate HTML, XML, JSON, and plain text from single source files
- **Pandoc Integration**: Leverage pandoc's powerful document conversion with syntax highlighting
- **Template-driven Architecture**: Jinja2-based templating with customizable output formats
- **TOML Configuration**: Modern configuration with format-specific options
- **Live Development Server**: Hot-reload development environment with file watching

## Installation

### Prerequisites
- Python 3.10+
- [Pandoc](https://pandoc.org/installing.html) (required for document conversion)

## Install
```bash
uv tool install ctxssg
```

### via Pip
```bash
pip install ctxssg
```

### Verify Installation
```bash
ctxssg doctor  # Check system dependencies and configuration
```

## Quick Start

### 1. Initialize Site
```bash
ctxssg init my-docs --title "Technical Documentation"
cd my-docs
```

### 2. Configure Output Formats
Edit `config.toml` to enable multiple formats:
```toml
[build]
output_formats = ["html", "xml", "json", "plain"]

[formats.json]
pretty_print = true
include_metadata = true

[formats.xml]
include_namespaces = false
```

### 3. Create Content
```bash
ctxssg new "API Reference" --type page
ctxssg new "Getting Started" --type post
```

### 4. Build and Serve
```bash
ctxssg build    # Generate all configured formats
ctxssg serve    # Development server with hot-reload
```

## Architecture

### Project Structure
```
my-docs/
├── config.toml              # TOML configuration
├── content/                 # Source content
│   ├── posts/              # Blog posts/articles
│   │   └── *.md
│   └── *.md                # Static pages
├── templates/               # Jinja2 templates
│   ├── base.html           # Base HTML template
│   ├── default.html        # Default page template
│   ├── index.html          # Homepage template
│   ├── post.html           # Post template
│   └── formats/            # Output format templates
│       ├── document.xml.j2 # XML output template
│       ├── document.json.j2# JSON output template
│       └── document.txt.j2 # Plain text template
├── static/                  # Static assets
│   ├── css/
│   └── js/
└── _site/                   # Generated output
    ├── *.html              # HTML files
    ├── *.xml               # XML files
    ├── *.json              # JSON files
    └── *.txt               # Plain text files
```

### Content Format
Content files use Markdown with YAML frontmatter:

```markdown
---
title: API Authentication
date: 2024-01-15
layout: default
tags: [api, auth, security]
---

# Authentication

API authentication is handled via...

## OAuth 2.0 Flow

1. Obtain authorization code
2. Exchange for access token
3. Include token in requests
```

## Configuration

### Basic Configuration (`config.toml`)
```toml
[site]
title = "Technical Documentation"
url = "https://docs.example.com"
description = "Comprehensive API and development documentation"
author = "Development Team"

[build]
output_dir = "_site"
output_formats = ["html", "xml", "json", "plain"]

[formats.json]
pretty_print = true
include_metadata = true

[formats.xml]
include_namespaces = false

[formats.plain]
include_metadata = true
wrap_width = 80
```

### Template Customization
Override default templates by creating files in your `templates/` directory. Templates use Jinja2 syntax with access to:

- `site` - Site configuration
- `page` - Current page data
- `content` - Structured content data (for format templates)
- `metadata` - Page metadata

### Format Templates
Create custom output formats by modifying templates in `templates/formats/`:

- `document.xml.j2` - XML output structure
- `document.json.j2` - JSON API response format
- `document.txt.j2` - Plain text documentation

## CLI Commands

### Site Management
```bash
ctxssg init [path] --title "Site Title"     # Initialize new site
ctxssg build                                # Build all configured formats
ctxssg serve --port 8000 --watch           # Development server
ctxssg doctor                               # System diagnostics
```

### Content Creation
```bash
ctxssg new "Page Title" --type page         # Create new page
ctxssg new "Post Title" --type post         # Create new post
ctxssg convert input.md --format xml        # Convert single file
```

### Development Commands
```bash
ctxssg serve --watch                        # Hot-reload development
ctxssg build --watch                        # Continuous building
```

## Output Formats

### HTML
Standard web output with responsive design, syntax highlighting, and navigation.

### XML
Structured XML output suitable for API consumption:
```xml
<document>
  <metadata>
    <title>API Reference</title>
    <date>2024-01-15</date>
  </metadata>
  <content>
    <section id="authentication" level="1">
      <title>Authentication</title>
      <content>...</content>
    </section>
  </content>
</document>
```

### JSON
API-friendly JSON structure:
```json
{
  "metadata": {
    "title": "API Reference",
    "date": "2024-01-15"
  },
  "content": {
    "sections": [
      {
        "id": "authentication",
        "level": 1,
        "title": "Authentication",
        "content": [...]
      }
    ]
  }
}
```

### Plain Text
Clean text output for documentation systems and CLIs.

## Advanced Usage

### Custom Templates
Create format-specific templates for specialized output:

```jinja2
{# templates/formats/api-spec.json.j2 #}
{
  "apiVersion": "v1",
  "kind": "Documentation",
  "metadata": {{ metadata | tojson }},
  "spec": {
    "sections": [
      {% for section in content.sections %}
      {
        "name": "{{ section.title }}",
        "content": "{{ section.content | join(' ') }}"
      }{% if not loop.last %},{% endif %}
      {% endfor %}
    ]
  }
}
```

### Batch Processing
Process multiple files programmatically:

```python
from ctxssg.generator import Site
from pathlib import Path

site = Site(Path("my-docs"))
site.build()  # Generate all formats
```

## Development

### Setup Development Environment
```bash
git clone https://github.com/kgruel/ctxssg.git
cd ctxssg
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e '.[dev]'
```

### Run Tests
```bash
python -m pytest                    # Run test suite
ruff check .                       # Lint code
ruff format .                      # Format code
```

### Project Architecture
- `ctxssg/generator.py` - Core site generation logic
- `ctxssg/cli.py` - Command-line interface
- `ctxssg/templates/` - Package template resources
- `ctxssg/assets/` - Default CSS and static assets

## Requirements

### System Dependencies
- **Pandoc**: Document conversion engine
- **Python 3.10+**: Modern Python with typing support

### Python Dependencies
- `click` - CLI framework
- `jinja2` - Template engine
- `pypandoc` - Pandoc integration
- `pyyaml` - YAML configuration support
- `tomli` - TOML configuration support
- `python-frontmatter` - Frontmatter parsing
- `beautifulsoup4` - HTML parsing
- `watchdog` - File system monitoring

## License

Apache-2.0

## Contributing

Contributions are welcome! Please read the contributing guidelines and submit pull requests for any enhancements.