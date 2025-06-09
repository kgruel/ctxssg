"""Tests for ctxssg.cli module."""

from pathlib import Path
from watchdog.events import FileModifiedEvent, DirModifiedEvent

from ctxssg.cli import cli, RebuildHandler
from ctxssg.generator import Site


class TestCLI:
    """Test CLI commands."""
    
    def test_version(self, cli_runner):
        """Test version command."""
        result = cli_runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output.lower()
    
    def test_init_command(self, cli_runner, tmp_path):
        """Test the init command."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            result = cli_runner.invoke(cli, ['init', 'my_site', '--title', 'My Test Site'])
            
            assert result.exit_code == 0
            assert "Site initialized successfully!" in result.output
            assert Path("my_site/config.toml").exists()
    
    def test_init_current_directory(self, cli_runner, tmp_path):
        """Test init command in current directory."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            result = cli_runner.invoke(cli, ['init', '.', '--title', 'Test Site'])
            
            assert result.exit_code == 0
            assert Path("config.toml").exists()
    
    def test_init_non_empty_directory_refuse(self, cli_runner, tmp_path):
        """Test init command in non-empty directory with refusal."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Create a file to make directory non-empty
            Path("existing.txt").write_text("content")
            
            # Refuse when prompted
            result = cli_runner.invoke(cli, ['init', '.'], input='n\n')
            
            assert result.exit_code == 0
            assert not Path("config.toml").exists()
    
    def test_init_non_empty_directory_accept(self, cli_runner, tmp_path):
        """Test init command in non-empty directory with acceptance."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Create a file to make directory non-empty
            Path("existing.txt").write_text("content")
            
            # Accept when prompted
            result = cli_runner.invoke(cli, ['init', '.'], input='y\n')
            
            assert result.exit_code == 0
            assert Path("config.toml").exists()
    
    def test_build_command(self, cli_runner, tmp_path):
        """Test the build command."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # First init a site
            cli_runner.invoke(cli, ['init', '.'])
            
            # Then build it
            result = cli_runner.invoke(cli, ['build'])
            
            assert result.exit_code == 0
            assert "Site built successfully" in result.output
            assert Path("_site/index.html").exists()
    
    def test_new_command(self, cli_runner, tmp_path):
        """Test the new command."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # First init a site
            cli_runner.invoke(cli, ['init', '.'])
            
            # Create a new post
            result = cli_runner.invoke(cli, ['new', 'My First Post'])
            
            assert result.exit_code == 0
            assert "Created post:" in result.output
            
            # Check that the file was created
            posts_dir = Path("content/posts")
            assert any(f.name.endswith("-my-first-post.md") for f in posts_dir.glob("*.md"))
    
    def test_new_page_command(self, cli_runner, tmp_path):
        """Test the new command for pages."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # First init a site
            cli_runner.invoke(cli, ['init', '.'])
            
            # Create a new page
            result = cli_runner.invoke(cli, ['new', 'My New Page', '--type', 'page'])
            
            assert result.exit_code == 0
            assert "Created page:" in result.output
            
            # Check that the file was created
            assert Path("content/my-new-page.md").exists()
    
    def test_new_no_config(self, cli_runner, tmp_path):
        """Test new command without config."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            result = cli_runner.invoke(cli, ['new', 'Test Post'])
            
            assert result.exit_code == 1
            assert "No config.toml or config.yaml found" in result.output
    
    def test_new_existing_file(self, cli_runner, tmp_path):
        """Test new command with existing file."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # First init a site
            cli_runner.invoke(cli, ['init', '.'])
            
            # Create first post
            cli_runner.invoke(cli, ['new', 'Test Post'])
            
            # Try to create same post again
            result = cli_runner.invoke(cli, ['new', 'Test Post'])
            
            assert result.exit_code == 1
            assert "already exists" in result.output
    
    def test_build_no_config(self, cli_runner, tmp_path):
        """Test build command without config."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            result = cli_runner.invoke(cli, ['build'])
            
            assert result.exit_code == 1
            assert "No config.toml or config.yaml found" in result.output
    
    def test_build_with_formats(self, cli_runner, tmp_path):
        """Test build command with specific formats."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # First init a site
            cli_runner.invoke(cli, ['init', '.'])
            
            # Build with specific formats
            result = cli_runner.invoke(cli, ['build', '--formats', 'json', '--formats', 'xml'])
            
            assert result.exit_code == 0
            assert "Output formats: json, xml" in result.output
            assert "Site built successfully" in result.output
            
            # Check that only specified formats were created
            assert Path("_site/about.json").exists()
            assert Path("_site/about.xml").exists()
            assert not Path("_site/about.txt").exists()  # Plain not specified
    
    def test_convert_command(self, cli_runner, tmp_path, sample_frontmatter_content):
        """Test the convert command."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Create a test markdown file using fixture
            test_md = Path("test.md")
            test_md.write_text(sample_frontmatter_content['with_frontmatter'])
            
            # Convert to multiple formats
            result = cli_runner.invoke(cli, ['convert', 'test.md', '--formats', 'json', '--formats', 'xml'])
            
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
            assert json_data["metadata"]["title"] == "Test Page"
            assert json_data["metadata"]["author"] == "Test Author"
    
    def test_convert_with_output_dir(self, cli_runner, tmp_path):
        """Test convert command with output directory."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Create a test markdown file
            test_md = Path("test.md")
            test_md.write_text("""---
title: Test Document
---

Content here.
""")
            
            # Convert with output directory
            result = cli_runner.invoke(cli, ['convert', 'test.md', '--output-dir', 'output', '--formats', 'json'])
            
            assert result.exit_code == 0
            assert Path("output/test.json").exists()
    
    def test_doctor_command(self, cli_runner, tmp_path):
        """Test the doctor command."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            result = cli_runner.invoke(cli, ['doctor'])
            
            assert result.exit_code == 0
            assert "Checking system dependencies" in result.output
            assert "Dependency check complete" in result.output
    
    def test_doctor_with_site(self, cli_runner, tmp_path):
        """Test doctor command with site."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Init a site first
            cli_runner.invoke(cli, ['init', '.'])
            
            result = cli_runner.invoke(cli, ['doctor'])
            
            assert result.exit_code == 0
            assert "config.toml: found" in result.output
            assert "content/: found" in result.output


class TestRebuildHandler:
    """Test the RebuildHandler class."""
    
    def test_rebuild_handler_methods(self, site_structure_paths, sample_config_toml):
        """Test RebuildHandler methods."""
        # Create site structure using fixture
        paths = site_structure_paths
        paths['site'].mkdir()
        paths['content'].mkdir()
        paths['templates'].mkdir()
        
        config_path = paths['site'] / "config.toml"
        config_path.write_text(sample_config_toml)
        
        site = Site(paths['site'])
        
        # Test with custom callback
        callback_called = False
        def custom_callback():
            nonlocal callback_called
            callback_called = True
        
        handler = RebuildHandler(site, custom_callback, "Custom message")
        
        # Test should_ignore method
        event = FileModifiedEvent(str(paths['content'] / "test.md"))
        assert not handler.should_ignore(event)
        
        # Test with output directory (should be ignored)
        output_event = FileModifiedEvent(str(site.output_dir / "test.html"))
        assert handler.should_ignore(output_event)
        
        # Test with hidden file (should be ignored)
        hidden_event = FileModifiedEvent(str(paths['site'] / ".hidden"))
        assert handler.should_ignore(hidden_event)
        
        # Test on_modified
        handler.on_modified(event)
        assert callback_called
    
    def test_directory_event_handling(self, site_structure_paths, sample_config_toml):
        """Test CLI rebuild handler with directory events."""
        # Create site structure using fixture
        paths = site_structure_paths
        paths['site'].mkdir()
        paths['content'].mkdir()
        paths['templates'].mkdir()
        
        config_path = paths['site'] / "config.toml"
        config_path.write_text(sample_config_toml)
        
        site = Site(paths['site'])
        handler = RebuildHandler(site)
        
        # Test directory event (should be ignored)
        dir_event = DirModifiedEvent(str(paths['content']))
        assert handler.should_ignore(dir_event)