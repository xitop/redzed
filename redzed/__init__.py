"""
Redzed is a library for building small automated systems.

The redzed package allows to build a so-called "circuit" containing:
 - logic Blocks with outputs reacting to events
 - Triggers sending events when certain outputs change

The application code must connect the circuit with outside world.

Copyright (c) 2025-2026 Vlado Potisk <redzed@poti.sk>.

Released under the MIT License.

Docs: https://redzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/redzed/
"""

__version_info__ = (26, 4, 20)
__version__ = '.'.join(str(n) for n in __version_info__)

from . import circuit, block, debug, defs, formula_trigger, initializers, validator

from .block import *
from .circuit import *
from .debug import *
from .defs import *
from .formula_trigger import *
from .initializers import *
# .utils not imported
from .validator import *

# block library
from . import blocklib
from .blocklib import *

__all__ = [
    '__version__', '__version_info__',
    *block.__all__,
    *blocklib.__all__,
    *circuit.__all__,
    *debug.__all__,
    *defs.__all__,
    *formula_trigger.__all__,
    *initializers.__all__,
    *validator.__all__,
    ]
