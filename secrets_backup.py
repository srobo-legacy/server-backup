#!/usr/bin/python

import sys
import os
import tarfile
import time

os.umask(0177)

# Produce a tarfile containing our secret keys.

output = tarfile.open('secret_keys_backup.tar.gz', mode='w:gz')

def my_addfile(tarname, srcfile):
    thestat = os.stat(srcfile)
    info = tarfile.TarInfo(name=tarname)
    info.mtime = time.time()
    info.size = thestat.st_size
    output.addfile(tarinfo=info, fileobj=open(srcfile))

my_addfile('www.studentrobotics.org.crt', '/etc/pki/tls/certs/www.studentrobotics.org.crt')
my_addfile('godaddy_bundle.crt', '/etc/pki/tls/certs/gd_bundle.crt')
my_addfile('server.key', '/etc/pki/tls/private/server.key')
my_addfile('ssh_host_dsa_key', '/etc/ssh/ssh_host_dsa_key')
my_addfile('ssh_host_dsa_key.pub', '/etc/ssh/ssh_host_dsa_key.pub')
my_addfile('ssh_host_rsa_key', '/etc/ssh/ssh_host_rsa_key')
my_addfile('ssh_host_rsa_key.pub', '/etc/ssh/ssh_host_rsa_key.pub')
my_addfile('ssh_host_key', '/etc/ssh/ssh_host_key')
my_addfile('ssh_host_key.pub', '/etc/ssh/ssh_host_key.pub')

try:
    os.stat('/home/gerrit')
    my_addfile('gerrit_ssh_host_dsa_key', '/home/gerrit/srdata/etc/ssh_host_dsa_key')
    my_addfile('gerrit_ssh_host_dsa_key.pub', '/home/gerrit/srdata/etc/ssh_host_dsa_key.pub')
    my_addfile('gerrit_ssh_host_rsa_key', '/home/gerrit/srdata/etc/ssh_host_rsa_key')
    my_addfile('gerrit_ssh_host_rsa_key.pub', '/home/gerrit/srdata/etc/ssh_host_rsa_key.pub')
except os.error:
  sys.stderr.write("Gerrit doesn't appear to be installed, skipping\n")

output.close()
