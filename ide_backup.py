#!/usr/bin/python

import glob, os, sys
import tarfile

# le privacy
os.umask(0177)

try:
  os.makedirs('ide_repos', 0700)
except os.error:
  pass

output = tarfile.open('ide_repo_backup.tar', mode='w')

# Back up user repos: we only want the _master_ copies of everything, not the
# user checkouts of repos, which I understand are only used for staging changes
# before being pushed back to master.
os.chdir('/var/www/html/ide/repos/')
list_of_dirs = glob.glob('./*/master')

for dir in list_of_dirs:
    output.add(dir, recursive=True)

output.close()
