#!/usr/bin/python

import ConfigParser
import os

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

for s in list_of_dbs:
    os.system("mysqldump {0} -u root -p > mysql_dbs/{1}".format(s, s))
