# Server Backup

This git repo contains scripts for backing up various wadges of data from the
SR server into some kind of manipulatable form.

These scripts aim to back up data into the same format used for the secrets
directory in the puppet/server configuration. Given how infrequently restores
are going to occur, bugs in the layout are likely.

## Basic usage

A copy of this repo is installed onto our servers by the puppet config. You can
either manually run the `create-backup.py` script via ssh, or use the
`do-backup.py` script to handle both creating backups and management of local
backup files.

## Configuration

Some of the locations and details of things to include are provided via
a config `backup.ini` file, which the script checks for. This is provided
by puppet on the live server, but a sample file is provided as `example.ini`
to ease development.

Any changes to existing key names, or additions of keys, need to be mirrored
in `srobo.org/server/puppet.git/modules/sr-site/templates/backup.ini.erb`.

## Encrypting

There is the option of encrypting the output of the backup. The intention being
that backing up of data can be done by cron on a remote machine under someones
user account, without us having to worry about additional access controls.

To do this, specify the -e switch. Currently the backup script will use whatever
key identies are in backup.ini, as configured by puppet. These need to be public
keys installed to root's keyring and _signed_ by root as well. These steps
shouldn't ever make their way into automated configuration, given how
important the decisions about who gets access to backups is.

## Room for improvement

Right now, backing up ldap and mysql involves manipulating a number of temporary
files so that they can be put in the tarball. This appears to be due to a
limitation of the tar format, in that I can't stream data into one, as it
requires the size of file in advance. Using a different file format that allows
this would be better, even if it meant stooping as low as zips.
