Flight & Hotel reservation email parser
========================================

Searches emails for flight tickets and hotel reservations.
Builds a brief summary view of all your reservations over time.


--------
Usage
--------


1. Adding emails to the email database

	People store emails in various ways. 
	Here we support the notmuch database (https://notmuchmail.org/)
	It is trivial to include maildir emails into notmuch with "notmuch new".

	For email programs with mailbox, mb2md (http://batleth.sapienti-sat.org/projects/mb2md/) can be run to convert to maildir::

		$ perl mb2md-3.20.pl -s $HOME/.thunderbird/..../Mail/Local\ Folders/Inbox -d MyMailMD/

	and then "notmuch new" be run onto the MyMailMD

2. Building the report

	run::
	
		$ python summary.py





