#!/bin/bash

SVN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd ../ && pwd )"

cp $SVN_DIR/menu.lst fs/iso9660/
cp $SVN_DIR/wipe output/target/usr/bin
mkdir -p output/target/usr/share/hwdata
cp $SVN_DIR/pci.ids output/target/usr/share/hwdata/
chmod +x output/target/usr/bin/wipe
mkdir -p output/target/usr/local
svn export --force $SVN_DIR/../lcrs/slave output/target/usr/local/slave
echo "udhcpc -n eth0" > output/target/etc/init.d/S50dhcp
echo "python /usr/local/slave/main.py" > output/target/etc/init.d/S60LCRS
chmod +x output/target/etc/init.d/*
