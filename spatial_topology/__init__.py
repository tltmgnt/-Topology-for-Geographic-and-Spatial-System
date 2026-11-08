"""Offline geographic network topology analysis, with no external execution."""
from .analysis import build_report
from .model import parse_network, parse_requirements
from .io import compare_bundles, create_bundle, verify_bundle

__version__ = '2.0.0'
__all__ = ['build_report', 'parse_network', 'parse_requirements', 'create_bundle', 'verify_bundle', 'compare_bundles']
