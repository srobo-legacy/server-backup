#!/usr/bin/python

import glob, os, sys
import tarfile
import ldap
from ldif import LDIFParser,LDIFWriter
import ConfigParser
import time
import tempfile
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('what', help='What data to back up')
parser.add_argument('output_file', help='Output tgz target, - for stdout')

args = parser.parse_args()

# A series of backup functions. They all take a tarfile object and put relevant
# data into them.

def do_git_backup(tar_output):
    print "Run `rsync -az optimus:/srv/git/ ./git/` to backup git into the 'git' dir"

def do_ide_backup(tar_output):
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

def do_ldap_backup(tar_output):
    # Produce an ldif of all users and groups. All other ldap objects, such as
    # the organizational units and the Manager entity, are managed by puppet in 
    # the future.
    os.system('ldapsearch -D cn=Manager,o=sr -y managerpw -x -h localhost "(objectClass=*)" -b ou=users,o=sr > tmp_ldap_ldif')
    os.system('ldapsearch -D cn=Manager,o=sr -y managerpw -x -h localhost "(objectClass=*)" -b ou=groups,o=sr >> tmp_ldap_ldif')

    # Code below procured from ldif parser documentation. Is fed an ldap,
    # reformats a couple of entries to be modifications rather than additions.
    # This is so that some special, puppet-created and configured groups, can be
    # backed up and restored. Without this, adding groups like shell-users
    # during backup restore would be an error.

    # This class hooks into processing an ldif
    class MyLDIF(LDIFParser):
       def __init__(self,input,output):
          LDIFParser.__init__(self,input)
          self.writer = LDIFWriter(output)

       # Encode special dn-specific backup logic here.
       def handle(self,dn,entry):
          if dn == "cn=shell-users,ou=groups,o=sr":
            ponies = entry['memberUid']
            self.writer.unparse(dn,[(ldap.MOD_REPLACE, 'memberUid', ponies)])
            return
          elif dn == None:
            return
          else:
            self.writer.unparse(dn,entry)

    # Open the ldif generated before, dump it into ldap_backup with relevant
    # modification.
    parser = MyLDIF(open("tmp_ldap_ldif", 'rb'), open("ldap_backup", "wb"))
    parser.parse()

    os.unlink("tmp_ldap_ldif")

def do_mysql_backup(tar_output):
    config = ConfigParser.SafeConfigParser()
    config.read("backup.ini")
    list_of_dbs_str = config.get("mysql", "databases")

    # Turn ugly ugly ini string into a list of db names.
    list_of_dbs = list_of_dbs_str.split(',')
    for s in list_of_dbs:
        s.strip()

    # Attempt to dump the set of databases into some files. This relies on
    # my.cnf being configured in $HOME, and a mysqldump section existing in
    # there.
    for s in list_of_dbs:
        handle, filename = tempfile.mkstemp()
        os.close(handle)
        os.system("mysqldump {0} > {1}".format(s, filename))

        # And put that into the tarfile.
        statres = os.stat(filename)
        info = tarfile.TarInfo(name="{0}.mysql".format(s))
        info.mtime = time.time()
        info.size = statres.st_size
        tar_output.addfile(tarinfo=info, fileobj=open(filename, 'r'))
        os.unlink(filename)

def do_secrets_backup(tar_output):
    def my_addfile(tarname, srcfile):
        thestat = os.stat(srcfile)
        info = tarfile.TarInfo(name=tarname)
        info.mtime = time.time()
        info.size = thestat.st_size
        tar_output.addfile(tarinfo=info, fileobj=open(srcfile))

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

# Mapping between names and the functions that implement them.
things = { 'ldap': do_ldap_backup,
           'mysql' : do_mysql_backup,
           'secrets' : do_secrets_backup,
           'ide' : do_ide_backup,
           'git' : do_git_backup,
         }
