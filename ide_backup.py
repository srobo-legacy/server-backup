#!/usr/bin/python

import glob, os, sys
import tarfile

def do_backup(tar_output):
    # Back up user repos: we only want the _master_ copies of everything, not
    # the user checkouts of repos, which I understand are only used for staging
    # changes before being pushed back to master.
    os.chdir('/var/www/html/ide/')
    list_of_dirs = glob.glob('./repos/*/master')

    for dir in list_of_dirs:
        tar_output.add(dir, recursive=True)

    # Also back up user settings. This contains team-status data too.
    tar_output.add('settings', recursive=True)

    # Also the notifications directory: I've no idea what this really is, but
    # it's not large.

    tar_output.add('notifications', recursive=True)
