"""Tests for ctxssg.content module."""

from bs4 import BeautifulSoup

from ctxssg.content import ContentProcessor


class TestContentProcessor:
    """Test the ContentProcessor class."""
    
    def test_process_content_basic(self, content_processor, sample_frontmatter_content):
        """Test basic content processing."""
        test_file = content_processor.content_dir / "test.md"
        test_file.write_text(sample_frontmatter_content['with_frontmatter'])
        
        page_data = content_processor.process_content(test_file)
        
        assert page_data['title'] == "Test Page"
        assert page_data['layout'] == "default"
        assert page_data['url'] == "/test.html"
        assert "<h1>Content Header</h1>" in page_data['content']
    
    def test_process_content_no_frontmatter(self, content_processor, sample_frontmatter_content):
        """Test processing content without frontmatter."""
        test_file = content_processor.content_dir / "simple.md"
        test_file.write_text(sample_frontmatter_content['without_frontmatter'])
        
        page_data = content_processor.process_content(test_file)
        
        assert page_data['title'] == "simple"
        assert page_data['layout'] == "default"
        assert "<h1>Simple Header</h1>" in page_data['content']
    
    def test_get_url_subdirectory(self, content_dir):
        """Test URL generation for subdirectory files."""
        posts_dir = content_dir / "posts"
        posts_dir.mkdir()
        
        processor = ContentProcessor(content_dir)
        
        test_file = posts_dir / "my-post.md"
        test_file.write_text("# Post")
        
        url = processor._get_url(test_file)
        assert url == "/posts/my-post.html"
    
    def test_parse_content_structure_empty(self, content_processor):
        """Test parsing empty content structure."""
        # Empty HTML
        structure = content_processor.parse_content_structure("")
        
        assert len(structure['sections']) == 1
        assert structure['sections'][0]['id'] == 'content'
        assert structure['sections'][0]['title'] == 'Content'
    
    def test_parse_content_structure_no_headers(self, content_processor):
        """Test parsing content with no headers."""
        html = "<p>Just a paragraph</p><p>Another paragraph</p>"
        structure = content_processor.parse_content_structure(html)
        
        assert len(structure['sections']) == 1
        assert structure['sections'][0]['id'] == 'content'
        assert structure['sections'][0]['title'] == 'Content'
    
    def test_generate_id_special_chars(self, content_processor):
        """Test ID generation with special characters."""
        # Test various special characters
        test_cases = [
            ("Hello World!", "hello-world"),
            ("C++ Programming", "c-programming"),
            ("Multi   Spaces", "multi-spaces"),
            ("---Dashes---", "dashes"),
            ("", ""),
        ]
        
        for input_text, expected in test_cases:
            result = content_processor._generate_id(input_text)
            assert result == expected
    
    def test_clean_html_with_tags(self, content_processor):
        """Test HTML cleaning with various elements."""
        # Test with BeautifulSoup element
        html = "<p>Text with <strong>bold</strong> and <em>italic</em></p>"
        soup = BeautifulSoup(html, 'html.parser')
        p_element = soup.find('p')
        
        cleaned = content_processor._clean_html(p_element)
        assert cleaned == "Text with bold and italic"
        
        # Test with string
        cleaned_str = content_processor._clean_html("   Plain text   ")
        assert cleaned_str == "Plain text"
    
    def test_code_class_detection(self, content_processor):
        """Test code block language detection in content processor."""
        # Test HTML with code blocks having different class formats
        html_content = '''
        <h1>Test</h1>
        <pre><code class="language-python">print("hello")</code></pre>
        <pre><code class="sourceCode python">def foo(): pass</code></pre>
        <pre><code class="javascript">console.log("test")</code></pre>
        <pre><code>no language</code></pre>
        <pre>no code element</pre>
        '''
        
        structure = content_processor.parse_content_structure(html_content)
        
        # Should have one section with multiple code blocks
        assert len(structure['sections']) >= 1
        
        # Find the code content items
        content_items = structure['sections'][0]['content']
        code_items = [item for item in content_items if item['type'] == 'code']
        
        # Should detect various language formats
        languages = [item.get('language') for item in code_items]
        assert 'python' in languages
        assert 'javascript' in languages
        assert None in languages  # For code without language
    
    def test_pandoc_error_handling(self, content_processor, mock_pandoc_failure):
        """Test content processor error handling with pandoc failures."""
        test_file = content_processor.content_dir / "test.md"
        test_file.write_text("# Test\n\nContent")
        
        try:
            content_processor.process_content(test_file)
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Pandoc is not installed" in str(e)
    
    def test_general_pandoc_error(self, content_processor, mock_pandoc_error):
        """Test content processor with general pandoc error."""
        test_file = content_processor.content_dir / "test.md"
        test_file.write_text("# Test\n\nContent")
        
        try:
            content_processor.process_content(test_file)
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Failed to convert markdown to HTML" in str(e)
    
    def test_error_handling(self, content_processor):
        """Test content processor error handling."""
        # Test with content that might cause pandoc errors
        test_file = content_processor.content_dir / "test.md"
        test_file.write_text("# Test\n\nContent")
        
        # This should work normally
        page_data = content_processor.process_content(test_file)
        assert page_data['title'] == "test"