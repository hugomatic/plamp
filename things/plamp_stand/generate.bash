#!/usr/bin/env bash

cad="plamp_stand"
views=("assembly" "plate" "camera_clip")

# we are assuming that a part.scad file exists in part directory
# (if the scad file is not standalone, all depends should be put there too)
# using git show, we make a copy of part.scad in /tmp folder at the commit
#    git show 90a6eba:part/part.scad
# we then use openscad to generate an stl file from the tmp directory
#    part_90a6eba.stl

# this file logs the output of this script
log="readme.md"

SCAD_FILE="${cad}.scad"
# name of the stl file, without the commit
STL_PREFIX="${cad}"
# where to find the scad file in git
GIT_FOLDER="things/${cad}"
# directory this script lives in
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# path to the scad file on disk
SCAD_PATH="$SCRIPT_DIR/$SCAD_FILE"
# repo-relative path to the scad file
GIT_SCAD_PATH="$GIT_FOLDER/$SCAD_FILE"
# name of this script (generate.bash)
name=$0

if [[ "$#" -ne 2 ]];
    then
        last_commit=`git log -n 1 --pretty=format:%h -- "$SCAD_PATH"`
        today=`date +%b%d | tr 'A-Z' 'a-z'`
        echo
        echo "$cad stl generator"
        echo "usage:"
        echo "  $name target_directory commit_hash"
        echo
        echo "ex:"
        echo "  $name prints/$today $last_commit"
        echo
        echo
        # check if file is modified on disk
        git_stat=`git status --porcelain -s | grep "$SCAD_PATH" || true`
        if [[ $git_stat ]];
          then
            echo "!!"
            echo "!! git status: $git_stat"
            echo "!! WARNING Please commit first if you want repeatable results"
            echo "!! File $SCAD_FILE is not committed (see git status below)"
            echo "!!"
        fi
        exit -1
fi

target_directory=$1
[ -d "$1" ] && echo "Error: directory $1 already exists." && exit -2

commit=$2

echo "commit $commit"
echo "target_directory $target_directory"


mkdir -p $target_directory
cd $target_directory
# remove any previous file
rm /tmp/scad_doc.scad


# get the correct version of the cad file in the temp directory
echo "# $SCAD_FILE" | tee -a $log
date | tee -a $log
echo "get the source CAD:" | tee -a $log
echo '```' >> $log
echo "git show $commit:$GIT_SCAD_PATH" | tee -a $log

echo '```' >> $log
git show "$commit:$GIT_SCAD_PATH" > /tmp/scad_doc.scad


for view in "${views[@]}"
do

  stl_file="${STL_PREFIX}_${view}_${commit}.stl"
  echo "## [$stl_file]($stl_file)" | tee -a $log

  options="-D revision_string=\"$commit\" -D view=\"$view\" -D ball_quality=64"
  echo -e "\noptions: $options\n" | tee -a $log

  echo "toto $view"

  echo '```' >> $log
  # time /Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD $options --export-format asciistl -o $stl_file /tmp/scad_doc.scad 2>&1 | tee -a $log
  time openscad $options --export-format asciistl -o $stl_file /tmp/scad_doc.scad 2>&1 | tee -a $log
  echo '```' >> $log
done
