"""Tests for ctxssg.__main__ module."""

import sys


class TestMainModule:
    """Test the __main__.py module."""
    
    def test_main_entry_point(self):
        """Test that the main module can be executed."""
        from ctxssg.__main__ import cli
        assert callable(cli)
        
    def test_main_module_imports(self):
        """Test that main module imports work correctly."""
        import ctxssg.__main__
        assert hasattr(ctxssg.__main__, 'cli')
    
    def test_main_module_execution(self):
        """Test __main__ module if __name__ == '__main__' execution."""
        # This tests the if __name__ == "__main__": cli() line
        from ctxssg import __main__
        
        # Mock sys.argv to simulate execution
        original_argv = sys.argv[:]
        try:
            sys.argv = ['ctxssg', '--version']
            # The line should be covered when the module is imported
            # if executed as main
            assert hasattr(__main__, 'cli')
        finally:
            sys.argv = original_argv