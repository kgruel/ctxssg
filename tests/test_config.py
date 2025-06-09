"""Tests for ctxssg.config module."""

from ctxssg.config import ConfigLoader


class TestConfigLoader:
    """Test the ConfigLoader class."""
    
    def test_load_toml_config(self, tmp_path):
        """Test loading TOML configuration."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("""
[site]
title = "Test Site"
url = "https://example.com"

[build]
output_dir = "dist"
output_formats = ["html", "json"]

[templates]
default_layout = "custom"

[formats]
[formats.json]
pretty_print = false

[css]
primary_color = "#123456"
""")
        
        loader = ConfigLoader(tmp_path)
        config = loader.load_config()
        
        assert config['title'] == "Test Site"
        assert config['url'] == "https://example.com"
        assert config['output_dir'] == "dist"
        assert config['output_formats'] == ["html", "json"]
        assert config['template_config']['default_layout'] == "custom"
        assert config['format_config']['json']['pretty_print'] == False
        assert config['css']['primary_color'] == "#123456"
    
    def test_load_yaml_config(self, tmp_path):
        """Test loading YAML configuration (legacy)."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
title: "YAML Site"
output_dir: "yaml_site"
output_formats:
  - html
  - plain
description: "A YAML configured site"
""")
        
        loader = ConfigLoader(tmp_path)
        config = loader.load_config()
        
        assert config['title'] == "YAML Site"
        assert config['output_dir'] == "yaml_site"
        assert config['output_formats'] == ["html", "plain"]
        assert config['description'] == "A YAML configured site"
    
    def test_load_default_config(self, tmp_path):
        """Test loading default configuration when no file exists."""
        loader = ConfigLoader(tmp_path)
        config = loader.load_config()
        
        assert config['title'] == 'My Site'
        assert config['output_dir'] == '_site'
        assert config['output_formats'] == ['html']
        assert config['url'] == 'http://localhost:8000'
    
    def test_toml_priority_over_yaml(self, tmp_path):
        """Test that TOML config takes priority over YAML."""
        # Create both files
        toml_path = tmp_path / "config.toml"
        yaml_path = tmp_path / "config.yaml"
        
        toml_path.write_text("""
[site]
title = "TOML Site"
""")
        
        yaml_path.write_text("""
title: "YAML Site"
""")
        
        loader = ConfigLoader(tmp_path)
        config = loader.load_config()
        
        # Should load TOML, not YAML
        assert config['title'] == "TOML Site"
    
    def test_normalize_flat_yaml_config(self, tmp_path):
        """Test normalizing flat YAML configuration."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
title: "Flat Config"
output_dir: "build"
template_config:
  custom_var: "value"
format_config:
  xml:
    include_namespaces: true
""")
        
        loader = ConfigLoader(tmp_path)
        config = loader.load_config()
        
        assert config['title'] == "Flat Config"
        assert config['template_config']['custom_var'] == "value"
        assert config['format_config']['xml']['include_namespaces'] == True
    
    def test_tomllib_import_fallback(self, tmp_path):
        """Test tomllib import fallback for older Python versions."""
        # Test that the tomllib/tomli import works
        config_path = tmp_path / "config.toml"
        config_path.write_text("""
[site]
title = "Test"
""")
        
        loader = ConfigLoader(tmp_path)
        config = loader.load_config()
        assert config['title'] == "Test"