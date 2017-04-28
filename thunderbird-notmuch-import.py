import configparser
import os
import glob
import subprocess

thunderbirdpath = os.path.join(os.environ['HOME'], '.thunderbird')
cf = configparser.ConfigParser()
cf.read(os.path.join(thunderbirdpath, 'profiles.ini'))

paths = []

for s in cf.sections():
	if cf.has_option(s, 'Default') and cf.getint(s, 'Default') == 1:
		path = cf.get(s, 'Path')
		if cf.getint(s, 'IsRelative') == 1:
			path = os.path.join(thunderbirdpath, path)
		paths += glob.glob(os.path.join(path, 'ImapMail/*/INBOX*'))
		paths += glob.glob(os.path.join(path, 'Mail/*/Inbox'))

print '# getting notmuch path ...'
o = None
try:
	p = subprocess.Popen(['notmuch', 'config', 'get', 'database.path'], stdout=subprocess.PIPE)
	if p.wait() == 0:
		o = p.stdout.read().strip()
except OSError:
	print 'ERROR could not check notmuch config'
	print '      make sure notmuch is installed and configured with "notmuch config"'

print '# will export maildir into %s' % o
print '# execute the following commands:'

for p in paths:
	if p.endswith('.msf') or 'trash' in p.lower(): 
		continue
	print "perl mb2md-3.20.pl -s '%s' -d '%s'" % (p, o)

print 
print 'notmuch new'


