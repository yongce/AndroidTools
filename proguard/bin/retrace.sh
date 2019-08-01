#!/bin/sh
#
# Start-up script for Retrace -- companion tool for ProGuard, free class file
# shrinker, optimizer, obfuscator, and preverifier for Java bytecode.
#
# Note: when passing file names containing spaces to this script,
#       you'll have to add escaped quotes around them, e.g.
#       "\"/My Directory/My File.txt\""

kernel_name=`uname -s`
IS_MAC_OS=false
if [ $kernel_name = "Darwin" ]; then
    IS_MAC_OS=true
fi

if ! $IS_MAC_OS; then # for Linux only
    alias greadlink="readlink"
fi

# Account for possibly missing/basic readlink.
# POSIX conformant (dash/ksh/zsh/bash).
PROGUARD=`greadlink -f "$0" 2>/dev/null`
if test "$PROGUARD" = ''
then
  PROGUARD=`greadlink "$0" 2>/dev/null`
  if test "$PROGUARD" = ''
  then
    PROGUARD="$0"
  fi
fi

PROGUARD_HOME=`dirname "$PROGUARD"`/..

java -jar "$PROGUARD_HOME/lib/retrace.jar" "$@"
