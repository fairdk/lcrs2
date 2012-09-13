#!/bin/bash

if [ ! -d ./buildroot-current ]
then
	echo "No buildroot-current found"
	exit
fi

cp postbuild.sh buildroot-current/
cp lcrs.config buildroot-current
cp linux.config buildroot-current
