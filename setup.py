import os
from setuptools import setup, find_packages

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "lcrs",
    version = "2.1",
    packages = find_packages(),
    scripts = ['bin/lcrs'],

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    install_requires=read('requirements.txt').split("\n"),
    long_description=read('README'),
    zip_safe = False,
    package_data = {
        # If any package contains *.txt or *.rst files, include them:
        '': ['*.txt', '*.rst', '*.glade', '*.png'],
        'lcrs.master': ['pxe-root/*'],
        'lcrs.master': ['pxe-root/*/*'],
        'lcrs.master': ['pxe-root/*/*/*'],
        'lcrs.master': ['pxe-root/*/*/*/*'],
        'lcrs.master.ui': ['glade/*'],
        'lcrs.master': ['*html', '*cfg'],
        'lcrs.master.plugins.fair': ['*html', 'glade/*'],
    },

    # metadata for upload to PyPI
    author = "Benjamin Bach",
    author_email = "benjamin@fairdanmark.dk",
    description = "LCRS - Large-scale Computer Reuse Suite",
    license = "GPLv3",
    keywords = "refurbishment wipe erasure logistics reuse recycling",
    url = "http://code.google.com/p/lcrs/",   # project home page, if any

    # could also include long_description, download_url, classifiers, etc.
)


