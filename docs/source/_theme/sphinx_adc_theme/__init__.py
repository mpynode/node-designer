"""Sphinx ADC theme.

Fork From https://github.com/coordt/ADCtheme/.

"""
import os

VERSION = (0, 1, 4)

__version__ = ".".join(str(v) for v in VERSION)
__version_full__ = __version__


def get_html_theme_path():
    """Return list of HTML theme paths."""
    return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

def get_theme_version():
    """Return the theme version"""
    return __version__

def update_context(app, pagename, templatename, context, doctree):
    context['adc_theme_version'] = __version__

def setup(app):
    app.connect('html-page-context', update_context)
    return {'version': __version__,
            'parallel_read_safe': True}
