"""Content processing and parsing for ctxssg."""

import re
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import frontmatter
import pypandoc
from bs4 import BeautifulSoup


class ContentProcessor:
    """Handles markdown processing and content structure parsing."""
    
    def __init__(self, content_dir: Path):
        self.content_dir = content_dir
    
    def process_content(self, file_path: Path) -> Dict[str, Any]:
        """Process a markdown file with frontmatter."""
        post = frontmatter.load(file_path)
        
        # Convert markdown to HTML using pandoc
        try:
            html_content = pypandoc.convert_text(
                post.content,
                'html',
                format='markdown',
                extra_args=['--highlight-style=pygments']
            )
            
            # Remove automatically generated header IDs for cleaner HTML
            html_content = re.sub(r'(<h[1-6])\s+id="[^"]*"', r'\1', html_content)
        except OSError as e:
            if "pandoc" in str(e).lower():
                raise RuntimeError("Pandoc is not installed. Please install pandoc: https://pandoc.org/installing.html")
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to convert markdown to HTML: {e}")
        
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
    
    def parse_content_structure(self, html_content: str) -> Dict[str, Any]:
        """Parse HTML content into structured data for templating."""
        soup = BeautifulSoup(html_content, 'html.parser')
        sections: List[Dict[str, Any]] = []
        current_section = None
        
        for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'pre', 'blockquote']):
            if element.name.startswith('h'):
                # Start new section
                if current_section:
                    sections.append(current_section)
                
                level = int(element.name[1])
                section_id = element.get('id') or self._generate_id(element.get_text())
                
                current_section = {
                    'id': section_id,
                    'level': level,
                    'title': element.get_text().strip(),
                    'content': []
                }
            elif current_section:
                # Add content to current section
                if element.name == 'p':
                    current_section['content'].append({
                        'type': 'paragraph',
                        'text': self._clean_html(element)
                    })
                elif element.name in ['ul', 'ol']:
                    list_items = [self._clean_html(li) for li in element.find_all('li')]
                    current_section['content'].append({
                        'type': 'list',
                        'list_type': 'ordered' if element.name == 'ol' else 'bullet',
                        'items': list_items
                    })
                elif element.name == 'pre':
                    code_element = element.find('code')
                    if code_element:
                        language = None
                        if code_element.get('class'):
                            for cls in code_element.get('class'):
                                if cls.startswith('sourceCode'):
                                    continue
                                if cls.startswith('language-'):
                                    language = cls[9:]
                                else:
                                    language = cls
                                break
                        
                        current_section['content'].append({
                            'type': 'code',
                            'language': language,
                            'text': code_element.get_text()
                        })
                    else:
                        current_section['content'].append({
                            'type': 'code',
                            'language': None,
                            'text': element.get_text()
                        })
                elif element.name == 'blockquote':
                    current_section['content'].append({
                        'type': 'quote',
                        'text': self._clean_html(element)
                    })
        
        # Add the last section
        if current_section:
            sections.append(current_section)
        
        # If no sections were found, create a default section
        if not sections:
            sections.append({
                'id': 'content',
                'level': 1,
                'title': 'Content',
                'content': [{
                    'type': 'paragraph',
                    'text': self._clean_html(soup)
                }]
            })
        
        return {'sections': sections}
    
    def _generate_id(self, text: str) -> str:
        """Generate a URL-safe ID from text."""
        # Convert to lowercase and replace spaces/special chars with hyphens
        id_text = re.sub(r'[^\w\s-]', '', text.lower())
        id_text = re.sub(r'[-\s]+', '-', id_text)
        return id_text.strip('-')
    
    def _clean_html(self, element) -> str:
        """Extract clean text from HTML element, preserving basic formatting."""
        if hasattr(element, 'get_text'):
            return element.get_text().strip()
        return str(element).strip()