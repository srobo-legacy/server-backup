#!/usr/bin/python

"""
A script to perform daily/weekly/monthly backups.

This script runs locally, perhaps triggered by a cron system, and connects to
the server in question to create and then download a backup.

This script also handles management of the locally stored backups, within
`daily`, `weekly` and `monthly` folders, with a bias to more recent backups.
"""

import os
import sys
import datetime
import subprocess
import glob

# Some privacy please
os.umask(0177)
# Work out where to dump all our data
os.chdir(os.path.dirname(__file__))

# No options are required
if len(sys.argv) != 1:
    print >>sys.stderr, "Usage: do-backup.py"
    sys.exit(1)

# Work out what todays date is, and what to call the backup file. Format is
# just 'backup-year-month-day'
thedate = datetime.date.today()
filename = str(thedate.year) + '-' + str(thedate.month) + '-' + str(thedate.day)
filename = 'backup-' + filename
todays_filename = "daily/" + filename

lefile = open(todays_filename, 'w')

# SSH into saffron and run the backup script, generating an encrypted backup
# that's pumped into the output file. You can parametise the hostname/account
# when we have more than one server where we care about the data.
subprocess.call(['ssh', '-i', '/home/jmorse/.ssh/backup_rsa', 'backup@saffron.studentrobotics.org', 'sudo', '/srv/backup/create-backup.py', '-e', '--', 'all', '-svn'], stdout=lefile)

# If it's Sunday or the 1st of the month, link in a weekly/monthly backup.
if thedate.weekday() == 6:
    weekly_filename = "weekly/" + filename
    os.link(todays_filename, weekly_filename)

if thedate.day == 1:
    monthly_filename = "monthly/" + filename
    os.link(todays_filename, monthly_filename)

# Work through existing files, deleting those that are two old:
# Any daily backups older than 7 days
# Any weekly backups older than 6 weeks
# No monthly backups are deleted.

def kill_old_files(alist, oldest_date):
    for i in alist:
        stat = os.stat(i)
        # Check last modified date; no birthdate appears to be installed
        # (at least on my ext4 machine), and this conveniently means if you want
        # to keep a backup for longer all you need do is touch it.
        cdate = datetime.date.fromtimestamp(stat.st_mtime)
        if cdate < oldest_date:
            os.unlink(i)

# 7 days ago
ago = datetime.timedelta(7)
old = thedate - ago
kill_old_files(glob.glob('daily/*'), old)

# 6 weeks ago
ago = datetime.timedelta(42)
old = thedate - ago
kill_old_files(glob.glob('weekly/*'), old)
