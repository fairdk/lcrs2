Large-scale Computer Reuse Suite (LCRS)
=======================================

**THIS PROJECT HAS A NEWER VERSION**

Go here:

https://github.com/fairdk/lcrs

---------------------------------------------------------

## For the benefit of people and the planet, let us start re-using, repairing and refurbishing computers instead of throwing them away

![LCRS main window](https://raw.githubusercontent.com/fairdk/lcrs2/master/lcrs_screenshot.png)


README
======

Thank you for downloading Large-scale Computer Re-use Suite (LCRS).

This program is intended for re-using loads of computers for the benefit of
people and the planet. We hope that you find good use of it and that you
report any problems or contribute with code on our website:

http://lcrs.fairdanmark.dk

Installing
==========

Click this link to install from PPA on Ubuntu/Debian:
  
[LCRS PPA on Launchpad](https://launchpad.net/~benjaoming/+archive/ubuntu/lcrs)

Installing as raw Python package:

    git clone https://github.com/fairdk/lcrs2.git
    cd lcrs2
    sudo python setup.py install


Running
=======

You need to run LCRS as a superuser. This is because it runs a stand-alone
DHCP and TFTP server. This also means that you need to shutdown any similar
service occupying those network ports already.

LCRS consists of a "master" application and a "slave" application.

The master is the one you should run on the computer controlling and
monitoring all the computers you wish to re-use.

1. Check that you have installed the required dependencies.
1. Run the command `lcrs`
1. Check the network preferences and make sure that it fits your own setup.
1. Close and start again if you make changes to the settings.


Configuring
===========

At the first run, you may be told of some issues with the DHCP server. You can
resolve those by changing your Preferences.

After reconfiguring, please restart LCRS.

Advanced users should look in `~/.coresu.cfg`


Plugins
=======

To register data from LCRS, you have to write your own plugin. Please refer to
the plugin documentation for this.

