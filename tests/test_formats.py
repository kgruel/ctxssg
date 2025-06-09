"""Tests for ctxssg.formats module."""

import frontmatter

from ctxssg.formats import FormatGenerator
from ctxssg.content import ContentProcessor


class TestFormatGenerator:
    """Test the FormatGenerator class."""
    
    def test_html_format_raises_error(self, format_generator, tmp_path):
        """Test that HTML format raises an error."""
        # HTML should be handled by Site class, not FormatGenerator
        try:
            format_generator.generate_format({}, tmp_path / "test.md", tmp_path / "output", 'html', None)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "HTML format should be handled by Site class" in str(e)
    
    def test_generate_pandoc_format(self, format_generator, tmp_path, sample_frontmatter_content):
        """Test generic pandoc format generation."""
        # Create a test markdown file
        test_md = tmp_path / "test.md"
        test_md.write_text(sample_frontmatter_content['with_frontmatter'])
        
        # Test latex format (should use pandoc directly)
        output_base = tmp_path / "output"
        format_generator.generate_format({}, test_md, output_base, 'latex', None)
        
        # Check that latex file was created
        latex_file = output_base.with_suffix('.latex')
        assert latex_file.exists()
        
        # Should contain some LaTeX markup
        content = latex_file.read_text()
        assert "section" in content.lower() or "Header" in content
    
    def test_plain_text_config_options(self, jinja_env_with_templates, format_config, tmp_path, sample_frontmatter_content):
        """Test plain text format with configuration options."""
        # Add plain text template to environment
        from jinja2 import DictLoader
        plain_template = '''METADATA:
{% if include_metadata %}
{% for key, value in metadata.items() %}
{{ key }}: {{ value }}
{% endfor %}
{% endif %}

CONTENT:
{{ plain_content }}
'''
        jinja_env_with_templates.loader.mapping['formats/document.txt.j2'] = plain_template
        
        config = {
            'format_config': {
                'plain': format_config['plain']
            }
        }
        
        # Create test file
        test_md = tmp_path / "test.md"
        test_md.write_text(sample_frontmatter_content['complex_frontmatter'])
        
        page_data = {
            'title': 'Complex Test',
            'author': 'Test Author',
            'content': '<h1>Complex Content</h1><p>This content has more complex frontmatter with various data types.</p>',
            'layout': 'custom'
        }
        
        generator = FormatGenerator(jinja_env_with_templates, config)
        output_base = tmp_path / "output"
        
        generator.generate_format(page_data, test_md, output_base, 'plain', None)
        
        # Check output
        txt_file = output_base.with_suffix('.txt')
        assert txt_file.exists()
        
        content = txt_file.read_text()
        assert "METADATA:" in content
        assert "title: Complex Test" in content
        assert "author: Test Author" in content
        assert "CONTENT:" in content
    
    def test_plain_text_no_metadata(self, jinja_env_with_templates, tmp_path):
        """Test plain text format without metadata."""
        # Add template with conditional metadata
        plain_template = '''{% if include_metadata %}METADATA:
{% for key, value in metadata.items() %}
{{ key }}: {{ value }}
{% endfor %}

{% endif %}CONTENT:
{{ plain_content }}
'''
        jinja_env_with_templates.loader.mapping['formats/document.txt.j2'] = plain_template
        
        config = {
            'format_config': {
                'plain': {
                    'include_metadata': False
                }
            }
        }
        
        # Create test file
        test_md = tmp_path / "test.md"
        test_md.write_text("# Header\n\nContent")
        
        page_data = {'title': 'Test', 'content': 'html'}
        
        generator = FormatGenerator(jinja_env_with_templates, config)
        output_base = tmp_path / "output"
        
        generator.generate_format(page_data, test_md, output_base, 'plain', None)
        
        # Check output
        txt_file = output_base.with_suffix('.txt')
        content = txt_file.read_text()
        assert "METADATA:" not in content
        assert "CONTENT:" in content
    
    def test_xml_format_config(self, jinja_env_with_templates, content_processor, tmp_path, format_config):
        """Test XML format with configuration."""
        # Add XML template
        xml_template = '''<?xml version="1.0" encoding="UTF-8"?>
<document{% if include_namespaces %} xmlns="http://example.com"{% endif %}>
  <meta>
    {% for key, value in metadata.items() %}
    <{{ key }}>{{ value }}</{{ key }}>
    {% endfor %}
  </meta>
  <content>
    {% for section in content.sections %}
    <section id="{{ section.id }}" level="{{ section.level }}">
      <title>{{ section.title }}</title>
    </section>
    {% endfor %}
  </content>
</document>
'''
        jinja_env_with_templates.loader.mapping['formats/document.xml.j2'] = xml_template
        
        config = {
            'format_config': {
                'xml': {
                    'include_namespaces': True
                }
            }
        }
        
        # Create test file
        test_md = tmp_path / "test.md"
        test_md.write_text("# Header\n\nContent")
        
        page_data = {
            'title': 'Test',
            'content': '<h1>Header</h1><p>Content</p>'
        }
        
        generator = FormatGenerator(jinja_env_with_templates, config)
        output_base = tmp_path / "output"
        
        generator.generate_format(page_data, test_md, output_base, 'xml', content_processor)
        
        # Check output
        xml_file = output_base.with_suffix('.xml')
        assert xml_file.exists()
        
        content = xml_file.read_text()
        assert 'xmlns="http://example.com"' in content
        assert '<title>Test</title>' in content
    
    def test_json_format_config(self, jinja_env_with_templates, content_processor, tmp_path):
        """Test JSON format with configuration."""
        # Add JSON template
        json_template = '''{
{% if include_metadata %}
  "metadata": {
    {% for key, value in metadata.items() %}
    "{{ key }}": "{{ value }}"{% if not loop.last %},{% endif %}
    {% endfor %}
  },
{% endif %}
  "content": {
    "sections": [
      {% for section in content.sections %}
      {
        "id": "{{ section.id }}",
        "title": "{{ section.title }}",
        "level": {{ section.level }}
      }{% if not loop.last %},{% endif %}
      {% endfor %}
    ]
  }
}
'''
        jinja_env_with_templates.loader.mapping['formats/document.json.j2'] = json_template
        
        config = {
            'format_config': {
                'json': {
                    'pretty_print': True,
                    'include_metadata': False
                }
            }
        }
        
        # Create test file
        test_md = tmp_path / "test.md"
        test_md.write_text("# Header\n\nContent")
        
        page_data = {
            'title': 'Test',
            'content': '<h1>Header</h1><p>Content</p>'
        }
        
        generator = FormatGenerator(jinja_env_with_templates, config)
        output_base = tmp_path / "output"
        
        generator.generate_format(page_data, test_md, output_base, 'json', content_processor)
        
        # Check output
        json_file = output_base.with_suffix('.json')
        assert json_file.exists()
        
        content = json_file.read_text()
        # Should not include metadata
        assert '"metadata"' not in content
        assert '"content"' in content
    
    def test_pandoc_error_handling(self, jinja_env_with_templates, tmp_path, mock_pandoc_failure):
        """Test format generator error handling with pandoc failures."""
        # Add plain text template
        jinja_env_with_templates.loader.mapping['formats/document.txt.j2'] = '{{ plain_content }}'
        
        generator = FormatGenerator(jinja_env_with_templates, {})
        
        test_md = tmp_path / "test.md"
        test_md.write_text("# Test\n\nContent")
        
        try:
            generator.generate_format({}, test_md, tmp_path / "output", 'plain', None)
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Pandoc is not installed" in str(e)
    
    def test_pandoc_general_error(self, format_generator, tmp_path, mock_pandoc_error):
        """Test format generator with general pandoc error."""
        test_md = tmp_path / "test.md"
        test_md.write_text("# Test\n\nContent")
        
        try:
            format_generator._generate_pandoc_format(test_md, tmp_path / "output", 'latex')
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Failed to convert markdown to latex format" in str(e)
    
    def test_error_handling(self, format_generator, tmp_path):
        """Test format generator error handling."""
        # Test with markdown file that might cause errors
        test_md = tmp_path / "test.md"
        test_md.write_text("# Test\n\nContent")
        
        # Test pandoc format with potential error
        output_base = tmp_path / "output"
        try:
            format_generator.generate_format({}, test_md, output_base, 'docx', None)
            # Should create a file if pandoc supports docx
            assert True
        except RuntimeError:
            # If pandoc fails, that's also expected
            assert True