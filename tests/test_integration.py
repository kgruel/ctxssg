"""Integration tests for ctxssg."""

import tempfile
import shutil
from pathlib import Path

from ctxssg import Site, SiteGenerator


class TestSiteIntegration:
    """Integration tests for the Site class."""
    
    def test_multiple_format_build(self, site_with_tempdir):
        """Test building with multiple output formats including new clean formats."""
        # Set all output formats
        site_with_tempdir.config['output_formats'] = ['html', 'plain', 'xml', 'json']
        site_with_tempdir.build()
        
        # Check that all formats are generated
        assert (site_with_tempdir.output_dir / "about.html").exists()
        assert (site_with_tempdir.output_dir / "about.txt").exists()
        assert (site_with_tempdir.output_dir / "about.xml").exists()
        assert (site_with_tempdir.output_dir / "about.json").exists()
        
        # Verify enhanced plain text format
        txt_content = (site_with_tempdir.output_dir / "about.txt").read_text()
        assert "METADATA:" in txt_content
        assert "Title: About" in txt_content
        assert "CONTENT:" in txt_content
        assert "=" * 80 in txt_content
        assert "About This Site" in txt_content
        
        # Verify clean XML format (no DocBook namespaces)
        xml_content = (site_with_tempdir.output_dir / "about.xml").read_text()
        assert '<?xml version="1.0" encoding="UTF-8"?>' in xml_content
        assert "<document>" in xml_content
        assert "<meta>" in xml_content
        assert "<title>About</title>" in xml_content
        assert 'xmlns' not in xml_content  # No namespaces
        assert "<section id=" in xml_content
        assert "<paragraph>" in xml_content
        
        # Verify JSON format
        import json
        json_content = (site_with_tempdir.output_dir / "about.json").read_text()
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
    
    def test_xml_structure(self, site_with_tempdir, sample_markdown):
        """Test clean XML structure without DocBook."""
        # Create a test markdown with various elements
        test_md = site_with_tempdir.root / "content" / "test.md"
        test_md.write_text(sample_markdown)
        
        site_with_tempdir.config['output_formats'] = ['xml']
        site_with_tempdir.build()
        
        xml_content = (site_with_tempdir.output_dir / "test.xml").read_text()
        
        # Verify clean structure
        assert "<section id=\"test-header\" level=\"1\">" in xml_content
        assert "<section id=\"subheader\" level=\"2\">" in xml_content
        assert "<list type=\"bullet\">" in xml_content
        assert "<list type=\"ordered\">" in xml_content
        assert "<code" in xml_content
        assert "<quote>" in xml_content
        assert 'xmlns' not in xml_content  # No namespaces
    
    def test_json_structure(self, site_with_tempdir, sample_frontmatter_content):
        """Test JSON structure with all content types."""
        # Create test markdown with complex content
        test_md = site_with_tempdir.root / "content" / "complex.md"
        test_md.write_text(sample_frontmatter_content['complex_frontmatter'])
        
        site_with_tempdir.config['output_formats'] = ['json']
        site_with_tempdir.build()
        
        import json
        json_content = (site_with_tempdir.output_dir / "complex.json").read_text()
        data = json.loads(json_content)
        
        # Verify metadata structure
        assert data["metadata"]["title"] == "Complex Test"
        assert data["metadata"]["author"] == "Test Author"
        assert data["metadata"]["tags"] == ["test", "complex", "example"]
        
        # Verify content structure
        sections = data["content"]["sections"]
        assert len(sections) >= 1
        
        # Check for presence of content sections
        section_titles = [s.get("title", "") for s in sections]
        assert any("Complex Content" in title or "Header" in title for title in section_titles)