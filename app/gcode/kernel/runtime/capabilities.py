"""Historical controller-policy module path, also used by existing native binaries."""

import sys

from ..milling import controller

sys.modules[__name__] = controller
