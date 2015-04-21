Thank you for downloading Large-scale Computer Re-use Suite (LCRS).

This program is intended for re-using loads of computers for the benefit of
people and the planet. We hope that you find good use of it and that you
report any problems or contribute with code on our website:

http://lcrs.fairdanmark.dk

## RUNNING ##

You need to run LCRS as a superuser. This is because it runs a stand-alone
DHCP and TFTP server. This also means that you need to shutdown any similar
service occupying those network ports already.

LCRS consists of a "master" application and a "slave" application.

The master is the one you should run on the computer controlling and
monitoring all the computers you wish to re-use.

1) Check that you have installed the required dependencies.
2) To run the master program, simply execute the start.sh script.


## CONFIGURING ##

At the first run, you may be told of some issues with the DHCP server. You can
resolve those by changing your Preferences.

After reconfiguring, please restart LCRS.

Advanced users should look in ~/.coresu.cfg


## PLUGINS ##

To register data from LCRS, you have to write your own plugin. Please refer to
the plugin documentation for this.