from .base import BaseModel

# Import submodules so their classes register with the mapper registry.
# Import modules, not classes, to avoid circular imports between request/property/notification.
from . import user
# add future models here as needed

__all__ = ["BaseModel"]