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

	run with some email search keywords::
	
		$ python summary.py 'schema.org/FlightReservation OR ticket OR flight OR flug OR viaje OR booking OR confirmation OR confirmacion'

	It will give you some idea of what it finds, for example::
	
		2015-11-28 Flight HOUSTON, TX --> WASHINGTON, DC

		Departing 2015-11-28 19:10 
		from HOUSTON, TX  
		arriving 2015-11-28 23:05
		To   WASHINGTON, DC  
		Flight number UA1955
		   
3. View report
	
	For an example report see "summary.html"!
	
	

Features implemented
----------------------

* Summary of all flights, with crucial information (when, from-to, ...)
* Including PDF eticket files, extracted from emails.
* Parallel parsing for speed-up.
* Parsing of the flight reservations schema following 
https://developers.google.com/gmail/markup/reference/flight-reservation
* Some heuristic parsing of html emails in English, Spanish and German.
  If you have emails that can serve as additional test cases, please submit 
  them. Contributions to the parsing are welcome!

To Do
------------

* More heuristic parsing rules.
* Implement hotel bookings (https://developers.google.com/gmail/markup/reference/hotel-reservation). Booking.com and some others produce the json version.



