"""Pytest configuration - add repo root to sys.path so imports resolve."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
