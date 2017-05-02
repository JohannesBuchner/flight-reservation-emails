#!/usr/bin/python
# -*- coding: utf-8 -*-
import notmuch
import BeautifulSoup
import datetime
import dateutil.parser
import emailparser
import logging
from tzlocal import get_localzone
import sys
import os

logging.basicConfig(filename='emailparser.log',level=logging.DEBUG)
logFormatter = logging.Formatter("[%(name)s %(levelname)s]: %(message)s")
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
consoleHandler.setLevel(logging.WARN)
logging.getLogger().addHandler(consoleHandler)

if len(sys.argv) < 3:
	sys.stderr.write("""SYNOPSIS: %(exe)s <database> <query>

database: absolute path to notmuch database
query: query to use. Has to be in quotes.

Example usage:
%(exe)s $PWD/test/ 'schema.org/FlightReservation OR ticket OR flight OR flug OR viaje OR booking OR confirmation OR confirmacion'

To speed up date parsing, you can specify the languages to consider with the 
LANGUAGES environment variable:
LANGUAGES="en de es" <cmd>

Author: Johannes Buchner (c) 2017
""" % dict(exe=sys.argv[0]))
	sys.exit(1)
db = notmuch.Database(sys.argv[1])
query = sys.argv[2]
query = db.create_query(query)
#'schema.org/FlightReservation OR ticket OR flight OR flug OR viaje OR booking OR confirmation OR confirmacion')
languages = os.environ.get('LANGUAGES', None)
if languages is not None:
	languages = languages.split()
#query = db.create_query('schema.org/FlightReservation OR eticket OR flight')
#languages = ['en']
#query = db.create_query('schema.org/FlightReservation')

all_reservations = emailparser.parse_multiple_email_messages(query.search_messages(), languages=languages)
#all_reservations = []
#messages = list(query.search_messages())
#for i, m in enumerate(messages[::-1]):
#	print('handling %d/%d: "%s" from %s' % (i, len(messages), m.get_header('Subject'), 
#		datetime.datetime.fromtimestamp(m.get_date()).strftime('%Y-%m-%d')))
#	reservations = emailparser.parse_email_message(m, languages = languages)
#	print('got %d reservations' % len(all_reservations))
#	all_reservations += reservations
print('got %d reservations' % len(all_reservations))

def prepend(info, k, prefix):
	if info[k] and info[k] != '':
		info[k] = prefix + info[k]

def dateConverter(day):
	#day = dateutil.parser.parse(dateText)
	if day.tzinfo is not None:
		return day
	print 'Warning: Using local time zone to order %s' % day
	local_tz = get_localzone()
	return day.replace(tzinfo=local_tz)

# sort by departure time
all_reservations.sort(key=lambda info: dateConverter(info['departureTime']))

previous = None
fout = open('summary.html', 'w')
fout.write("""<!doctype html><html lang="en">
<head>
<meta charset=utf-8>
<title>Flight summary</title>
<link rel="stylesheet" type="text/css" href="theme.css">
</head>
<body>
<h1>Flights</h1>
<table>
""")

file_id = 1
for info in all_reservations:
	prepend(info, 'departureGate', 'Gate ')
	prepend(info, 'arrivalGate', 'Gate ')
	prepend(info, 'arrivalTerminal', 'Terminal ')
	prepend(info, 'departureTerminal', 'Terminal ')
	prepend(info, 'ticketNumber', 'Ticket#')
	prepend(info, 'operator', ' operated by ')
	flightday = info['departureTime'].date()
	prepend(info, 'boardingTimestr', 'Boarding ')
	
	filenames = []
	msg_id = info['emailId']
	for m in db.create_query('id:%s' % msg_id).search_messages():
		for mp in m.get_message_parts():
			if mp.get_content_type() == 'application/pdf' or (mp.get_content_type() == 'application/octet-stream' and mp.get_filename().lower().endswith('.pdf')):
				filename = 'file_id%d.pdf' % file_id
				with open(filename, 'w') as f:
					f.write(mp.get_payload(decode=True))
				filenames.append((mp.get_filename(), filename))
				file_id += 1
	info['pdffiles'] = ' | '.join(['<a class="pdffile" href="%s">%s</a>' % (filename, origfilename) for (origfilename, filename) in filenames])
	
	if previous is not None and (flightday - previous).days > 14:
		delta = (flightday - previous).days
		print '=============', delta, 'days later'
		fout.write("""
<tr>
<td colspan="3" class="gaplater">%d days later
</tr>
		""" % delta)
	else:
		fout.write("""
<tr>
<td colspan="3" class="gap">&nbsp;
</tr>
		""")
	previous = flightday
	info['departureDay'] = flightday.strftime('%Y-%m-%d')
	info['departureJustTime'] = info['departureTime'].strftime('%H:%M')
	info['emailday'] = info['emailTime'].date().strftime('%Y-%m-%d')
	
	print """
%(departureDay)s Flight %(departure)s --> %(arrival)s

Departing %(departureTimestr)s %(boardingTime)s
from %(departure)s %(departureTerminal)s %(departureGate)s
arriving %(arrivalTimestr)s
To   %(arrival)s %(arrivalTerminal)s %(arrivalGate)s
Flight number %(flightNumber)s with %(airline)s%(operator)s
%(ticketNumber)s %(ticketText)s %(ticketDownload)s %(ticketPrint)s

Email %(emailday)s "%(emailSubject)s"


""" % info
	fout.write(("""
<tr><td class="left">
<h5>From</h5>
%(departure)s
%(departureTerminal)s 
%(departureGate)s
<td class="middle" rowspan="2" >&#9992;
<td class="right">
<h5>Destination</h5>
%(arrival)s
%(arrivalTerminal)s 
%(arrivalGate)s
</tr>

<tr>
<td class="left">
<h5>Depart</h5>
%(departureJustTime)s 
<td class="right">
<h5>Date</h5>
%(departureDay)s
</tr>

<tr>
<td colspan="3" class="details">
<h5>Arriving</h5>
%(arrivalTimestr)s
<h5>Flight number</h5>
Flight number %(flightNumber)s with %(airline)s%(operator)s
<h5>Ticket</h5>
%(ticketNumber)s %(ticketText)s %(ticketDownload)s %(ticketPrint)s
<div>%(boardingTime)s</div>
<div>%(pdffiles)s</div>
</td>
</tr>
<tr>
<td colspan="3" class="email">
<h5>Email</h5>
%(emailday)s "%(emailSubject)s"
</td>
	""" % info).encode('utf-8'))
		
