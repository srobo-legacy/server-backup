#!/usr/bin/python3

"""
A script to create a backup of a Student Robotics server.

This script runs on the server itself and collects the important data into a tar
file, optionally compressing and encrypting that file.
"""

import glob, os, sys
import tarfile
import configparser
import time
import tempfile
import argparse
import subprocess

import ldap
from ldif import LDIFParser,LDIFWriter

os.umask(0o177)

# Read our config
config = configparser.SafeConfigParser()

# What's the location of *this* file?
thisdir = os.path.dirname(__file__)
backupfile = '{0}/backup.ini'.format(thisdir)

if not os.path.exists(backupfile):
    print("No backup config file at {0}".format(backupfile), file=sys.stderr)
    sys.exit(1)

config.read(backupfile)

# A series of backup functions. They all take a tarfile object and put relevant
# data into them.

def do_ide_backup(tar_output: tarfile.TarFile) -> int:
    # Back up user repos: we only want the _master_ copies of everything, not
    # the user checkouts of repos, which I understand are only used for staging
    # changes before being pushed back to master.
    ide_location = config.get('ide', 'location')
    os.chdir(ide_location)
    list_of_dirs = glob.glob('./repos/*/master')

    for dir in list_of_dirs:
        arcname = '/ide' + dir[1:]
        tar_output.add(dir, arcname=arcname, recursive=True)

    # Also back up user settings. This contains team-status data too.
    tar_output.add('settings', arcname='ide/settings', recursive=True)

    # Also the notifications directory: I've no idea what this really is, but
    # it's not large.

    tar_output.add('notifications', arcname='ide/notifications', recursive=True)
    return 0

def do_team_status_images_backup(tar_output: tarfile.TarFile) -> int:
    tsimg_location = config.get('team_status_images', 'location')
    os.chdir(tsimg_location)
    tar_output.add('.', arcname='team_status_images', recursive=True)
    return 0

def do_forum_attachments_backup(tar_output: tarfile.TarFile) -> int:
    tsimg_location = config.get('forum_attachments', 'location')
    os.chdir(tsimg_location)
    tar_output.add('.', arcname='forum_attachments', recursive=True)
    return 0

def do_ldap_backup(tar_output: tarfile.TarFile) -> int:
    # Produce an ldif of all users and groups. All other ldap objects, such as
    # the organizational units and the Manager entity, are managed by puppet in
    # the future.
    result = 0
    handle, tmpfilename1 = tempfile.mkstemp()
    os.close(handle)
    ret = os.system('ldapsearch -LLL -z 0 -D cn=Manager,o=sr -y /etc/ldap.secret -x -h localhost "(objectClass=posixAccount)" -b ou=users,o=sr > {0}'.format(tmpfilename1))
    if not os.WIFEXITED(ret) or os.WEXITSTATUS(ret) != 0:
        print("Couldn't backup ldap users", file=sys.stderr)
        result = 1

    ret = os.system('ldapsearch -LLL -z 0 -D cn=Manager,o=sr -y /etc/ldap.secret -x -h localhost "(objectClass=posixGroup)" -b ou=groups,o=sr >> {0}'.format(tmpfilename1))
    if not os.WIFEXITED(ret) or os.WEXITSTATUS(ret) != 0:
        print("Couldn't backup ldap groups", file=sys.stderr)
        result = 1

    # Code below procured from ldif parser documentation. Is fed an ldap,
    # reformats a couple of entries to be modifications rather than additions.
    # This is so that some special, puppet-created and configured groups, can be
    # backed up and restored. Without this, adding groups like shell-users
    # during backup restore would be an error.

    make_modify = ["cn=shell-users,ou=groups,o=sr", "cn=mentors,ou=groups,o=sr",
                    "cn=srusers,ou=groups,o=sr", "cn=withdrawn,ou=groups,o=sr",
                    "cn=media-consent,ou=groups,o=sr"]
    remove = ["uid=ide,ou=users,o=sr", "uid=anon,ou=users,o=sr"]

    # This class hooks into processing an ldif
    class MyLDIF(LDIFParser):
        def __init__(self,input,output):
            LDIFParser.__init__(self,input)
            self.writer = LDIFWriter(output)

       # Encode special dn-specific backup logic here.
        def handle(self,dn,entry):
            if dn in make_modify:
                if not 'memberUid' in entry:
                    # No members in this group, discard
                    return

                members = entry['memberUid']
                self.writer.unparse(dn,[(ldap.MOD_REPLACE,'memberUid',members)])
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
    infile = open(tmpfilename1, 'r')
    outfile = open(tmpfilename2, 'w')
    parser = MyLDIF(infile, outfile)
    parser.parse()
    infile.close()
    outfile.close()

    tar_output.add(tmpfilename2, arcname="ldap/ldap_backup")

    os.unlink(tmpfilename1)
    os.unlink(tmpfilename2)
    return result

def do_mysql_backup(tar_output: tarfile.TarFile) -> int:
    result = 0
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
        ret = os.system("mysqldump {0} > {1}".format(s, filename))
        if not os.WIFEXITED(ret) or os.WEXITSTATUS(ret) != 0:
            print("Couldn't dump database {0}".format(s), file=sys.stderr)
            result = 1
            os.unlink(filename)
            continue

        # And put that into the tarfile.
        tar_output.add(filename, arcname="mysql/{0}.db".format(s))
        os.unlink(filename)

    return result

def do_secrets_backup(tar_output: tarfile.TarFile) -> int:
    def my_addfile(tarname: str, srcfile: str):
        thestat = os.stat(srcfile)
        info = tarfile.TarInfo(name=tarname)
        info.mtime = time.time()
        info.size = thestat.st_size
        tar_output.addfile(tarinfo=info, fileobj=open(srcfile, 'rb'))

    if os.path.exists('/etc/pki/tls/certs/www.studentrobotics.org.crt'):
       my_addfile('https/server.crt',
                  '/etc/pki/tls/certs/www.studentrobotics.org.crt')
    else:
       my_addfile('https/server.crt',
                  '/etc/pki/tls/certs/server.crt')

    if os.path.exists('/etc/pki/tls/certs/comodo_bundle.crt'):
        my_addfile('https/comodo_bundle.crt', '/etc/pki/tls/certs/comodo_bundle.crt')

    my_addfile('https/server.key', '/etc/pki/tls/private/server.key')
    my_addfile('login/ssh_host_rsa_key', '/etc/ssh/ssh_host_rsa_key')
    my_addfile('login/ssh_host_rsa_key.pub', '/etc/ssh/ssh_host_rsa_key.pub')

    my_addfile('patience.studentrobotics.org.yaml', '/srv/secrets/patience.studentrobotics.org.yaml')
    my_addfile('login/backups_ssh_keys', '/home/backup/.ssh/authorized_keys')
    my_addfile('login/monitoring_ssh_keys', '/home/monitoring/.ssh/authorized_keys')

    my_addfile('tickets/config.ini', '/var/www/html/tickets/tickets/webapi/config.ini')
    my_addfile('tickets/ticket.key', '/var/www/html/tickets/tickets/ticket.key')

    my_addfile('mcfs/ticket.key', '/var/www/html/mediaconsent/tickets/ticket.key')

    return 0

def do_trac_backup(tar_output: tarfile.TarFile) -> int:
    os.chdir('/srv/trac')
    tar_output.add('.', arcname='trac', recursive=True)
    return 0

def do_gerrit_backup(tar_output: tarfile.TarFile) -> int:
    # Only backup all-projects, which counts as config. Everything else is in
    # mysql.
    os.chdir('/home/gerrit/srdata/git/')
    tar_output.add('All-Projects.git', recursive=True)

    return 0

def do_svn_backup(tar_output: tarfile.TarFile) -> int:
    # Run svnadmin dump through gzip and use that for the backup.
    result = 0
    handle, filename = tempfile.mkstemp()
    admincall = subprocess.Popen(['svnadmin', 'dump', '/srv/svn/sr', '--deltas'],
                                 stdout=subprocess.PIPE,
                                 stderr=open('/dev/null', 'w'))
    gzipcall = subprocess.Popen(['gzip'], stdin=admincall.stdout, stdout=handle)
    admincall.wait()
    gzipcall.wait()
    if admincall.returncode != 0 or gzipcall.returncode != 0:
        print("SVN dump failed", file=sys.stderr)
        result = 1
    os.close(handle)
    tar_output.add(filename, arcname='svn/db.gz')
    os.unlink(filename)
    return result

def do_sqlite_backup(comp_name: str, dblocation: str, arcname: str, tar_output: tarfile.TarFile) -> int:
    # Backup contents of a sqlite database. Use sqlite backup command to
    # create a backup first. This essentially copies the db file, but performs
    # all the required lock dancing.
    result = 0
    handle, filename = tempfile.mkstemp()
    backupcall = subprocess.Popen(['sqlite3', dblocation, '.dump'],
                                   stdout=subprocess.PIPE,
                                  stderr=open('/dev/null', 'w'))
    gzipcall = subprocess.Popen(['gzip'], stdin=backupcall.stdout, stdout=handle)
    backupcall.wait()
    gzipcall.wait()
    if backupcall.returncode != 0 or gzipcall.returncode != 0:
        print("{0} DB dump failed".format(comp_name), file=sys.stderr)
        result = 1
    os.close(handle)
    tar_output.add(filename, arcname=arcname + 'sqlite3_dump.gz')
    os.unlink(filename)
    return result

def do_nemesis_backup(tar_output: tarfile.TarFile) -> int:
    dblocation = config.get('nemesis', 'dblocation')
    return do_sqlite_backup("Nemesis", dblocation, "nemesis/", tar_output)

def do_fritter_backup(tar_output: tarfile.TarFile) -> int:
    dblocation = config.get('fritter', 'dblocation')
    return do_sqlite_backup("Fritter", dblocation, "fritter/", tar_output)

def do_all_backup(tar_output: tarfile.TarFile) -> int:
    result = 0
    for i in things.keys():
        if i != 'all':
            newresult = things[i](tar_output)
            if newresult != 0:
                result = 1

    return result

# Mapping between data names and the functions that back them up.
things = { 'ldap': do_ldap_backup,
           'mysql' : do_mysql_backup,
           'secrets' : do_secrets_backup,
           'ide' : do_ide_backup,
           'team_status_images' : do_team_status_images_backup,
           'forum_attachments' : do_forum_attachments_backup,
           'trac' : do_trac_backup,
           'gerrit' : do_gerrit_backup,
           'svn' : do_svn_backup,
           'nemesis' : do_nemesis_backup,
           'fritter' : do_fritter_backup,
         }

what_values = ', '.join(things.keys())
parser = argparse.ArgumentParser()
parser.add_argument('what', help='What data to back up. One of: ' + what_values,
                    nargs = "*")
parser.add_argument('-e', help='Encrypt output. Requires gpg_keyring',
                    action='store_true')

args = parser.parse_args()

sources = set()

for desc in args.what:

    if desc[0] == "-":
        "'-' prefix means exclude this thing"
        name = desc[1:]
        exclude = True
    else:
        name = desc
        exclude = False

    if name == "git":
        # Allow people to try and backup git, and tell them how to do it properly.
        # Given the nature of git repos, rsync is the most efficient way of performing
        # this backup.
        print("Run `rsync -az optimus:/srv/git/ ./git/` to backup git into the 'git' dir")
        sys.exit(1)

    if name == "all":
        "All the things"
        if exclude:
            print("Excluding all is not supported -- aborting.", file=sys.stderr)
            exit(1)

        for v in things.keys():
            sources.add(v)

    else:
        if name not in things:
            "That thing has no backup function"
            print("No backup definition for", name, file=sys.stderr)
            parser.parse_args(['-h'])   # Hack to show the help.
            sys.exit(1)

        if exclude:
            try:
                sources.remove( name )
            except KeyError:
                print("Cannot exclude '{0}' as it is not already included.".format(name), file=sys.stderr)
                exit(1)
        else:
            sources.add( name )

print("Backing up", ", ".join( sources ), file=sys.stderr)

# Final output should be stdout.
finaloutput = sys.stdout.buffer
if sys.stdout.isatty():
    print("Refusing to write a tarfile to your terminal", file=sys.stderr)
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

result = 0

for source in sources:

    # Select the backup function.
    backup_func = things[source]

    # Actually perform the desired backup.
    newresult = backup_func(outputtar)

    if newresult != 0:
        print("Failed to backup {0} (exit code {1})".format( source, newresult ), file=sys.stderr)
        result = 1

outputtar.close()

if result != 0:
    print("Errors in backup", file=sys.stderr)
sys.exit(result)
