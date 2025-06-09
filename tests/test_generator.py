"""Tests for ctxssg.generator module."""

import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from ctxssg import Site, SiteGenerator
from ctxssg.generator import check_dependencies


def test_import():
    """Test that the package can be imported."""
    import ctxssg
    assert ctxssg.__version__ == "0.1.0"


class TestSiteGenerator:
    """Test the SiteGenerator class."""
    
    def test_init_site(self, tmp_path):
        """Test site initialization."""
        site_path = tmp_path / "test_site"
        site_path.mkdir()
        
        SiteGenerator.init_site(site_path, "Test Site")
        
        # Check directory structure
        assert (site_path / "config.toml").exists()
        assert (site_path / "content").exists()
        assert (site_path / "content" / "posts").exists()
        assert (site_path / "templates").exists()
        assert (site_path / "static").exists()
        assert (site_path / "static" / "css").exists()
        assert (site_path / "static" / "js").exists()
        
        # Check templates
        assert (site_path / "templates" / "base.html").exists()
        assert (site_path / "templates" / "default.html").exists()
        assert (site_path / "templates" / "index.html").exists()
        assert (site_path / "templates" / "post.html").exists()
        
        # Check sample content
        assert (site_path / "content" / "about.md").exists()
        assert (site_path / "content" / "posts" / "welcome.md").exists()
        
        # Check CSS
        assert (site_path / "static" / "css" / "style.css").exists()
    
    def test_fallback_methods(self, tmp_path):
        """Test SiteGenerator fallback methods."""
        # Test fallback config
        config = SiteGenerator._get_fallback_config()
        assert "{title}" in config
        assert "[site]" in config
        assert "[build]" in config
        
        # Test fallback about
        about = SiteGenerator._get_fallback_about()
        assert "title: About" in about
        assert "layout: default" in about
        assert "About This Site" in about
        
        # Test fallback welcome
        welcome = SiteGenerator._get_fallback_welcome()
        assert "title: Welcome" in welcome
        assert "layout: post" in welcome
        assert "Welcome to your new site!" in welcome
        
        # Test fallback CSS creation
        css_path = tmp_path / "style.css"
        SiteGenerator._create_fallback_css(css_path)
        
        assert css_path.exists()
        css_content = css_path.read_text()
        assert "body {" in css_content
        assert "font-family:" in css_content


class TestSite:
    """Test the Site class."""
    
    def test_load_config(self, site_with_tempdir):
        """Test config loading."""
        assert site_with_tempdir.config['title'] == "Test Site"
        assert site_with_tempdir.config['output_dir'] == "_site"
    
    def test_build(self, site_with_tempdir):
        """Test site building."""
        site_with_tempdir.build()
        
        # Check output directory
        assert site_with_tempdir.output_dir.exists()
        assert (site_with_tempdir.output_dir / "index.html").exists()
        assert (site_with_tempdir.output_dir / "about.html").exists()
        assert (site_with_tempdir.output_dir / "posts" / "welcome.html").exists()
        assert (site_with_tempdir.output_dir / "static" / "css" / "style.css").exists()
    
    def test_process_content(self, site_with_tempdir, sample_markdown):
        """Test markdown processing."""
        # Create a test markdown file
        test_md = site_with_tempdir.root / "content" / "test.md"
        test_md.write_text(sample_markdown)
        
        page_data = site_with_tempdir._process_content(test_md)
        
        assert page_data['title'] == "Test Document"
        assert page_data['layout'] == "default"
        assert "<h1>Test Header</h1>" in page_data['content']
        assert "<strong>bold</strong>" in page_data['content']
        assert "hello()" in page_data['content']


class TestGenerator:
    """Test the generator module functions."""
    
    def test_check_dependencies_success(self):
        """Test successful dependency check."""
        # Should not raise an exception if pandoc is available
        try:
            check_dependencies()
        except RuntimeError:
            # Skip test if pandoc is not installed
            import pytest
            pytest.skip("Pandoc not available for testing")
    
    def test_missing_pandoc_error(self, mock_pandoc_failure):
        """Test check_dependencies with missing pandoc."""
        try:
            check_dependencies()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Pandoc is required" in str(e)
    
    def test_pandoc_other_error(self, monkeypatch):
        """Test check_dependencies with other pandoc error."""
        # Mock pypandoc to raise general exception
        def mock_get_pandoc_version():
            raise Exception("Some other error")
        
        monkeypatch.setattr('pypandoc.get_pandoc_version', mock_get_pandoc_version)
        
        try:
            check_dependencies()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Error checking pandoc installation" in str(e)
    
    def test_site_process_css_user_css(self, site_structure_paths, sample_config_toml):
        """Test CSS processing with user CSS file."""
        # Create site structure using fixture
        paths = site_structure_paths
        paths['site'].mkdir()
        paths['content'].mkdir()
        paths['templates'].mkdir()
        paths['css'].mkdir(parents=True)
        
        # Create config
        config_path = paths['site'] / "config.toml"
        config_path.write_text(sample_config_toml)
        
        # Create user CSS
        user_css_path = paths['css'] / "style.css"
        user_css_content = "body { background: red; }"
        user_css_path.write_text(user_css_content)
        
        site = Site(paths['site'])
        site._process_css()
        
        # Check that user CSS was copied
        output_css = site.output_dir / "static" / "css" / "style.css"
        assert output_css.exists()
        assert output_css.read_text() == user_css_content
    
    def test_site_process_css_fallback(self, site_structure_paths, sample_config_toml):
        """Test CSS processing with fallback CSS."""
        # Create site structure using fixture
        paths = site_structure_paths
        paths['site'].mkdir()
        paths['content'].mkdir()
        paths['templates'].mkdir()
        paths['static'].mkdir()
        
        # Create config
        config_path = paths['site'] / "config.toml"
        config_path.write_text(sample_config_toml)
        
        site = Site(paths['site'])
        site._process_css()
        
        # Should create fallback CSS
        output_css = site.output_dir / "static" / "css" / "style.css"
        assert output_css.exists()
        
        css_content = output_css.read_text()
        assert "body {" in css_content
        assert "font-family:" in css_content
    
    def test_site_generate_index_with_posts(self, site_structure_paths, sample_config_toml):
        """Test index generation with posts."""
        # Create site structure using fixture
        paths = site_structure_paths
        paths['site'].mkdir()
        paths['content'].mkdir()
        paths['templates'].mkdir()
        
        # Create config
        config_path = paths['site'] / "config.toml"
        config_path.write_text(sample_config_toml)
        
        # Create basic templates using data from jinja_env_with_templates fixture pattern
        base_template = paths['templates'] / "base.html"
        base_template.write_text("""<!DOCTYPE html>
<html>
<head><title>{{ site.title }}</title></head>
<body>{% block content %}{% endblock %}</body>
</html>""")
        
        index_template = paths['templates'] / "index.html"
        index_template.write_text("""{% extends "base.html" %}
{% block content %}
<h1>{{ page.title }}</h1>
<ul>
{% for post in page.posts %}
<li>{{ post.title }} - {{ post.date }}</li>
{% endfor %}
</ul>
{% endblock %}""")
        
        site = Site(paths['site'])
        
        # Ensure output directory exists
        site.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create sample posts data
        posts = [
            {
                'title': 'Post 1',
                'date': datetime(2024, 1, 1),
                'content': 'Content 1'
            },
            {
                'title': 'Post 2',
                'date': datetime(2024, 1, 2),
                'content': 'Content 2'
            }
        ]
        
        pages = []
        
        site._generate_index(posts, pages)
        
        # Check index was created
        index_file = site.output_dir / "index.html"
        assert index_file.exists()
        
        index_content = index_file.read_text()
        assert "Post 1" in index_content
        assert "Post 2" in index_content
    
    def test_site_generate_format_wrapper(self, site_structure_paths, sample_config_toml, tmp_path):
        """Test the _generate_format wrapper method."""
        # Create site structure using fixture
        paths = site_structure_paths
        paths['site'].mkdir()
        paths['content'].mkdir()
        paths['templates'].mkdir()
        
        # Create config
        config_path = paths['site'] / "config.toml"
        config_path.write_text(sample_config_toml)
        
        # Create basic template
        template_path = paths['templates'] / "default.html"
        template_path.write_text("""<!DOCTYPE html>
<html>
<head><title>{{ page.title }}</title></head>
<body>{{ page.content | safe }}</body>
</html>""")
        
        # Create test markdown
        test_md = tmp_path / "test.md"
        test_md.write_text("# Test\n\nContent")
        
        site = Site(paths['site'])
        
        page_data = {
            'title': 'Test Page',
            'content': '<h1>Test</h1><p>Content</p>',
            'layout': 'default'
        }
        
        output_base = tmp_path / "output"
        
        # Test HTML format
        site._generate_format(page_data, test_md, output_base, 'html')
        
        html_file = output_base.with_suffix('.html')
        assert html_file.exists()
        
        html_content = html_file.read_text()
        assert '<title>Test Page</title>' in html_content
        assert '<h1>Test</h1>' in html_content
    
    def test_site_process_content_wrapper(self, site_structure_paths, sample_config_toml):
        """Test the _process_content wrapper method."""
        # Create site structure using fixture
        paths = site_structure_paths
        paths['site'].mkdir()
        paths['content'].mkdir()
        paths['templates'].mkdir()
        
        # Create config
        config_path = paths['site'] / "config.toml"
        config_path.write_text(sample_config_toml)
        
        site = Site(paths['site'])
        
        # Create test file
        test_file = paths['content'] / "test.md"
        test_file.write_text("""---
title: Test Page
layout: custom
---

# Header

Content here.
""")
        
        page_data = site._process_content(test_file)
        
        assert page_data['title'] == "Test Page"
        assert page_data['layout'] == "custom"
        assert "<h1>Header</h1>" in page_data['content']