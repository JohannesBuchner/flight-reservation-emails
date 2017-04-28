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

	For email programs with mailbox, mb2md (http://batleth.sapienti-sat.org/projects/mb2md/) can be run to convert to maildir, followed by "notmuch new"
	
	For Thunderbird, the thunderbird-notmuch-import.py script is provided,
	which finds the relevant folders automatically.

2. Building the report

	run::
	
		$ python summary.py


Features implemented
----------------------

Parsing of the flight reservations schema following 
https://developers.google.com/gmail/markup/reference/flight-reservation


To Do
------------

* Not all eticket emails follow this schema. Google uses machine learning to parse more emails. Some simple parsing to handle more emails would be nice. Contributions welcome!
* implement hotel bookings (https://developers.google.com/gmail/markup/reference/hotel-reservation). Booking.com and some others produce the json version.





