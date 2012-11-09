#!/usr/bin/python

import sys
import os
import ldap
from ldif import LDIFParser,LDIFWriter

# Privacy please
os.umask(0177)

# Produce an ldif of all users and groups. All other ldap objects, such as the
# organizational units and the Manager entity, are managed by puppet in the
# future.
os.system('ldapsearch -D cn=Manager,o=sr -y managerpw -x -h localhost "(objectClass=*)" -b ou=users,o=sr > tmp_ldap_ldif')
os.system('ldapsearch -D cn=Manager,o=sr -y managerpw -x -h localhost "(objectClass=*)" -b ou=groups,o=sr >> tmp_ldap_ldif')

# Code below procured from ldif parser documentation. Is fed an ldap, reformats
# a couple of entries to be modifications rather than additions. This is so
# that some special, puppet-created and configured groups, can be backed up
# and restored. Without this, adding groups like shell-users during backup
# restore would be an error.

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
