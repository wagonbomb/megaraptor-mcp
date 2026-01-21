"""
Jinja2 templates for deployment configurations.
"""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent


def get_template_path(name: str) -> Path:
    """Get the path to a template file.

    Args:
        name: Template filename

    Returns:
        Path to the template file
    """
    return TEMPLATES_DIR / name
