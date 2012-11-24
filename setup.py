import os
from setuptools import setup, find_packages
from distutils.command.install import install

VERSION="2.2.4"

class lcrs_install(install):

    def run(self):
        install.run(self)
        
        print "Creating desktop shortcuts..."
        os.system('xdg-icon-resource install --noupdate --size 16 data/icon/16/lcrs-lcrs.png')
        os.system('xdg-icon-resource install --noupdate --size 22 data/icon/22/lcrs-lcrs.png')
        os.system('xdg-icon-resource install --noupdate --size 32 data/icon/32/lcrs-lcrs.png')
        os.system('xdg-icon-resource install --noupdate --size 48 data/icon/48/lcrs-lcrs.png')
        os.system('xdg-icon-resource install --noupdate --size 64 data/icon/64/lcrs-lcrs.png')
        os.system('xdg-icon-resource install --size 128 data/icon/128/lcrs-lcrs.png')
        os.system('xdg-desktop-menu install data/lcrs-master.desktop')
        print "All done. Start LCRS from your application menu or run 'lcrs'."

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "lcrs",
    version = VERSION,
    packages = find_packages(),
    scripts = ['bin/lcrs'],

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    install_requires=read('requirements.txt').split("\n"),
    long_description=read('README'),
    zip_safe = False,
    package_data = {
        # If any package contains *.txt or *.rst files, include them:
        'lcrs.master': ['pxe-root/pxelinux.0', 
                        'pxe-root/lcrs/*.*', 
                        'pxe-root/pxelinux.cfg/*', 
                        'pxe-root/ubuntu-installer/i386/boot-screens/*.*', 
                        'pxe-root/ubuntu-installer/i386/pxelinux.cfg/*', 
                        'pxe-root/ubuntu-installer/i386/pxelinux.0',
                        '*html',
                        '*cfg'],
        'lcrs.master.ui': ['glade/*'],
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
    cmdclass={'install': lcrs_install}

)


