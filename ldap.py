#!/usr/bin/python

import sys
import os
import ldap
from ldif import LDIFParser,LDIFWriter

# Privacy please
os.umask(0177)

os.system('ldapsearch -D cn=Manager,o=sr -y managerpw -x -h localhost "(objectClass=*)" -b ou=users,o=sr > tmp_ldap_ldif')
os.system('ldapsearch -D cn=Manager,o=sr -y managerpw -x -h localhost "(objectClass=*)" -b ou=groups,o=sr >> tmp_ldap_ldif')

# Code below procured from ldif parser documentation

class MyLDIF(LDIFParser):
   def __init__(self,input,output):
      LDIFParser.__init__(self,input)
      self.writer = LDIFWriter(output)

   def handle(self,dn,entry):
      if dn == "cn=shell-users,ou=groups,o=sr":
        ponies = entry['memberUid']
        self.writer.unparse(dn,[(ldap.MOD_REPLACE, 'memberUid', ponies)])
        return
      elif dn == None:
        return
      else:
        self.writer.unparse(dn,entry)

parser = MyLDIF(open("tmp_ldap_ldif", 'rb'), open("ldap_backup", "wb"))
parser.parse()

os.unlink("tmp_ldap_ldif")
