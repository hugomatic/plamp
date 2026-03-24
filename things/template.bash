#!/usr/bin/env bash

part=$1

if [ -z "$part" ]; then
    echo
    echo "SCAD Part generator"
    echo
    echo "usage: $0 [part] whhere part is tbe name of the scad part to generate "
    exit -1
else
    echo "empty"
fi

echo "Hello $part"

mkdir $part
cp ./3d_template/generate.bash ./$1/generate.bash
cp ./3d_template/cad.scad ./$1/$1.scad
sed -i -e "s/__cad__name__/$1/g" ./$1/generate.bash
rm ./$1/generate.bash-e
