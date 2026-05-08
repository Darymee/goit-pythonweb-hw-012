"""Sphinx configuration for Contacts API documentation."""
import os
import sys

sys.path.insert(0, os.path.abspath(".."))
os.environ.setdefault("DATABASE_URL", "sqlite:///./docs.db")
os.environ.setdefault("SECRET_KEY", "docs-secret")
os.environ.setdefault("CLOUDINARY_NAME", "docs-cloud")
os.environ.setdefault("CLOUDINARY_API_KEY", "docs-key")
os.environ.setdefault("CLOUDINARY_API_SECRET", "docs-secret")

project = "Contacts API"
author = "GOIT"
extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon"]
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "alabaster"
