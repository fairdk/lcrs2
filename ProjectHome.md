# Large-scale Computer Re-use Suite (LCRS) #

# For the benefit of people and the planet, let us start re-using, repairing and refurbishing computers instead of creating more e-waste! #

## About ##

This software is meant to be used by organizations that re-use computer equipment. It consists of a GUI _master_ application and a _slave_ program booting on a custom Linux image. The slave allows for the master to scan hardware and do data deletion through LAN.

The master application contains a DHCP server which gives out IP addresses to the slaves and an optional TFTP server that boots the custom linux image on slave machines. When a slave's IP is known the master can issue commands to it.

A plugin architecture is provided, which receives results from scans and data deletions, allowing for eg. communication with warehouse logic etc.

This project is currently used and maintained by Danish organizations [SUG](http://www.seniorerudengraenser.dk) and [FAIR Danmark](http://www.fairdanmark.dk).

![http://lcrs.googlecode.com/files/screenshot.png](http://lcrs.googlecode.com/files/screenshot.png)



## Get involved! ##

Please send us bug reports, feature requests etc.!

We are very interested in hearing from you. If you are using the program or want to contribute.