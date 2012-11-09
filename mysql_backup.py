#!/usr/bin/python

import ConfigParser

config = ConfigParser.SafeConfigParser()
config.read("backup.ini")
list_of_dbs = config.get("mysql", "databases")
print repr(list_of_dbs)
