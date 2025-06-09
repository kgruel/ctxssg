import click
import os
import sys
from pathlib import Path
import http.server
import socketserver
import threading
from typing import Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime

from .generator import Site, SiteGenerator, check_dependencies


class RebuildHandler(FileSystemEventHandler):
    """Shared file system event handler for rebuilding the site on changes."""
    
    def __init__(self, site: Site, rebuild_callback: Optional[Callable[[], None]] = None, success_message: str = "Site rebuilt") -> None:
        self.site = site
        self.rebuild_callback = rebuild_callback or self._default_rebuild
        self.success_message = success_message
        
    def _default_rebuild(self) -> None:
        """Default rebuild action - just build the site."""
        self.site.build()
        
    def should_ignore(self, event) -> bool:
        """Check if an event should be ignored."""
        if event.is_directory:
            return True
        
        # Ignore output directory and hidden files
        path = Path(event.src_path)
        if (str(self.site.output_dir) in str(path) or 
            any(part.startswith('.') for part in path.parts)):
            return True
        
        return False
        
    def on_modified(self, event) -> None:
        """Handle file modification events."""
        if self.should_ignore(event):
            return
        
        click.echo(f"Detected change in {Path(event.src_path)}")
        self.rebuild_callback()


@click.group()
@click.version_option()
def cli():
    """A pandoc-based static site generator."""
    pass


@cli.command()
@click.argument('path', type=click.Path(), default='.')
@click.option('--title', '-t', default='My Site', help='Site title')
def init(path, title):
    """Initialize a new static site."""
    site_path = Path(path).resolve()
    
    if site_path.exists() and any(site_path.iterdir()):
        if not click.confirm(f"Directory {site_path} is not empty. Continue?"):
            return
    
    click.echo(f"Initializing new site at {site_path}")
    SiteGenerator.init_site(site_path, title)
    click.secho("Site initialized successfully!", fg='green')
    click.echo("\nNext steps:")
    click.echo("  1. cd " + str(site_path))
    click.echo("  2. ctxssg build")
    click.echo("  3. ctxssg serve")


@cli.command()
@click.option('--watch', '-w', is_flag=True, help='Watch for changes and rebuild')
@click.option('--formats', '-f', multiple=True, help='Output formats (html, plain, xml)')
@click.option('--incremental/--full', default=True, help='Use incremental building (default: incremental)')
@click.option('--clean', is_flag=True, help='Force clean rebuild (removes cache)')
@click.option('--stats', is_flag=True, help='Show build statistics')
def build(watch, formats, incremental, clean, stats):
    """Build the static site."""
    # Check dependencies first
    try:
        check_dependencies()
    except RuntimeError as e:
        click.secho(f"Dependency error: {e}", fg='red')
        sys.exit(1)
    
    site_path = Path.cwd()
    toml_config_path = site_path / "config.toml"
    yaml_config_path = site_path / "config.yaml"
    
    if not (toml_config_path.exists() or yaml_config_path.exists()):
        click.secho("Error: No config.toml or config.yaml found. Run 'ctxssg init' first.", fg='red')
        sys.exit(1)
    
    site = Site(site_path)
    
    # Override output formats if specified
    if formats:
        site.config['output_formats'] = list(formats)
    
    def do_build():
        try:
            build_type = "clean" if clean else ("full" if not incremental else "incremental")
            click.echo(f"Building site ({build_type})...")
            output_formats = site.config.get('output_formats', ['html'])
            click.echo(f"Output formats: {', '.join(output_formats)}")
            
            build_stats = site.build(incremental=incremental, clean=clean, show_stats=stats)
            
            if stats and build_stats:
                # Show detailed build statistics
                cache_enabled = build_stats.get("cache_enabled", False)
                total_files = build_stats.get("total_files", 0)
                rebuilt_files = build_stats.get("rebuilt_files", 0)
                cached_files = build_stats.get("cached_files", 0)
                duration = build_stats.get("duration", 0)
                
                if cache_enabled and total_files > 0:
                    cache_hit_rate = build_stats.get("cache_hit_rate", 0)
                    click.echo(f"Incremental build: {rebuilt_files}/{total_files} files rebuilt ({cache_hit_rate:.1f}% cached)")
                else:
                    click.echo(f"Full build: {rebuilt_files} files processed")
                    
                click.echo(f"Build completed in {duration:.2f}s")
                
                # Show time savings estimate
                if cache_enabled and cached_files > 0:
                    time_per_file = duration / max(rebuilt_files, 1)
                    estimated_full_time = time_per_file * total_files
                    if estimated_full_time > duration:
                        time_saved = estimated_full_time - duration
                        click.secho(f"Estimated time saved: {time_saved:.2f}s", fg='cyan')
            else:
                click.secho(f"Site built successfully to {site.output_dir}", fg='green')
                
        except Exception as e:
            click.secho(f"Build error: {e}", fg='red')
    
    do_build()
    
    if watch:
        click.echo("Watching for changes...")
        
        event_handler = RebuildHandler(site, do_build)
        observer = Observer()
        observer.schedule(event_handler, str(site_path), recursive=True)
        observer.start()
        
        try:
            while True:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            observer.stop()
            click.echo("\nStopping watcher...")
        observer.join()


@cli.command()
@click.option('--port', '-p', default=8000, help='Port to serve on')
@click.option('--watch', '-w', is_flag=True, help='Watch for changes and rebuild')
def serve(port, watch):
    """Serve the built site locally."""
    # Check dependencies first if we might need to rebuild
    if watch:
        try:
            check_dependencies()
        except RuntimeError as e:
            click.secho(f"Dependency error: {e}", fg='red')
            sys.exit(1)
    
    site_path = Path.cwd()
    site = Site(site_path)
    
    if not site.output_dir.exists():
        click.secho("No build directory found. Building site first...", fg='yellow')
        site.build()
    
    os.chdir(site.output_dir)
    
    class Handler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            super().end_headers()
    
    def start_server():
        with socketserver.TCPServer(("", port), Handler) as httpd:
            click.secho(f"Serving site at http://localhost:{port}", fg='green')
            click.echo("Press Ctrl+C to stop")
            httpd.serve_forever()
    
    if watch:
        # Start watcher in a separate thread
        os.chdir(site_path)
        
        def rebuild_with_feedback():
            """Rebuild with success/error feedback."""
            try:
                site.build()
                click.secho("Site rebuilt", fg='green')
            except Exception as e:
                click.secho(f"Build error: {e}", fg='red')
        
        event_handler = RebuildHandler(site, rebuild_with_feedback)
        observer = Observer()
        observer.schedule(event_handler, str(site_path), recursive=True)
        observer.start()
        
        os.chdir(site.output_dir)
        
        try:
            start_server()
        except KeyboardInterrupt:
            observer.stop()
            click.echo("\nShutting down...")
        observer.join()
    else:
        try:
            start_server()
        except KeyboardInterrupt:
            click.echo("\nShutting down...")


@cli.command()
def doctor():
    """Check system dependencies and configuration."""
    click.echo("Checking system dependencies...")
    
    # Check pandoc
    try:
        check_dependencies()
        import pypandoc
        version = pypandoc.get_pandoc_version()
        click.secho(f"✓ Pandoc: {version}", fg='green')
    except RuntimeError as e:
        click.secho(f"✗ Pandoc: {e}", fg='red')
        return
    except Exception as e:
        click.secho(f"✗ Pandoc: Error checking version - {e}", fg='red')
        return
    
    # Check Python dependencies
    required_modules = [
        ('click', 'Click'),
        ('yaml', 'PyYAML'),
        ('frontmatter', 'python-frontmatter'),
        ('jinja2', 'Jinja2'),
        ('watchdog', 'watchdog'),
        ('bs4', 'BeautifulSoup4'),
    ]
    
    # Check TOML support
    try:
        import sys
        if sys.version_info >= (3, 11):
            import tomllib  # noqa: F401
            click.secho("✓ TOML support: built-in (Python 3.11+)", fg='green')
        else:
            import tomli  # noqa: F401
            click.secho("✓ TOML support: tomli library", fg='green')
    except ImportError:
        click.secho("✗ TOML support: tomli library not installed", fg='red')
    
    for module, name in required_modules:
        try:
            __import__(module)
            click.secho(f"✓ {name}: installed", fg='green')
        except ImportError:
            click.secho(f"✗ {name}: not installed", fg='red')
    
    # Check current directory structure
    site_path = Path.cwd()
    toml_config_path = site_path / "config.toml"
    yaml_config_path = site_path / "config.yaml"
    
    click.echo("\nChecking site configuration...")
    if toml_config_path.exists():
        click.secho("✓ config.toml: found (preferred)", fg='green')
        config_type = "TOML"
    elif yaml_config_path.exists():
        click.secho("✓ config.yaml: found (legacy)", fg='green')
        config_type = "YAML"
    else:
        click.secho("✗ config file: not found (run 'ctxssg init' to create)", fg='yellow')
        config_type = None
    
    if config_type:
        try:
            site = Site(site_path)
            click.secho(f"✓ Configuration format: {config_type}", fg='green')
            click.secho(f"✓ Site title: {site.config.get('title', 'Not set')}", fg='green')
            click.secho(f"✓ Output directory: {site.config.get('output_dir', '_site')}", fg='green')
            click.secho(f"✓ Output formats: {', '.join(site.config.get('output_formats', ['html']))}", fg='green')
            
            # Check for enhanced configuration features
            if 'format_config' in site.config:
                click.secho("✓ Enhanced format configuration: enabled", fg='green')
            if 'template_config' in site.config:
                click.secho("✓ Template configuration: enabled", fg='green')
        except Exception as e:
            click.secho(f"✗ Site configuration: {e}", fg='red')
    
    # Check directory structure
    directories = ['content', 'templates', 'static']
    for dir_name in directories:
        dir_path = site_path / dir_name
        if dir_path.exists():
            click.secho(f"✓ {dir_name}/: found", fg='green')
        else:
            click.secho(f"✗ {dir_name}/: not found", fg='yellow')
    
    click.echo("\nDependency check complete!")


@cli.group()
def cache():
    """Manage the build cache."""
    pass


@cache.command('info')
def cache_info():
    """Show cache statistics."""
    from .cache import BuildCache
    
    site_path = Path.cwd()
    cache_dir = site_path / '.ctxssg-cache'
    
    if not cache_dir.exists():
        click.secho("No cache found. Run a build first to create cache.", fg='yellow')
        return
    
    try:
        cache = BuildCache(cache_dir)
        stats = cache.get_stats()
        
        click.echo("Build Cache Statistics:")
        click.echo(f"  Files tracked: {stats['files_tracked']}")
        click.echo(f"  Templates tracked: {stats['templates_tracked']}")
        click.echo(f"  Disk cache size: {stats['disk_cache_size_mb']:.2f} MB")
        click.echo(f"  Memory cache size: {stats['memory_cache_size_mb']:.2f} MB")
        click.echo(f"  Memory cache entries: {stats['memory_cache_entries']}")
        
        if stats['last_build']:
            click.echo(f"  Last build: {stats['last_build']}")
        else:
            click.echo("  Last build: Never")
            
    except Exception as e:
        click.secho(f"Error reading cache: {e}", fg='red')


@cache.command('clear')
@click.confirmation_option(prompt='Are you sure you want to clear the cache?')
def cache_clear():
    """Clear the build cache."""
    from .cache import BuildCache
    
    site_path = Path.cwd()
    cache_dir = site_path / '.ctxssg-cache'
    
    if not cache_dir.exists():
        click.secho("No cache found.", fg='yellow')
        return
    
    try:
        cache = BuildCache(cache_dir)
        cache.clear()
        click.secho("Cache cleared successfully.", fg='green')
    except Exception as e:
        click.secho(f"Error clearing cache: {e}", fg='red')


@cache.command('clean')
@click.option('--older-than', type=int, default=30, help='Remove entries older than N days')
def cache_clean(older_than):
    """Clean old cache entries."""
    from .cache import BuildCache
    
    site_path = Path.cwd()
    cache_dir = site_path / '.ctxssg-cache'
    
    if not cache_dir.exists():
        click.secho("No cache found.", fg='yellow')
        return
    
    try:
        cache = BuildCache(cache_dir)
        cleaned_count = cache.clean_old_entries(older_than)
        
        if cleaned_count > 0:
            click.secho(f"Cleaned {cleaned_count} old cache entries.", fg='green')
        else:
            click.echo("No old cache entries to clean.")
            
    except Exception as e:
        click.secho(f"Error cleaning cache: {e}", fg='red')


@cli.command()
@click.argument('title')
@click.option('--type', '-t', type=click.Choice(['post', 'page']), default='post', help='Content type')
def new(title, type):
    """Create a new post or page."""
    site_path = Path.cwd()
    
    if not ((site_path / "config.toml").exists() or (site_path / "config.yaml").exists()):
        click.secho("Error: No config.toml or config.yaml found. Run 'ctxssg init' first.", fg='red')
        sys.exit(1)
    
    # Generate filename from title
    filename = title.lower().replace(' ', '-').replace('/', '-')
    filename = ''.join(c for c in filename if c.isalnum() or c == '-')
    
    if type == 'post':
        date_str = datetime.now().strftime('%Y-%m-%d')
        file_path = site_path / "content" / "posts" / f"{date_str}-{filename}.md"
        
        content = f'''---
title: {title}
date: {datetime.now().isoformat()}
layout: post
---

Write your content here...
'''
    else:
        file_path = site_path / "content" / f"{filename}.md"
        
        content = f'''---
title: {title}
layout: default
---

Write your content here...
'''
    
    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    if file_path.exists():
        click.secho(f"Error: File {file_path} already exists", fg='red')
        sys.exit(1)
    
    file_path.write_text(content)
    click.secho(f"Created {type}: {file_path}", fg='green')


@cli.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--formats', '-f', multiple=True, default=['html'], help='Output formats')
@click.option('--output-dir', '-o', type=click.Path(), help='Output directory')
def convert(input_file, formats, output_dir):
    """Convert a single markdown file to specified formats."""
    import frontmatter
    from pathlib import Path
    
    input_path = Path(input_file)
    
    if output_dir:
        output_base = Path(output_dir) / input_path.stem
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    else:
        output_base = input_path.with_suffix('')
    
    # Create a temporary site for conversion
    site_path = Path.cwd()
    site = Site(site_path)
    
    # Create dummy page data
    post = frontmatter.load(input_path)
    page_data = {
        'title': post.get('title', input_path.stem),
        'content': '',  # Will be filled by _generate_format
        'date': post.get('date', datetime.now()),
        'layout': post.get('layout', 'default'),
        **post.metadata
    }
    
    click.echo(f"Converting {input_file}...")
    for fmt in formats:
        try:
            site._generate_format(page_data, input_path, output_base, fmt)
            ext = 'txt' if fmt == 'plain' else fmt
            output_file = output_base.with_suffix(f'.{ext}')
            click.echo(f"  → {output_file}")
        except Exception as e:
            click.secho(f"  Error converting to {fmt}: {e}", fg='red')
