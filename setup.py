"""
Script for building the example:

Usage:
    python3 setup.py py2app
"""

from setuptools import setup

OPTIONS = {
    'packages': ['rumps', 'json', 'subprocess', 'datetime'],
    'iconfile': 'studybar.icns'
}

setup(
    name="StudyBar",
    app=["studyBar.py"],
    data_files=["config.json"],
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)