#!/usr/bin/python

'''
    Copyright 2009, The Android Open Source Project

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
'''

# script to highlight adb logcat output for console
# written by jeff sharkey, http://jsharkey.org/
# piping detection and popen() added by other android team members

# Modified by Yongce Tu <yongce.tu at gmail.com>
# 1. Add line number
# 2. Support logcat filter args
# 3. Support logcat -v brief|time|threadtime
#

import os, sys, re, StringIO
import fcntl, termios, struct
import getopt

# unpack the current terminal width/height
data = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, '1234')
HEIGHT, WIDTH = struct.unpack('hh',data)

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

def format(fg=None, bg=None, bright=False, bold=False, dim=False, reset=False):
    # manually derived from http://en.wikipedia.org/wiki/ANSI_escape_code#Codes
    codes = []
    if reset: codes.append("0")
    else:
        if not fg is None: codes.append("3%d" % (fg))
        if not bg is None:
            if not bright: codes.append("4%d" % (bg))
            else: codes.append("10%d" % (bg))
        if bold: codes.append("1")
        elif dim: codes.append("2")
        else: codes.append("22")
    return "\033[%sm" % (";".join(codes))


def indent_wrap(message, indent=0, width=80):
    wrap_area = width - indent
    messagebuf = StringIO.StringIO()
    current = 0
    while current < len(message):
        next = min(current + wrap_area, len(message))
        messagebuf.write(message[current:next])
        if next < len(message):
            messagebuf.write("\n%s" % (" " * indent))
        current = next
    return messagebuf.getvalue()


LAST_USED = [RED,GREEN,YELLOW,BLUE,MAGENTA,CYAN,WHITE]
KNOWN_TAGS = {
    "dalvikvm": BLUE,
    "Process": BLUE,
    "ActivityManager": CYAN,
    "ActivityThread": CYAN,
}

def allocate_color(tag):
    # this will allocate a unique format for the given tag
    # since we dont have very many colors, we always keep track of the LRU
    if not tag in KNOWN_TAGS:
        KNOWN_TAGS[tag] = LAST_USED[0]
    color = KNOWN_TAGS[tag]
    LAST_USED.remove(color)
    LAST_USED.append(color)
    return color


RULES = {
    #re.compile(r"([\w\.@]+)=([\w\.@]+)"): r"%s\1%s=%s\2%s" % (format(fg=BLUE), format(fg=GREEN), format(fg=BLUE), format(reset=True)),
}

NUMBER_WIDTH = 6
TAGTYPE_WIDTH = 3
TAG_WIDTH = 25
PID_WIDTH = 7
TID_WIDTH = 7
TIME_WIDTH = 21
HEADER_SIZE =  1 + NUMBER_WIDTH + TAGTYPE_WIDTH + 1 + TAG_WIDTH + 1 + PID_WIDTH + 1

TAGTYPES = {
    "V": "%s%s%s " % (format(fg=WHITE, bg=BLACK), "V".center(TAGTYPE_WIDTH), format(reset=True)),
    "D": "%s%s%s " % (format(fg=BLACK, bg=BLUE), "D".center(TAGTYPE_WIDTH), format(reset=True)),
    "I": "%s%s%s " % (format(fg=BLACK, bg=GREEN), "I".center(TAGTYPE_WIDTH), format(reset=True)),
    "W": "%s%s%s " % (format(fg=BLACK, bg=YELLOW), "W".center(TAGTYPE_WIDTH), format(reset=True)),
    "E": "%s%s%s " % (format(fg=BLACK, bg=RED), "E".center(TAGTYPE_WIDTH), format(reset=True)),
    "F": "%s%s%s " % (format(fg=BLACK, bg=RED), "F".center(TAGTYPE_WIDTH), format(reset=True)),
    "?": "%s%s%s " % (format(fg=BLACK, bg=RED), "?".center(TAGTYPE_WIDTH), format(reset=True)),
}

# regular expression for logs
retagBrief = re.compile("^([A-Z])/([^\(]+)\(([^\)]+)\): (.*)$")
retagTime = re.compile("^([\-:\. 0-9]+) ([A-Z])/([^\(]+)\(([^\)]+)\): (.*)$")
retagThreadtime = re.compile("^([\-:\. 0-9]+)[ ]+([0-9]+)[ ]+([0-9]+) ([A-Z]) ([^ ]+)[ ]*: (.*)$")
reSubTag = re.compile("^\[([^\]]*)\] .*$");

# indicate whether indent the output
indentOutput = False

def showUsage():
    print "Usage:"
    print "    coloredlogcat [-s <specific device>] [-v brief|time|threadtime] [--st <skipped tags>] [--sp <skipped pids] [--sub <sub_tags>] -p <pids> --tp <tags for pids> [<log filters>]"
    print "    adb [-d|-e|-s <specific device>] logcat [-v brief|time|threadtime] <log filters> | coloredlogcat [-v brief|time|threadtime] [--st <skipped tags>]  [--sub <sub_tags>] -p <pids> --tp <tags for pids>"
    print "\nOptions:"
    print "    --st  <skipped tags, seperated by ':'>"
    print "    --sp  <skipped tags, seperated by ':'>"
    print "   --sub  <sub tags, separated by ':'>"
    print "      -p  <pids, separated by ':'>"
    print "    --tp  <tags for pids, separated by ':'>"
    print "      -i  Indent the messages when wrap lines"
    print "      -s  <specific device>"
    print "      -v  same to adb logcat, only 'brief', 'time', 'threadtime' supported"
    print "\nExamples:"
    print "    $ coloredlogcat"
    print "    $ coloredlogcat ActivityManager:* *:E"
    print "    $ adb -d logcat -v brief | coloredlogcat -v brief"
    print "    $ adb logcat ActivityManager:* *:S | coloredlogcat"
    print "    $ coloredlogcat -p 1167:136 --tp ActivityManager:ImageShaderCpp"
    print "    $ coloredlogcat --sp 1234:5678"
    sys.exit(1)

try:
    opts, filtersArgs = getopt.gnu_getopt(sys.argv[1:], "his:p:v:", ["sub=","tp=","st=","sp="])
except getopt.GetoptError, err:
    print "Error: " + str(err)
    showUsage()

adb_group = 0
adb_args = ""
outputFormat = "threadtime"
timeOutputted = True
tidOutputted = True
skipped_pids = set()
skipped_tags = set()
sub_tags = set()
filter_pids = set()
filter_pid_tags = set()

for optName,  optArg in opts:
    if optName == "-s":
        adb_args = "-s " + optArg
        adb_group += 1
    elif optName == "--st":
        skipped_tags = set(optArg.split(':'))
    elif optName == "--sp":
        skipped_pids = set(optArg.split(':'))
    elif optName == "--sub":
        sub_tags = set(optArg.split(':'))
    elif optName == "-p":
        filter_pids = set(optArg.split(':'))
    elif optName == "--tp":
        filter_pid_tags = set(optArg.split(':'))
    elif optName == "-i":
        indentOutput = True
    elif optName == "-v":
        if optArg == "brief":
            outputFormat = optArg
            timeOutputted = False
            tidOutputted = False
        elif optArg == "time":
            outputFormat = optArg
            timeOutputted = True
            tidOutputted = False
        else:
            outputFormat = "threadtime"
            timeOutputted = True
            tidOutputted = True
    elif optName == "-h":
        showUsage()
    else:
        assert False,  "Unhandled option: " + optName

logcat_args = ' '.join(filtersArgs)

# if someone is piping in to us, use stdin as input.  if not, invoke adb logcat
if os.isatty(sys.stdin.fileno()):
    adb_cmd = "adb %s logcat -v %s %s" % (adb_args, outputFormat, logcat_args)
    input = os.popen(adb_cmd)
    #print "Cmd: " + adb_cmd # for debug
else:
    input = sys.stdin

linenumber = 1

while True:
    try:
        line = input.readline()
    except KeyboardInterrupt:
        break

    if outputFormat == "threadtime":
        match = retagThreadtime.match(line)
    elif outputFormat == "time":
        match = retagTime.match(line)
    else:
        match = retagBrief.match(line)

    if not match is None:
        if outputFormat == "threadtime":
            time, pid, tid, tagtype, tag, message = match.groups()
        elif outputFormat == "time":
            time, tagtype, tag, pid, message = match.groups()
        else:
            tagtype, tag, pid, message = match.groups()

        tag = tag.strip();
        if tag in skipped_tags:
            continue; # skip the tag

        if len(sub_tags) > 0:
            match2 = reSubTag.match(message)
            if match2 is None:
                continue; # skip this message
            subtag, = match2.groups()
            if not subtag in sub_tags:
                continue; # skip this message

        # Get pid from tag
        pid = pid.strip()
        if tag in filter_pid_tags:
            filter_pids.add(pid)

        if len(filter_pids) > 0 and not pid in filter_pids:
            continue; # skip the process

        if pid in skipped_pids:
            continue; # skip the process

        linebuf = StringIO.StringIO()

        # line number
        linebuf.write(" " + str(linenumber).ljust(NUMBER_WIDTH))
        linenumber += 1

        # center process info
        pid = pid.strip().center(PID_WIDTH)
        linebuf.write("%s%s%s " % (format(fg=BLACK, bg=BLACK, bright=True), pid, format(reset=True)))

        if tidOutputted:
            tid = tid.strip().center(TID_WIDTH)
            linebuf.write("%s%s%s " % (format(fg=BLACK, bg=BLACK, bright=True), tid, format(reset=True)))

        # right-align tag title and allocate color if needed
        tag = tag.strip()
        color = allocate_color(tag)
        tag = tag[-TAG_WIDTH:].rjust(TAG_WIDTH)
        linebuf.write("%s%s %s" % (format(fg=color, dim=False), tag, format(reset=True)))

        # write out tagtype colored edge
        if not tagtype in TAGTYPES: tagtype = "?"
        linebuf.write(TAGTYPES[tagtype])

        # time
        if timeOutputted:
            time = time.strip()
            linebuf.write(str("[" + time + "] ").ljust(TIME_WIDTH))

        # insert line wrapping as needed
        if indentOutput:
            headerSize = HEADER_SIZE
            if tidOutputted:
                headerSize += TID_WIDTH + 1
            if timeOutputted:
                headerSize += TIME_WIDTH
            message = indent_wrap(message, headerSize, WIDTH)

        # format tag message using rules
        for matcher in RULES:
            replace = RULES[matcher]
            message = matcher.sub(replace, message)

        linebuf.write(message)
        line = linebuf.getvalue()

        print line

    if len(line) == 0: break

print "clc had exited!!!"
