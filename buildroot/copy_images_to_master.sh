#!/bin/sh
cp buildroot-current/output/images/rootfs.tar.gz ../master/pxe-root/lcrs/initrd.gz
cp buildroot-current/output/images/bzImage ../master/pxe-root/lcrs/kernel.fair-net
cp buildroot-current/output/images/rootfs.iso9660 ../lcrs.iso

