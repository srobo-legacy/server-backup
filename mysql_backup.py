#!/usr/bin/python

import ConfigParser
import os
import sys

try :
    os.stat("backup.ini")
except OSError:
    sys.stderr.write("mysql backup must have backup.ini\n")
    sys.exit(1)

config = ConfigParser.SafeConfigParser()
config.read("backup.ini")
list_of_dbs_str = config.get("mysql", "databases")

# Turn ugly ugly ini string into a list of db names.
list_of_dbs = list_of_dbs_str.split(',')
for s in list_of_dbs:
    s.strip()

try:
  os.makedirs('mysql_dbs', 0600)
except os.error: 
  pass

# Attempt to dump the set of databases into some files. This relies on my.cnf
# being configured in $HOME, and a mysqldump section existing in there.
for s in list_of_dbs:
    os.system("mysqldump {0} > mysql_dbs/{1}".format(s, s))
