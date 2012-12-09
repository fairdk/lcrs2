1) Get the necessary ubuntu packages

sudo apt-get install build-essentials
sudo apt-get install libncurses5-dev bison flex texinfo

2) Get the latest buildroot

wget http://....
tar xvfz ...

You might wanna move the whole buildroot dir as it 
will end up at several GBs.

mv buildroot-201x-xx /media/otherdrive/
ln -s /media/otherdrive/buildroot-201x-xx buildroot-current

./prepare-buildroot.sh

cd buildroot-current
make menuconfig

Configuration:
 1) load lcrs.config
 2) Make sure that the latest versions of ulibc, gcc, linux kernel headers etc. and the linux kernel
    are selected. Otherwise the ones from the old config will...
 3) Make sure you're not using old configuration files for busybox, ulibc, set kernel header version
 4) make changes and make sure ./postbuild.sh is run before creating images (-> system configuration)
 5) make sure your configuration is saved in .config

make

If there are problems with uClibc then make sure that there is a uClibc.config in toolchain/uClibc/

To change the linux kernel:
make linux-menuconfig
 1) Load linux.config (you need to give it an absolute path)
 2) make changes
 3) save to linux.config

make

To rebuild:
 1) rm -Rf output/

Make sure to do this if you've made basic changes as there are many
dependencies in buildroot. If you've just added a new program, you
don't need to rebuild, just run make.

To rebuild just the kernel:

cd output/build/linux-xx/
make clean
cd ../../../
make


NOTES:

Building with static device table: TTY is "tty1"
Building with devtmpfs use "ttyS0"
