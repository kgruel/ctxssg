"""ctxssg - A pandoc-based static site generator."""

__version__ = "0.1.0"

from .generator import Site, SiteGenerator

__all__ = ["Site", "SiteGenerator"]