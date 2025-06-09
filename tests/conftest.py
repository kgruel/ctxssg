"""Shared pytest fixtures for ctxssg test suite.

This module provides reusable fixtures to eliminate code duplication
across test files and implement DRY (Don't Repeat Yourself) principles.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from click.testing import CliRunner
from jinja2 import Environment, DictLoader

from ctxssg import Site, SiteGenerator
from ctxssg.content import ContentProcessor
from ctxssg.formats import FormatGenerator


# Core Infrastructure Fixtures

@pytest.fixture
def cli_runner():
    """Provides a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def initialized_site(tmp_path):
    """Provides a fully initialized test site."""
    site_path = tmp_path / "test_site"
    site_path.mkdir()
    SiteGenerator.init_site(site_path, "Test Site")
    return Site(site_path)


@pytest.fixture
def content_dir(tmp_path):
    """Provides a content directory for testing."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    return content_dir


@pytest.fixture
def content_processor(content_dir):
    """Provides a ContentProcessor instance."""
    return ContentProcessor(content_dir)


@pytest.fixture
def jinja_env():
    """Provides a basic Jinja2 environment for testing."""
    return Environment(loader=DictLoader({}))


@pytest.fixture
def format_generator(jinja_env):
    """Provides a FormatGenerator instance."""
    return FormatGenerator(jinja_env, {})


@pytest.fixture
def site_with_tempdir(tmp_path):
    """Provides a site instance using tempfile for compatibility with existing tests."""
    temp_dir = tempfile.mkdtemp()
    site_path = Path(temp_dir)
    SiteGenerator.init_site(site_path, "Test Site")
    site = Site(site_path)
    
    # Store cleanup function for teardown
    site._temp_dir = temp_dir
    yield site
    
    # Cleanup
    shutil.rmtree(temp_dir)


# Test Data Fixtures

@pytest.fixture
def sample_markdown():
    """Provides standard test markdown content."""
    return """---
title: Test Document
author: Test Author
date: 2024-01-01
layout: default
---

# Test Header

This is a test paragraph with **bold** text.

```python
def hello():
    print("Hello, world!")
```

> This is a quoted section.

## Subheader

- List item 1
- List item 2

1. Ordered item 1
2. Ordered item 2
"""


@pytest.fixture
def sample_config_toml():
    """Provides standard TOML configuration for testing."""
    return """
[site]
title = "Test Site"
url = "https://example.com"

[build]
output_dir = "_site"
output_formats = ["html", "json", "xml"]

[formats.json]
pretty_print = true
include_metadata = true

[formats.xml]
include_namespaces = false
"""


@pytest.fixture
def sample_config_yaml():
    """Provides standard YAML configuration for testing."""
    return """
title: Test Site
url: https://example.com
output_dir: _site
output_formats:
  - html
  - json
  - xml
"""


@pytest.fixture
def sample_about_markdown():
    """Provides sample about page markdown."""
    return """---
title: About
layout: default
---

# About This Site

This is a sample about page for testing purposes.
"""


@pytest.fixture
def sample_welcome_post():
    """Provides sample welcome post markdown."""
    return """---
title: Welcome
date: 2024-01-01
layout: post
---

# Welcome to your new site!

This is your first post. You can edit or delete it to get started.
"""


# Mock Fixtures

@pytest.fixture
def mock_pandoc_failure(monkeypatch):
    """Mocks pandoc to simulate installation failure."""
    def mock_get_version():
        raise OSError("pandoc not found")
    
    def mock_convert_text(*args, **kwargs):
        raise OSError("pandoc not found")
    
    monkeypatch.setattr('pypandoc.get_pandoc_version', mock_get_version)
    monkeypatch.setattr('pypandoc.convert_text', mock_convert_text)


@pytest.fixture
def mock_pandoc_error(monkeypatch):
    """Mocks pandoc to simulate conversion errors."""
    def mock_convert_text(*args, **kwargs):
        raise Exception("conversion failed")
    
    monkeypatch.setattr('pypandoc.convert_text', mock_convert_text)


@pytest.fixture
def mock_pypandoc_missing(monkeypatch):
    """Mocks pypandoc module as missing."""
    import sys
    original_modules = sys.modules.copy()
    
    # Remove pypandoc from sys.modules if it exists
    if 'pypandoc' in sys.modules:
        del sys.modules['pypandoc']
    
    # Mock import to raise ImportError
    def mock_import(name, *args, **kwargs):
        if name == 'pypandoc':
            raise ImportError("No module named 'pypandoc'")
        return original_import(name, *args, **kwargs)
    
    original_import = __builtins__.__import__
    monkeypatch.setattr(__builtins__, '__import__', mock_import)
    
    yield
    
    # Restore original state
    sys.modules.update(original_modules)


# Advanced Fixtures for Complex Scenarios

@pytest.fixture
def site_with_content(initialized_site, sample_markdown):
    """Provides a site with sample content files."""
    content_dir = initialized_site.root / "content"
    (content_dir / "test-page.md").write_text(sample_markdown)
    posts_dir = content_dir / "posts"
    (posts_dir / "test-post.md").write_text(sample_markdown)
    return initialized_site


@pytest.fixture(params=['html', 'json', 'xml', 'plain'])
def output_format(request):
    """Parameterized fixture for testing all output formats."""
    return request.param


@pytest.fixture
def format_config():
    """Provides format-specific configuration for testing."""
    return {
        'json': {
            'pretty_print': True,
            'include_metadata': True
        },
        'xml': {
            'include_namespaces': False
        },
        'plain': {
            'include_metadata': True,
            'wrap_width': 80
        }
    }


@pytest.fixture
def jinja_env_with_templates():
    """Provides a Jinja2 environment with test templates."""
    templates = {
        'base.html': '''<!DOCTYPE html>
<html>
<head><title>{{ site.title }}</title></head>
<body>{% block content %}{% endblock %}</body>
</html>''',
        'default.html': '''{% extends "base.html" %}
{% block content %}
<h1>{{ page.title }}</h1>
{{ page.content | safe }}
{% endblock %}''',
        'index.html': '''{% extends "base.html" %}
{% block content %}
<h1>{{ page.title }}</h1>
<ul>
{% for post in page.posts %}
<li>{{ post.title }} - {{ post.date }}</li>
{% endfor %}
</ul>
{% endblock %}''',
        'post.html': '''{% extends "base.html" %}
{% block content %}
<h1>{{ page.title }}</h1>
<p>{{ page.date }}</p>
{{ page.content | safe }}
{% endblock %}'''
    }
    return Environment(loader=DictLoader(templates))


# Content Processing Fixtures

@pytest.fixture
def sample_frontmatter_content():
    """Provides content with frontmatter for testing."""
    return {
        'with_frontmatter': """---
title: Test Page
author: Test Author
date: 2024-01-01
layout: default
tags: [test, example]
---

# Content Header

This is test content with frontmatter.""",
        
        'without_frontmatter': """# Simple Header

This is content without frontmatter metadata.""",
        
        'complex_frontmatter': """---
title: Complex Test
description: A more complex test page
author: Test Author
date: 2024-01-01T10:30:00
layout: custom
tags: 
  - test
  - complex
  - example
published: true
---

# Complex Content

This content has more complex frontmatter with various data types."""
    }


@pytest.fixture
def site_structure_paths(tmp_path):
    """Provides standardized site structure paths for testing."""
    site_path = tmp_path / "test_site"
    return {
        'site': site_path,
        'content': site_path / "content",
        'posts': site_path / "content" / "posts",
        'templates': site_path / "templates",
        'static': site_path / "static",
        'css': site_path / "static" / "css",
        'js': site_path / "static" / "js",
        'output': site_path / "_site"
    }