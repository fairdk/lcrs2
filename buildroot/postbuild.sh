#!/bin/sh
cp menu.lst fs/iso9660/
cp wipe output/target/usr/bin
mkdir -p output/target/usr/share/hwdata
cp pci.ids output/target/usr/share/hwdata/
chmod +x output/target/usr/bin/wipe
mkdir -p output/target/usr/local
cp -R ../../slave output/target/usr/local/
echo "udhcpc -n eth0" > output/target/etc/init.d/S50dhcp
echo "python /usr/local/slave/main.py" > output/target/etc/init.d/S60LCRS
chmod +x output/target/etc/init.d/*
