#!/usr/bin/python

import glob, os, sys, shutil

# le privacy
os.umask(0177)

try:
  os.makedirs('ide_repos', 0700)
except os.error:
  pass

# Back up user repos: we only want the _master_ copies of everything, not the
# user checkouts of repos, which I understand are only used for staging changes
# before being pushed back to master.
list_of_dirs = glob.glob('/var/www/html/ide-off/repos/*/master')
for dir in list_of_dirs:
    # Extract what the team number is
    teamnum = os.path.basename(os.path.dirname(dir))
    targetdir = 'ide_repos/{0}'.format(teamnum)

    # Copy the master dir into there, with all relevant git repos.
    shutil.copytree(dir, targetdir)
