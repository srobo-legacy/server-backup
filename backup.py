#!/usr/bin/python

import glob, os, sys
import tarfile
import ldap
from ldif import LDIFParser,LDIFWriter
import ConfigParser
import time
import tempfile
import argparse
import subprocess

os.umask(0177)

parser = argparse.ArgumentParser()
parser.add_argument('what', help='What data to back up')
parser.add_argument('-e', help='Encrypt output. Requires gpg_keyring',
                    action='store_true')

args = parser.parse_args()

# Read our config
config = ConfigParser.SafeConfigParser()

# What's the location of *this* file?
thisdir = os.path.dirname(__file__)
backupfile = '{0}/backup.ini'.format(thisdir)

if not os.path.exists(backupfile)
    sys.stderr.write('No backup config file at {0}'.format(backupfile))
    sys.exit(1)

config.read("{0}/backup.ini".format(thisdir))

# A series of backup functions. They all take a tarfile object and put relevant
# data into them.

def do_ide_backup(tar_output):
    # Back up user repos: we only want the _master_ copies of everything, not
    # the user checkouts of repos, which I understand are only used for staging
    # changes before being pushed back to master.
    ide_location = config.get('ide', 'location')
    os.chdir(ide_location)
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
    handle, tmpfilename1 = tempfile.mkstemp()
    os.close(handle)
    os.system('ldapsearch -D cn=Manager,o=sr -y /etc/ldap.secret -x -h localhost "(objectClass=*)" -b ou=users,o=sr > {0}'.format(tmpfilename1))
    os.system('ldapsearch -D cn=Manager,o=sr -y /etc/ldap.secret -x -h localhost "(objectClass=*)" -b ou=groups,o=sr >> {0}'.format(tmpfilename1))

    # Code below procured from ldif parser documentation. Is fed an ldap,
    # reformats a couple of entries to be modifications rather than additions.
    # This is so that some special, puppet-created and configured groups, can be
    # backed up and restored. Without this, adding groups like shell-users
    # during backup restore would be an error.

    make_modify = ["cn=shell-users,ou=groups,o=sr", "cn=mentors,ou=groups,o=sr",
		   "cn=srusers,ou=groups,o=sr"]
    remove = ["uid=ide,ou=users,o=sr", "uid=anon,ou=users,o=sr"]

    # This class hooks into processing an ldif
    class MyLDIF(LDIFParser):
        def __init__(self,input,output):
            LDIFParser.__init__(self,input)
            self.writer = LDIFWriter(output)

       # Encode special dn-specific backup logic here.
        def handle(self,dn,entry):
            if dn in make_modify:
                ponies = entry['memberUid']
                self.writer.unparse(dn,[(ldap.MOD_REPLACE, 'memberUid', ponies)])
                return
            elif dn in remove:
                return
            elif dn == None:
                return
            else:
                self.writer.unparse(dn,entry)

    # Open the ldif generated before, dump it into another tmpe file with
    # relevant modification.
    handle, tmpfilename2 = tempfile.mkstemp()
    os.close(handle)
    parser = MyLDIF(open(tmpfilename1, 'rb'), open(tmpfilename2, "wb"))
    parser.parse()

    statres = os.stat(tmpfilename2)
    info = tarfile.TarInfo(name="ldap_backup")
    info.mtime = time.time()
    info.size = statres.st_size
    tar_output.addfile(tarinfo=info, fileobj=open(tmpfilename2, 'r'))

    os.unlink(tmpfilename1)
    os.unlink(tmpfilename2)

def do_mysql_backup(tar_output):
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

    if os.path.exists('/etc/pki/tls/certs/www.studentrobotics.org.crt'):
       my_addfile('https/server.crt',
                  '/etc/pki/tls/certs/www.studentrobotics.org.crt')
    else:
       my_addfile('https/server.crt',
                  '/etc/pki/tls/certs/server.crt')

    if os.path.exists('/etc/pki/tls/certs/gd_bundle.crt')
        my_addfile('https/gd_bundle.crt', '/etc/pki/tls/certs/gd_bundle.crt')

    my_addfile('https/server.key', '/etc/pki/tls/private/server.key')
    my_addfile('login/ssh_host_dsa_key', '/etc/ssh/ssh_host_dsa_key')
    my_addfile('login/ssh_host_dsa_key.pub', '/etc/ssh/ssh_host_dsa_key.pub')
    my_addfile('login/ssh_host_rsa_key', '/etc/ssh/ssh_host_rsa_key')
    my_addfile('login/ssh_host_rsa_key.pub', '/etc/ssh/ssh_host_rsa_key.pub')
    my_addfile('login/ssh_host_key', '/etc/ssh/ssh_host_key')
    my_addfile('login/ssh_host_key.pub', '/etc/ssh/ssh_host_key.pub')

    if os.path.exist('/home/gerrit'):
        os.stat('/home/gerrit')
        my_addfile('gerrit_ssh_host_dsa_key',
                   '/home/gerrit/srdata/etc/ssh_host_dsa_key')
        my_addfile('gerrit_ssh_host_dsa_key.pub',
                   '/home/gerrit/srdata/etc/ssh_host_dsa_key.pub')
        my_addfile('gerrit_ssh_host_rsa_key',
                   '/home/gerrit/srdata/etc/ssh_host_rsa_key')
        my_addfile('gerrit_ssh_host_rsa_key.pub',
                   '/home/gerrit/srdata/etc/ssh_host_rsa_key.pub')
    else:
      sys.stderr.write("Gerrit doesn't appear to be installed, skipping\n")

    if os.path.exists('/srv/secrets/common.csv'):
      my_addfile('common.csv', '/srv/secrets/common.csv')
    else:
      sys.stderr.write("common.csv isn't installed, you're not using puppet?\n")

    if os.path.exists('/home/backup/.ssh/authorized_keys'):
      my_addfile('login/backups_ssh_keys', '/home/backup/.ssh/authorized_keys')
    else:
      sys.stderr.write("No backup ssh keys, assuming not using puppet yet\n")

def do_trac_backup(tar_output):
    os.chdir('/srv/trac')
    tar_output.add('sr', recursive=True)

def do_gerrit_backup(tar_output):
    # Only backup all-projects, which counts as config. Everything else is in
    # mysql.
    os.chdir('/home/gerrit/srdata/git/')
    tar_output.add('All-Projects.git', recursive=True)

# Allow people to try and backup git, and tell them how to do it properly.
# Given the nature of git repos, rsync is the most efficient way of performing
# this backup.
if args.what == 'git':
    print "Run `rsync -az optimus:/srv/git/ ./git/` to backup git into the 'git' dir"
    sys.exit(1)

# Mapping between data names and the functions that back them up.
things = { 'ldap': do_ldap_backup,
           'mysql' : do_mysql_backup,
           'secrets' : do_secrets_backup,
           'ide' : do_ide_backup,
           'trac' : do_trac_backup,
           'gerrit' : do_gerrit_backup,
         }

# Check that the piece of data we're backing up has a function to do it.
if not args.what in things:
    sys.stderr.write("{0} can't be backed up\n".format(args.what))
    sys.exit(1)

# Select the backup function.
backup_func = things[args.what]

# Final output should be stdout.
finaloutput = sys.stdout
if sys.stdout.isatty():
    sys.stderr.write('Refusing to write a tarfile to your terminal\n')
    sys.exit(1)

# Are we going to be pumping data through gpg?
if args.e:
    # Form a list of people who can decrypt the backup,
    crypt_identity_str = config.get("crypt", "cryptkey")

    crypt_identities = crypt_identity_str.split(',')
    for s in crypt_identities:
        s.strip()

    callargs = ['gpg', '--batch', '--encrypt']
    for i in crypt_identities:
        callargs.append('-r')
        callargs.append(i)

    call = subprocess.Popen(callargs, stdin=subprocess.PIPE, stdout=finaloutput)
    finaloutput = call.stdin

# Create a compressed tarball.
outputtar = tarfile.open(fileobj=finaloutput, mode="w|gz")

# Actually perform the desired backup.
backup_func(outputtar)

outputtar.close()
