# ctxssg

[![PyPI](https://img.shields.io/pypi/v/ctxssg.svg)](https://pypi.org/project/ctxssg/)
[![Changelog](https://img.shields.io/github/v/release/kgruel/ctxssg?include_prereleases&label=changelog)](https://github.com/kgruel/ctxssg/releases)
[![Tests](https://github.com/kgruel/ctxssg/actions/workflows/test.yml/badge.svg)](https://github.com/kgruel/ctxssg/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/kgruel/ctxssg/blob/master/LICENSE)

A pandoc-based static site generator for creating contextual documentation sites.

## Features

- **Pandoc-powered**: Uses pandoc for powerful document conversion with syntax highlighting
- **YAML frontmatter**: Support for metadata in your Markdown files
- **Jinja2 templates**: Flexible templating system for layouts
- **Live reload**: Development server with automatic rebuilding on file changes
- **Simple CLI**: Easy-to-use command-line interface
- **Fast**: Minimal dependencies and efficient build process

## Installation

Install this tool using `pip`:
```bash
pip install ctxssg
```

## Quick Start

1. **Initialize a new site:**
   ```bash
   ctxssg init my-site --title "My Documentation"
   cd my-site
   ```

2. **Create content:**
   ```bash
   ctxssg new "Getting Started" --type post
   ctxssg new "About" --type page
   ```

3. **Build the site:**
   ```bash
   ctxssg build
   ```

4. **Serve locally with live reload:**
   ```bash
   ctxssg serve --watch
   ```

## Project Structure

```
my-site/
├── config.yaml          # Site configuration
├── content/            # Your markdown content
│   ├── posts/         # Blog posts
│   └── *.md           # Pages
├── templates/          # Jinja2 templates
│   ├── base.html      # Base template
│   ├── default.html   # Default page template
│   ├── index.html     # Homepage template
│   └── post.html      # Blog post template
├── static/            # Static assets
│   ├── css/
│   └── js/
└── _site/             # Generated site (git-ignored)
```

## Content Format

Create content files in Markdown with YAML frontmatter:

```markdown
---
title: My First Post
date: 2024-01-01
layout: post
tags: [tutorial, getting-started]
---

# Welcome

Your content goes here...
```

## Configuration

Edit `config.yaml` to customize your site:

```yaml
title: My Site
url: https://example.com
description: A static site built with ctxssg
author: Your Name
output_dir: _site
```

## Commands

- `ctxssg init [path]` - Initialize a new site
- `ctxssg build` - Build the static site
- `ctxssg serve` - Serve the site locally
- `ctxssg new [title]` - Create a new post or page
- `ctxssg --help` - Show help for any command

### Command Options

**init**
- `--title, -t` - Set the site title (default: "My Site")

**build**
- `--watch, -w` - Watch for changes and rebuild automatically

**serve**
- `--port, -p` - Port to serve on (default: 8000)
- `--watch, -w` - Watch for changes and rebuild

**new**
- `--type, -t` - Content type: 'post' or 'page' (default: 'post')

## Development

To contribute to this tool, first checkout the code. Then create a new virtual environment:
```bash
cd ctxssg
python -m venv venv
source venv/bin/activate
```

Now install the dependencies and test dependencies:
```bash
pip install -e '.[test]'
```

To run the tests:
```bash
python -m pytest
```

For development with automatic rebuilding:
```bash
ctxssg serve --watch --port 8080
```

This will:
- Start a local server at http://localhost:8080
- Watch for file changes
- Automatically rebuild the site
- No browser refresh needed!

## License

Apache-2.0