"""Profiling / watch / snapshot.

This package replaces the former ``instrumentation.py`` module. Its dotted
name equals the old module's, so existing
``from mpynode._common.instrumentation import <name>`` imports keep working:
the submodules define the public names and this facade re-exports them.
"""
from .stats import *  # noqa: F401,F403
from .cprofile_encode import *  # noqa: F401,F403
from .watch import *  # noqa: F401,F403
from .snapshot_io import *  # noqa: F401,F403
from .exec_runner import *  # noqa: F401,F403

# Private/underscore names reached by external callers by NAME. Star-imports
# skip leading-underscore names, so re-export them explicitly.
#   - _is_previewable_media: test_media_preview.py:1042
from .watch import _is_previewable_media  # noqa: F401
