"""dedao-notebooklm package."""

__version__ = "0.4.0"
__author__ = "dedao-notebooklm contributors"

from .converter import HTMLToMarkdownConverter
from .dedao import Chapter, Course, CourseDetail, DedaoAuth, DedaoClient

__all__ = [
    "__version__",
    "DedaoClient",
    "DedaoAuth",
    "Course",
    "Chapter",
    "CourseDetail",
    "HTMLToMarkdownConverter",
]
