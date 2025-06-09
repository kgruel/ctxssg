"""Integration tests for ctxssg."""

import tempfile
import shutil
from pathlib import Path

from ctxssg import Site, SiteGenerator


class TestSiteIntegration:
    """Integration tests for the Site class."""
    
    def setup_method(self):
        """Set up test site."""
        self.temp_dir = tempfile.mkdtemp()
        self.site_path = Path(self.temp_dir)
        SiteGenerator.init_site(self.site_path, "Test Site")
        self.site = Site(self.site_path)
    
    def teardown_method(self):
        """Clean up test site."""
        shutil.rmtree(self.temp_dir)
    
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