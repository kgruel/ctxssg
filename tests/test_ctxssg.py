import pytest
from pathlib import Path
import tempfile
import shutil
from click.testing import CliRunner

from ctxssg import Site, SiteGenerator
from ctxssg.cli import cli


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
        assert (site_path / "config.yaml").exists()
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


class TestSite:
    """Test the Site class."""
    
    def setup_method(self):
        """Set up test site."""
        self.temp_dir = tempfile.mkdtemp()
        self.site_path = Path(self.temp_dir)
        SiteGenerator.init_site(self.site_path, "Test Site")
        self.site = Site(self.site_path)
    
    def teardown_method(self):
        """Clean up test site."""
        shutil.rmtree(self.temp_dir)
    
    def test_load_config(self):
        """Test config loading."""
        assert self.site.config['title'] == "Test Site"
        assert self.site.config['output_dir'] == "_site"
    
    def test_build(self):
        """Test site building."""
        self.site.build()
        
        # Check output directory
        assert self.site.output_dir.exists()
        assert (self.site.output_dir / "index.html").exists()
        assert (self.site.output_dir / "about.html").exists()
        assert (self.site.output_dir / "posts" / "welcome.html").exists()
        assert (self.site.output_dir / "static" / "css" / "style.css").exists()
    
    def test_process_content(self):
        """Test markdown processing."""
        # Create a test markdown file
        test_md = self.site_path / "content" / "test.md"
        test_md.write_text("""---
title: Test Page
layout: default
---

# Test Header

This is a test paragraph with **bold** text.

```python
def hello():
    print("Hello, world!")
```
""")
        
        page_data = self.site._process_content(test_md)
        
        assert page_data['title'] == "Test Page"
        assert page_data['layout'] == "default"
        assert "<h1>Test Header</h1>" in page_data['content']
        assert "<strong>bold</strong>" in page_data['content']
        assert "hello()" in page_data['content']
    
    def test_multiple_format_build(self):
        """Test building with multiple output formats including new clean formats."""
        # Set all output formats
        self.site.config['output_formats'] = ['html', 'plain', 'xml', 'json']
        self.site.build()
        
        # Check that all formats are generated
        assert (self.site.output_dir / "about.html").exists()
        assert (self.site.output_dir / "about.txt").exists()
        assert (self.site.output_dir / "about.xml").exists()
        assert (self.site.output_dir / "about.json").exists()
        
        # Verify enhanced plain text format
        txt_content = (self.site.output_dir / "about.txt").read_text()
        assert "METADATA:" in txt_content
        assert "Title: About" in txt_content
        assert "CONTENT:" in txt_content
        assert "=" * 80 in txt_content
        assert "About This Site" in txt_content
        
        # Verify clean XML format (no DocBook namespaces)
        xml_content = (self.site.output_dir / "about.xml").read_text()
        assert '<?xml version="1.0" encoding="UTF-8"?>' in xml_content
        assert "<document>" in xml_content
        assert "<meta>" in xml_content
        assert "<title>About</title>" in xml_content
        assert 'xmlns' not in xml_content  # No namespaces
        assert "<section id=" in xml_content
        assert "<paragraph>" in xml_content
        
        # Verify JSON format
        import json
        json_content = (self.site.output_dir / "about.json").read_text()
        json_data = json.loads(json_content)
        
        assert "metadata" in json_data
        assert "content" in json_data
        assert json_data["metadata"]["title"] == "About"
        assert "sections" in json_data["content"]
        assert len(json_data["content"]["sections"]) >= 1
        
        # Check first section structure
        first_section = json_data["content"]["sections"][0]
        assert "id" in first_section
        assert "level" in first_section
        assert "title" in first_section
        assert "content" in first_section
        
    def test_xml_structure(self):
        """Test clean XML structure without DocBook."""
        # Create a test markdown with various elements
        test_md = self.site_path / "content" / "test.md"
        test_md.write_text("""---
title: Test Page
layout: default
---

# Main Header

This is a paragraph with **bold** text.

## Subheader

- Item 1
- Item 2

```python
def hello():
    print("Hello!")
```

> This is a quote

### Third Level

1. Ordered item 1
2. Ordered item 2
""")
        
        self.site.config['output_formats'] = ['xml']
        self.site.build()
        
        xml_content = (self.site.output_dir / "test.xml").read_text()
        
        # Verify clean structure
        assert "<section id=\"main-header\" level=\"1\">" in xml_content
        assert "<section id=\"subheader\" level=\"2\">" in xml_content
        assert "<section id=\"third-level\" level=\"3\">" in xml_content
        assert "<list type=\"bullet\">" in xml_content
        assert "<list type=\"ordered\">" in xml_content
        assert "<code" in xml_content
        assert "<quote>" in xml_content
        assert 'xmlns' not in xml_content  # No namespaces
        
    def test_json_structure(self):
        """Test JSON structure with all content types."""
        # Create test markdown with complex content
        test_md = self.site_path / "content" / "complex.md"
        test_md.write_text("""---
title: Complex Test
author: Test Author
tags: [test, example]
---

# Header One

Paragraph text here.

## Code Section

```javascript
function test() {
    return "hello";
}
```

## List Section

- Bullet one
- Bullet two

## Quote Section

> This is a quoted text.
""")
        
        self.site.config['output_formats'] = ['json']
        self.site.build()
        
        import json
        json_content = (self.site.output_dir / "complex.json").read_text()
        data = json.loads(json_content)
        
        # Verify metadata structure
        assert data["metadata"]["title"] == "Complex Test"
        assert data["metadata"]["author"] == "Test Author"
        assert data["metadata"]["tags"] == ["test", "example"]
        
        # Verify content structure
        sections = data["content"]["sections"]
        assert len(sections) >= 3
        
        # Find code section
        code_section = next((s for s in sections if s["title"] == "Code Section"), None)
        assert code_section is not None
        code_content = next((c for c in code_section["content"] if c["type"] == "code"), None)
        assert code_content is not None
        assert code_content["language"] == "javascript"
        assert "function test()" in code_content["text"]
        
        # Find list section
        list_section = next((s for s in sections if s["title"] == "List Section"), None)
        assert list_section is not None
        list_content = next((c for c in list_section["content"] if c["type"] == "list"), None)
        assert list_content is not None
        assert list_content["style"] == "bullet"
        assert "Bullet one" in list_content["items"]
        
        # Find quote section
        quote_section = next((s for s in sections if s["title"] == "Quote Section"), None)
        assert quote_section is not None
        quote_content = next((c for c in quote_section["content"] if c["type"] == "quote"), None)
        assert quote_content is not None
        assert "quoted text" in quote_content["text"]


class TestCLI:
    """Test CLI commands."""
    
    def test_version(self):
        """Test version command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output.lower()
    
    def test_init_command(self, tmp_path):
        """Test the init command."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ['init', 'my_site', '--title', 'My Test Site'])
            
            assert result.exit_code == 0
            assert "Site initialized successfully!" in result.output
            assert Path("my_site/config.yaml").exists()
    
    def test_build_command(self, tmp_path):
        """Test the build command."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # First init a site
            runner.invoke(cli, ['init', '.'])
            
            # Then build it
            result = runner.invoke(cli, ['build'])
            
            assert result.exit_code == 0
            assert "Site built successfully" in result.output
            assert Path("_site/index.html").exists()
    
    def test_new_command(self, tmp_path):
        """Test the new command."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # First init a site
            runner.invoke(cli, ['init', '.'])
            
            # Create a new post
            result = runner.invoke(cli, ['new', 'My First Post'])
            
            assert result.exit_code == 0
            assert "Created post:" in result.output
            
            # Check that the file was created
            posts_dir = Path("content/posts")
            assert any(f.name.endswith("-my-first-post.md") for f in posts_dir.glob("*.md"))
    
    def test_build_no_config(self, tmp_path):
        """Test build command without config."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ['build'])
            
            assert result.exit_code == 1
            assert "No config.yaml found" in result.output
    
    def test_build_with_formats(self, tmp_path):
        """Test build command with specific formats."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # First init a site
            runner.invoke(cli, ['init', '.'])
            
            # Build with specific formats
            result = runner.invoke(cli, ['build', '--formats', 'json', '--formats', 'xml'])
            
            assert result.exit_code == 0
            assert "Output formats: json, xml" in result.output
            assert "Site built successfully" in result.output
            
            # Check that only specified formats were created
            assert Path("_site/about.json").exists()
            assert Path("_site/about.xml").exists()
            assert not Path("_site/about.txt").exists()  # Plain not specified
    
    def test_convert_command(self, tmp_path):
        """Test the convert command."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create a test markdown file
            test_md = Path("test.md")
            test_md.write_text("""---
title: Test Document
author: Test User
---

# Test Header

This is test content.
""")
            
            # Convert to multiple formats
            result = runner.invoke(cli, ['convert', 'test.md', '--formats', 'json', '--formats', 'xml'])
            
            assert result.exit_code == 0
            assert "Converting test.md..." in result.output
            assert "test.json" in result.output
            assert "test.xml" in result.output
            
            # Verify output files exist
            assert Path("test.json").exists()
            assert Path("test.xml").exists()
            
            # Verify JSON content
            import json
            json_data = json.loads(Path("test.json").read_text())
            assert json_data["metadata"]["title"] == "Test Document"
            assert json_data["metadata"]["author"] == "Test User"