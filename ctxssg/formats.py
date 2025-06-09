"""Format generation for different output types."""

from pathlib import Path
from typing import Dict, Any
import frontmatter
import pypandoc
from jinja2 import Environment


class FormatGenerator:
    """Handles generation of different output formats."""
    
    def __init__(self, jinja_env: Environment, config: Dict[str, Any]):
        self.env = jinja_env
        self.config = config
    
    def generate_format(self, page_data: Dict[str, Any], source_file: Path, 
                       output_base: Path, fmt: str, content_processor) -> None:
        """Generate output file for a specific format using templates."""
        # Ensure output directory exists
        output_base.parent.mkdir(parents=True, exist_ok=True)
        
        if fmt == 'html':
            # HTML generation will be handled by the main Site class
            raise ValueError("HTML format should be handled by Site class")
        
        elif fmt in ['plain', 'txt']:
            self._generate_plain_text(page_data, source_file, output_base)
        
        elif fmt == 'xml':
            self._generate_xml(page_data, source_file, output_base, content_processor)
        
        elif fmt == 'json':
            self._generate_json(page_data, source_file, output_base, content_processor)
        
        else:
            # Generic pandoc conversion for other formats
            self._generate_pandoc_format(source_file, output_base, fmt)
    
    def _generate_plain_text(self, page_data: Dict[str, Any], source_file: Path, 
                           output_base: Path) -> None:
        """Generate plain text format using templates."""
        post = frontmatter.load(source_file)
        
        # Get format-specific configuration
        plain_config = self.config.get('format_config', {}).get('plain', {})
        wrap_width = plain_config.get('wrap_width', 0)  # 0 means no wrap
        include_metadata = plain_config.get('include_metadata', True)
        
        # Generate plain text content using pandoc
        try:
            extra_args = []
            if wrap_width > 0:
                extra_args.append('--wrap=auto')  # Pandoc expects 'auto', 'none', or 'preserve'
            else:
                extra_args.append('--wrap=none')
            
            plain_content = pypandoc.convert_text(
                post.content,
                'plain',
                format='markdown',
                extra_args=extra_args
            )
        except OSError as e:
            if "pandoc" in str(e).lower():
                raise RuntimeError("Pandoc is not installed. Please install pandoc: https://pandoc.org/installing.html")
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to convert markdown to plain text: {e}")
        
        # Prepare metadata for template
        metadata = {}
        if include_metadata:
            for key, value in page_data.items():
                if key not in ['content', 'url'] and value is not None:
                    if hasattr(value, 'isoformat'):
                        value = value.isoformat()
                    metadata[key] = value
        
        # Render using template
        template = self.env.get_template('formats/document.txt.j2')
        content = template.render(
            metadata=metadata if include_metadata else {},
            plain_content=plain_content,
            include_metadata=include_metadata
        )
        
        output_path = output_base.with_suffix('.txt')
        output_path.write_text(content)
    
    def _generate_xml(self, page_data: Dict[str, Any], source_file: Path, 
                     output_base: Path, content_processor) -> None:
        """Generate XML format using templates."""
        # Get format-specific configuration
        xml_config = self.config.get('format_config', {}).get('xml', {})
        include_namespaces = xml_config.get('include_namespaces', False)
        
        # Parse HTML content into structured format
        content_structure = content_processor.parse_content_structure(page_data['content'])
        
        # Prepare metadata for template
        metadata = {}
        for key, value in page_data.items():
            if key not in ['content', 'url'] and value is not None:
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                metadata[key] = value
        
        # Render using template
        template = self.env.get_template('formats/document.xml.j2')
        content = template.render(
            metadata=metadata,
            content=content_structure,
            include_namespaces=include_namespaces
        )
        
        output_path = output_base.with_suffix('.xml')
        output_path.write_text(content)
    
    def _generate_json(self, page_data: Dict[str, Any], source_file: Path, 
                      output_base: Path, content_processor) -> None:
        """Generate JSON format using templates."""
        # Get format-specific configuration
        json_config = self.config.get('format_config', {}).get('json', {})
        pretty_print = json_config.get('pretty_print', True)
        include_metadata = json_config.get('include_metadata', True)
        
        # Parse HTML content into structured format
        content_structure = content_processor.parse_content_structure(page_data['content'])
        
        # Prepare metadata for template
        metadata = {}
        if include_metadata:
            for key, value in page_data.items():
                if key not in ['content', 'url'] and value is not None:
                    if hasattr(value, 'isoformat'):
                        value = value.isoformat()
                    metadata[key] = value
        
        # Render using template
        template = self.env.get_template('formats/document.json.j2')
        content = template.render(
            metadata=metadata if include_metadata else {},
            content=content_structure,
            pretty_print=pretty_print,
            include_metadata=include_metadata
        )
        
        output_path = output_base.with_suffix('.json')
        output_path.write_text(content)
    
    def _generate_pandoc_format(self, source_file: Path, output_base: Path, fmt: str) -> None:
        """Generate format using direct pandoc conversion."""
        post = frontmatter.load(source_file)
        try:
            converted_content = pypandoc.convert_text(
                post.content,
                fmt,
                format='markdown'
            )
        except OSError as e:
            if "pandoc" in str(e).lower():
                raise RuntimeError("Pandoc is not installed. Please install pandoc: https://pandoc.org/installing.html")
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to convert markdown to {fmt} format: {e}")
        
        output_path = output_base.with_suffix(f'.{fmt}')
        output_path.write_text(converted_content)