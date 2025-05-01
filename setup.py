"""
Script for building the example:

Usage:
    python3 setup.py py2app
"""

from setuptools import setup

plist = {

}

setup(
    name="studyBar",
    app=["studyBar.py"],
    # data_files=[""],
    options={"py2app": {"plist": plist}},
    setup_requires=["py2app", "pyobjc-framework-Cocoa"],
)