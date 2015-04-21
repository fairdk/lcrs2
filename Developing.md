# Developing #

When you have checked out LCRS, you'll see the following directory structure:

| buildroot/ | This is where you'll find config files for buildroot and the Linux kernel. |
|:-----------|:---------------------------------------------------------------------------|
| master/ | Master (GUI+monitoring) application |
| slave/ | The source files of the slave program which are packed into the ISO and PXE images |
| run\_virtualbox.sh | A script that configures bridgeutils and the vboxnet0 interface for testing LCRS with virtual machines |

# Using Virtualbox #

In order to test the Master application efficiently, you should be running a virtual machine:

  * apt-get install **virtualbox-ose**
  * apt-get install **bridge-utils**
  * run **.run\_virtualbox.sh**
  * On the first run, make sure that the built-in Virtualbox DHCP server is switched off.
  * Restart Virtualbox.
  * Create a new virtual machine, and let it use the host-only adapter (**vboxnet0**) which is connected to br0. Make sure the network card (under the Advanced section) is set to **PCnet-FAST III**, as it supports network booting.
  * When you run LCRS, you should configure it to use the br0 interface.