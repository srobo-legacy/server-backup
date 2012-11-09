#!/usr/bin/python

import ConfigParser
import os
import sys
import tarfile
import tempfile

os.umask(0177)

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

output = tarfile.open('mysql_backups.tar', mode='w')

# Attempt to dump the set of databases into some files. This relies on my.cnf
# being configured in $HOME, and a mysqldump section existing in there.
for s in list_of_dbs:
    handle, filename = tempfile.mkstemp()
    os.close(handle)
    os.system("mysqldump {0} > {1}".format(s, filename))

    # And put that into the tarfile.
    statres = os.stat(filename)
    info = tarfile.TarInfo(name="{0}.mysql".format(s))
    info.size = statres.st_size
    output.addfile(tarinfo=info, fileobj=open(filename, 'r'))
    os.unlink(filename)

output.close()
