#!/bin/sh

PRG=`readlink -e "$0"`
if [ $? -ne 0 ]; then
    PRG="$0"
fi
PRGDIR=`dirname "$PRG"`
#

_classpath="."
for k in $PRGDIR/lib/*.jar
do
 _classpath="${_classpath}:${k}"
done
java -Xms512m -Xmx1024m -classpath "${_classpath}" "com.googlecode.dex2jar.v3.Main" $1 $2 $3 $4 $5 $6
