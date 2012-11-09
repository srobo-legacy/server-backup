#!/usr/bin/python

import glob, os, sys

# le privacy
os.umask(0177)

try:
  os.makedirs('ide_repos', 0700)
except os.error:
  pass

# Back up user repos: we only want the _master_ copies of everything, not the
# user checkouts of repos, which I understand are only used for staging changes
# before being pushed back to master.
list_of_dirs = glob.glob('/var/www/html/ide/repos/*/master')
print repr(list_of_dirs)
for dir in list_of_dirs:
    teamnum = os.path.basename(os.path.dirname(dir))
    print teamnum
