#!/usr/bin/python
# -*- coding: utf-8 -*-
import notmuch
import BeautifulSoup
import datetime
import dateutil.parser
import dateparser

import logging
from tzlocal import get_localzone

# this makes everything utf8
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

# this disables relative dates
import dateparser.date
dateparser.date._DateLanguageParser._try_freshness_parser = lambda self: False

def get_value(reservation, element, itemprop, default):
	node = reservation.find(element, itemprop=itemprop)
	if node is None:
		return default
	else:
		attrs = dict(node.attrs)
		if element == 'link':
			return attrs.get('href', default)
		elif element == 'meta':
			return attrs.get('content', default)
def get_name(parent, itemprop, itemtype, default, childitemprop='name'):
	node = parent.find('div', itemprop=itemprop, itemtype=itemtype)
	if node is None: 
		return default
	return get_value(node, 'meta', childitemprop, default)

def get_code(parent, itemprop, itemtype, default):
	return get_name(parent, itemprop, itemtype, default, childitemprop='iataCode')

def prepend(info, k, prefix):
	if info[k] and info[k] != '':
		info[k] = prefix + info[k]

from six.moves.html_parser import HTMLParser
h = HTMLParser()

def nicefy_htmltext(txt):
	el = h.unescape(txt.strip())
	el = el.strip('.').replace('\n', ' ').replace('\t', ' ').replace('    ', ' ').replace('  ', ' ').replace('  ', ' ').strip()
	return el

def parse_field(v):
	# split td field into components
	vs = []
	#for el in list(v) + list(v.findChildren()):
	for el in list(v.recursiveChildGenerator()) + list(v):
		if hasattr(el, 'text'):
			el = el.text
		el = nicefy_htmltext(el)
		if '<' in el or '>' in el: 
			continue
		if len(el) != 0 and len(el) < 200:
			vs.append(el)
	return vs

def shorten_airport(name):
	name = nicefy_htmltext(name).strip('#')
	if len(name) < 8:
		return name
	if '(' not in name:
		return name
	part = name.split('(')[1]
	if ')' not in part:
		return name
	part = part.split(')')[0]
	if len(part) != 3:
		return name
	return part

def parsedate_simple(s):
	logf = logging.getLogger('emailparser.parsedate')
	logf.info('simple date parsing "%s"...' % s)
	if s == '':
		return ''
	return dateutil.parser.parse(s)
def parsedate(s, default, languages=None):
	logf = logging.getLogger('emailparser.parsedate')
	logf.info('date parsing "%s"...' % s)
	try:
		return dateutil.parser.parse(s, default=default.replace(second=0, minute=0, hour=0))
	except ValueError as e:
		r = dateparser.parse(s, languages=languages, settings=
			dateparser.conf.Settings().replace(
			RELATIVE_BASE=default.replace(second=0, minute=0, hour=0)))
		if r is None:
			raise e
		else:
			return r

previous_dates = {}

def parsedate_cached(s, default, languages=None):
	logf = logging.getLogger('emailparser.parsedate_cached')
	s = s.replace('\n', ' ').replace('\t', ' ').replace('      ', ' ').replace('  ', ' ').replace('  ', ' ')
	if len(s) > 50:
		raise ValueError('too long for a date')
	if len(s) < 4:
		raise ValueError('too short for a date')
	if not any([n in s for n in '0123456789']):
		raise ValueError('numbers expected in a date')
	k = (s, default)
	if k not in previous_dates:
		try:
			d = parsedate(s, default=default, languages=languages)
			if d.year < 1980 or d.year > datetime.datetime.now().year + 2:
				logf.warn('problem parsing "%s": outside reasonable date range' % (s))
				d = None
			previous_dates[k] = d
		except OverflowError as e:
			logf.warn('problem parsing "%s": %s' % (s, e))
			previous_dates[k] = None
		except Exception as e:
			logf.warn('problem parsing "%s": %s' % (s, e))
			previous_dates[k] = None
	if previous_dates[k] is None:
		raise ValueError(s)
	else:
		return previous_dates[k]

def parse_flight(columns, values, global_info, languages=None):
	logf = logging.getLogger('emailparser.parse_flight')
	info = {}
	defaultdate = global_info['emailTime']
	logf.info('defaultdate(email) <- %s' % defaultdate)
	for c, v in zip(columns, values):
		logf.debug('parsing row: column %s: "%s"' % (c, v))
		if c.lower() in ['departs', 'departure', 'departure city and time', 'from', 'salida']:
			logf.debug('parsing departure: "%s"' % v)
			for vi in parse_field(v):
				logf.debug('parsing departure component: "%s"' % vi)
				# try to parse as time
				try:
					time = parsedate_cached(vi, default=defaultdate, languages=languages)
					if time.hour != 0 or time.minute != 0:
						logf.info('departureTime <- %s' % time)
						info['departureTime'] = time
				except ValueError as e:
					# could be a location
					v = shorten_airport(vi)
					if is_airport(v):
						logf.info('departure (location) <- %s (date: %s)' % (v, e))
						info['departure'] = v
		elif c.lower() in ['arrives', 'arrival', 'arrival city and time', 'to', 'llegada']:
			logf.debug('parsing arrival: "%s"' % v)
			for vi in parse_field(v):
				logf.debug('parsing arrival component: "%s"' % vi)
				# try to parse as time
				try:
					time = parsedate_cached(vi, default=defaultdate, languages=languages)
					if time.hour != 0 or time.minute != 0:
						logf.info('arrivalTime <- %s' % time)
						info['arrivalTime'] = time
				except ValueError as e:
					# could be a location
					v = shorten_airport(vi)
					if is_airport(v):
						logf.info('arrival (location) <- %s (date: %s)' % (v, e))
						info['arrival'] = v
		elif c.lower() in ['day, date']:
			day = nicefy_htmltext(v.text)
			if day != '':
				logf.debug('parsing day "%s"' % day)
				try:
					defaultdate = parsedate_cached(day, default=defaultdate, languages=languages)
					logf.info('defaultdate <- %s' % defaultdate)
				except ValueError as e:
					try:
						defaultdate = datetime.datetime.strptime(day, '%a, %d%b%y')
						logf.info('defaultdate <- %s' % defaultdate)
					except ValueError as e:
						logf.debug('failed to parse as day "%s" (%s)' % (day[:100], e))
						pass
		elif c.lower() in ['flight', 'flights', 'vuelo \xe2\x84\x96']:
			flight = nicefy_htmltext(v.text.strip())
			#if flight.startswith('Seat'):
			#	logf.info('airplaneSeat <- "%s"' % flight)
			#	info['airplaneSeat'] = flight
			#else:
			logf.info('flightNumber <- "%s"' % flight)
			info['flightNumber'] = flight
			for k in 'operado por', 'operated by':
				if k in flight.lower():
					i = flight.lower().index(k)
					flightNumber = flight[:i].strip()
					operator = flight[i+len(k):].strip()
					logf.info('flightNumber <- "%s"' % flightNumber)
					info['flightNumber'] = flightNumber
					logf.info('operator <- "%s"' % operator)
					info['operator'] = operator
		elif c.lower() in ['airline']:
			airline = v.text.strip()
			try:
				airline, flightNumber = airline.split('#')
				logf.info('airline <- "%s"' % airline.strip())
				info['airline'] = airline.strip()
				logf.info('flightNumber <- "%s"' % flightNumber.strip())
				info['flightNumber'] = flightNumber.strip()
			except:
				logf.info('airline <- "%s"' % airline.strip())
				info['airline'] = airline.strip()
		else:
			logf.debug('unhandled column "%s" with content: "%s"' % (c, v.text))
		
	if len(info) > 0:
		logf.info('learned flight info: %s' % info)
	
	info.update(global_info)
	all_keys = ['reservationNumber', 'checkinUrl', 'ticketNumber', 'ticketDownload',
	'ticketPrint', 'ticketText', 'airplaneSeat', 'boardingGroup', 'flightNumber',
	'airline', 'operator', 'departure', 'boardingTime', 'departureTime', 'departureGate',
	'departureTerminal', 'arrival', 'arrivalTime', 'arrivalGate', 'arrivalTerminal']
	for k in all_keys:
		if k not in info:
			info[k] = ''
	return info

def is_airport(v):
	if len(v) < 3:
		return False
	if any([n in v for n in '0123456789']):
		return False
	if len(v.split()) > 5:
		return False
	if v.startswith('('):
		return False
	invalid_symbols = ':@#'
	if any(s in v for s in invalid_symbols) or v.startswith('/'):
		return False
	return True

stopwords = ['estimated', 'total', 
	'cabin: ', 'take this survey', 'callout panel', 'award miles', 
	'passengers', 'right column',
	'foreign affairs', 'security', 'book now', 'see deal', 
	'enjoy', 'experience', 'entertainment', 'footer', 'awards', '®',
	'twitter', ' your ', 'requires', 'approval', 'www',
	'@', '#',
] + ['january', 'february', 'march', 'april', 'july', 'august', 'september', 'october', 'november', 'december']

def is_flight(info):
	required_keys = ['departureTime', 'departure', 'arrivalTime', 'arrival']
	logf = logging.getLogger('emailparser.is_flight')
	logf.info('checking if is a flight: %s' % info)
	if not all([k in info and info[k] != '' for k in required_keys]):
		return False
	for k in 'departure', 'arrival':
		v = info[k].lower()
		if v in ['manage flight', 'airport Lounges', 'total estimated cost', 'here']:
			return False
		if any([stopword in v for stopword in stopwords]):
			return False
	#	if not is_airport(info[k]):
	#		return False
	logf.info('yes, is a flight: %s' % info)
	return True

def replace_booking_number(info, key, number):
	if key not in info or info[key] == number:
		info[key] = number
		return
	info[key] = info[key] + ', ' + number

def parse_flight_info(columns, values):
	global_info = {}
	logf = logging.getLogger('emailparser.parse_flight_info')
	logf.debug('parsing row: %s %s' % (columns, [str(v)[:200] for v in values]))
	for c, v in zip(columns, values):
		number = v.text
		if c.lower() in ['eticket number', 'flight confirmation number', 'airline booking number', 'reservation number', 'código de reserva', 'código de reservación', 'buchungsnummer', 'pnr #']:
			logf.info('found ticketNumber key "%s" -> %s' % (c, number))
			if is_airline_booking_number(number):
				replace_booking_number(global_info, 'ticketNumber', number)
				logf.info('ticketNumber <- %s' % number)
	for c, v in zip(columns, values):
		if c.lower() in ['eticket number', 'booking id', 'booking number', 'e-ticket #']:
			number = v.text
			logf.info('found booking number key "%s" -> %s' % (c, number))
			if is_ticket_number(number) and 'bookingNumber' not in global_info:
				replace_booking_number(global_info, 'bookingNumber', number)
				global_info['bookingNumber'] = number
				logf.info('bookingNumber <- %s' % number)
			if is_airline_booking_number(number) and 'ticketNumber' not in global_info:
				replace_booking_number(global_info, 'ticketNumber', number)
				global_info['ticketNumber'] = number
				logf.info('ticketNumber <- %s' % number)
		if c.lower() in ['seats']:
			global_info['airplaneSeat'] = v.text
	if len(global_info) > 0:
		logf.info('learned new global info: %s' % global_info)
	return global_info
				
def is_airline_booking_number(number):
	if len(number) != 6:
		return False
	for d in number:
		if d not in '0123456789QWERTZUIOPASDFGHJKLYXCVBNM':
			return False
	return True
def is_ticket_number(number):
	if len(number) < 6 or len(number) > 20:
		return False
	for d in number:
		if d not in '0123456789QWERTZUIOPASDFGHJKLYXCVBNM':
			return False
	return True

def default_logging():
	logging.basicConfig(filename='emailparser.log',level=logging.DEBUG)
	logFormatter = logging.Formatter("[%(name)s %(levelname)s]: %(message)s")
	consoleHandler = logging.StreamHandler()
	consoleHandler.setFormatter(logFormatter)
	consoleHandler.setLevel(logging.INFO)
	logging.getLogger().addHandler(consoleHandler)

def parse_email_html_message(t, languages = None, email_info={}):
	logf = logging.getLogger('emailparser.html')
	reservations = []
	if 'schema.org' in t: 
		logf.info('parsing with schema.org information')
		b = BeautifulSoup.BeautifulSoup(t)
		for fr in b.findAll('div', itemtype="http://schema.org/FlightReservation"):
			fl = fr.find(itemprop="reservationFor", itemtype="http://schema.org/Flight")
			if fl is None:
				logf.debug('no reservationFor element in %s' % fr)
				continue
			info = dict(
				reservationNumber = get_value(fr, 'meta', "reservationNumber", ''),
				checkinUrl = get_value(fr, 'link', "checkinUrl", ''),
				ticketNumber = get_value(fr, 'meta', "ticketNumber", ''),
				ticketDownload = get_value(fr, 'link', "ticketDownloadUrl", ''),
				ticketPrint = get_value(fr, 'link', "ticketPrintUrl", ''),
				ticketText = get_value(fr, 'meta', "additionalTicketText", ''),
				airplaneSeat = get_value(fr, 'meta', "airplaneSeat", ''),
				boardingGroup = get_value(fr, 'meta', "boardingGroup", ''),
				flightNumber = get_value(fl, 'meta', 'flightNumber', ''),
				airline = get_name(fl, 'airline', 'http://schema.org/Airline', ''),
				operator = get_name(fl, 'operatedBy', 'http://schema.org/Airline', ''),
				departure = get_code(fl, 'departureAirport', 'http://schema.org/Airport', ''),
				boardingTime = parsedate_simple(get_value(fl, 'meta', 'boardingTime', '')),
				departureTime = parsedate_simple(get_value(fl, 'meta', 'departureTime', '')),
				departureGate = get_value(fl, 'meta', 'departureGate', ''),
				departureTerminal = get_value(fl, 'meta', 'departureTerminal', ''),
				arrival = get_code(fl, 'arrivalAirport', 'http://schema.org/Airport', ''),
				arrivalTime = parsedate_simple(get_value(fl, 'meta', 'arrivalTime', '')),
				arrivalGate = get_value(fl, 'meta', 'arrivalGate', ''),
				arrivalTerminal = get_value(fl, 'meta', 'arrivalTerminal', '')
			)
			if info['departureTime'] == '':
				logf.warn('skipping: not enough schema.org information, missing departureTime')
				logf.debug(str(info))
				continue
			# add email subject and date
			info.update(email_info)
			reservations.append(info)
	
	if len(reservations) == 0:
		b = BeautifulSoup.BeautifulSoup(t)
		logf.info('parsing html email')
		global_info = dict(email_info)
		txt = b.text
		txtlower = txt.lower()
		
		for key, languages1 in ('flight confirmation number', ['en']), ('airline booking number', ['en']), ('confirmation', ['en']), ('digo de reserva', ['es']):
			if key in txtlower:
				logf.debug('found key: "%s"' % key)
				languages = languages1
				try:
					i = txtlower.index(key) + len(key)
					for number in txt[i:i+1000].split(':')[1:4:2]:
						logf.debug('parsing flight confirmation number: %s: %s' % (key, number))
						number = number.strip()[:6]
						if is_airline_booking_number(number):
							global_info['ticketNumber'] = number
							logf.info('ticketNumber <- "%s"' % number)
				except Exception as e:
					logf.warn('parsing %s failed: %s' % (key, e))
		for key, languages1 in ('booking id', ['en']), ('booking number', ['en']), ('buchungsnummer', ['de']):
			if key in txtlower:
				languages = languages1
				logf.debug('found key: "%s"' % key)
				try:
					i = txtlower.index(key) + len(key)
					number = txt[i:i+1000].split(':')[1]
					logf.debug('parsing booking number: %s: %s' % (key, number))
					for j in range(len(number)):
						if number[j] not in '0123456789QWERTZUIOPASDFGHJKLYXCVBNM':
							break
					if j == 0: 
						continue
					number = number[:j]
					if is_ticket_number(number) and 'bookingNumber' not in global_info:
						global_info['bookingNumber'] = number
						logf.info('bookingNumber <- "%s"' % number)
					if is_airline_booking_number(number) and 'ticketNumber' not in global_info:
						global_info['ticketNumber'] = number
						logf.info('ticketNumber <- "%s"' % number)
				except Exception as e:
					logf.warn('parsing %s failed: %s' % (key, e))
		if languages is None:
			if any([v in txtlower for v in 'confirmacion', 'itinerario', 'viaje']):
				languages = ['es']
				logf.info('language detected: es')
			if any([v in txtlower for v in 'buchung', 'rechnung', 'flugzeug', 'stunden', 'danke', 'vielen dank']):
				languages = ['de']
				logf.info('language detected: de')
			if any([v in txtlower for v in 'passenger information', 'traveler information', 'departs', 'arrives', 'reconfirm', 'payment', 'itinerary', 'receipt', 'confirmation', 'thank you']):
				logf.info('language detected: en')
				languages = ['en']
		if languages is None:
			logf.warn('language unsure')
		for table in b.findAll('table'):
			# make dictionaries for vertical tables
			header = []
			#logf.debug('')
			#logf.debug('')
			#logf.debug('found table: %s' % (table))
			#logf.debug('')
			#logf.debug('')
			rows = table.findChildren('tr')
			override_header = True
			for row in rows:
				# build header column
				newheader = []
				for th in row.findChildren('th'):
					newheader.append(nicefy_htmltext(th.text.strip().strip(':')))
					override_header = True
				if len(newheader) == 0:
					for td in row.findChildren('td'):
						# has h1,h2,h3,h4 as child? probably a header
						header_names = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
						if any([c.name in header_names 
							for c in td.recursiveChildGenerator() if hasattr(c, 'name')]):
							override_header = True
						newheader.append(nicefy_htmltext(td.text.strip().strip(':')))
				if len(newheader) == 1 or all([len(h) > 100 for h in newheader]):
					newheader = []
				if override_header:
					logf.debug('table header: %s' % newheader)
				if override_header and len(newheader) > 0 and any([len(h) > 0 for h in newheader]):
					header = newheader
					logf.debug('new header assigned')
					override_header = False
					continue
				if len(header) != 0:
					override_header = False
				# deal with content
				values = []
				for td in row.findChildren('td'):
					values.append(td)
				
				if len(header) > 0:
					info = parse_flight(header, values, global_info, languages=languages)
					if is_flight(info):
						if info not in reservations:
							reservations.append(info)
					else:
						global_info.update(parse_flight_info(header, values))
				else:
					logf.info('skipping row, no header found so far, in "%s"' % row)
					continue
		if len(reservations) == 0:
			for table in b.findAll('table'):
				# make dictionaries for vertical tables
				rows = table.findChildren('tr')
				for row in rows:
					values = row.findChildren('td')
					# could be this information:
					logf.info('no header, trying something with "%s"' % values)
					testheader = ['Day, date', 'Departure', 'Arrival', 'Flight']
					info = parse_flight(testheader, values, global_info, languages=languages)
					if is_flight(info):
						if info not in reservations:
							reservations.append(info)
		if len(reservations) == 0:
			# try making bullet points out of all horizontal tables
			header = []
			values = []
			logf.info('horizontal parsing')
			info = {}
			for row in b.findAll('tr'):
				cells = row.findChildren('td')
				if len(cells) == 0:
					continue
				cellheaders = row.findChildren('th')
				logf.debug('learning from row: [%s] %s' % (
					[c.text[:100] for c in cellheaders],
					[c.text[:100] for c in cells]))
				if len(cellheaders) == 0:
					cell = cells[0].text.strip()
					cells = cells[1:]
				else:
					cell = cellheaders[0].text.strip()
				if len(cells) > 0 and cell.endswith(':'):
					key = cell.rstrip(':').strip()
					for v in cells:
						if len(v.text) > 0 and len(v.text) < 100:
							logf.info('learned fact: %s = %s' % (key, v.text))
							header.append(nicefy_htmltext(key))
							values.append(v)
				elif ' to ' in cell and len(cell) < 150 and '.' not in cell and ' you ' not in cell  and ' do ' not in cell:
					parts = cell.split(' to ')
					if len(parts) == 2:
						logf.info('learned from-to: %s' % parts)
						departure, arrival = parts
						info['departure'] = departure
						info['arrival'] = arrival
					else:
						logf.info('strange from-to: %s' % cell)
				elif ':' in cell and len(cell) < 150 and '.' not in cell and ' you ' not in cell  and ' do ' not in cell:
					parts = cell.split(':')
					if len(parts) == 2:
						key, v = parts
						key, v = key.strip(), v.strip()
						v = BeautifulSoup.BeautifulSoup(v)
						logf.info('learned fact: %s = %s' % (key, v))
						header.append(nicefy_htmltext(key))
						values.append(v)
					else:
						logf.info('strange fact: %s' % cell)
					
					
			#for k, v in items:
			#	logf.info('learned following fact: %s = %s' % (k, v))
			logf.info('finding global info %s -> %s' % (header, [v.text for v in values]))
			global_info.update(parse_flight_info(header, values))
			info.update(global_info)
			logf.info('finding flight info %s -> %s' % (header, [v.text for v in values]))
			info = parse_flight(header, values, info, languages=languages)
			if is_flight(info):
				if info not in reservations:
					reservations.append(info)
	for info in reservations:
		for datekey in ['departureTime', 'arrivalTime', 'boardingTime']:
			if info[datekey] != '':
				info[datekey + 'str'] = info[datekey].strftime('%Y-%m-%d %H:%M')
			else:
				info[datekey + 'str'] = ''
	return reservations

def parse_email_message(m, languages = None):
	logf = logging.getLogger('emailparser')
	email_info = {}
	email_info['emailTime'] = datetime.datetime.fromtimestamp(m.get_date())
	email_info['emailSubject'] = m.get_header('Subject')
	reservations = []
	for mp in m.get_message_parts():
		logf.info('Subject:' + m.get_header('Subject'))
		t = mp.get_payload(decode=True)
		if mp.get_content_type() == 'text/html':
			reservations += parse_email_html_message(t, languages=languages, email_info=email_info)
		elif mp.get_content_type() == 'text/plain':
			logf.debug('message: text/plain: %s' % t)
		else:
			logf.debug('message: other content type: "%s"' % mp.get_content_type())
	return reservations

def parse_multiple_email_messages(query_results, languages=None):
	all_reservations = []
	import joblib
	call = joblib.delayed(parse_email_html_message)
	calls = []
	messages = list(query_results)
	logf = logging.getLogger('emailparser')
	for i, m in enumerate(messages):
		logf.info('handling %d/%d: "%s" from %s' % (i, len(messages), m.get_header('Subject'), 
			datetime.datetime.fromtimestamp(m.get_date()).strftime('%Y-%m-%d')))
		email_info = {}
		email_info['emailTime'] = datetime.datetime.fromtimestamp(m.get_date())
		email_info['emailSubject'] = m.get_header('Subject')
		email_info['emailId'] = m.get_message_id()
		for mp in m.get_message_parts():
			t = mp.get_payload(decode=True)
			if mp.get_content_type() == 'text/html':
				calls.append(call(t, languages=languages, email_info=email_info))
			elif mp.get_content_type() == 'text/plain':
				logf.debug('message: text/plain: %s' % t)
			else:
				logf.debug('message: other content type: %s' % mp.get_content_type())
	
	logf.info('processing in parallel...')
	for reservations_part in joblib.Parallel(n_jobs=-1)(calls):
		all_reservations += reservations_part
		logf.info('%d reservations' % len(all_reservations))
	return all_reservations


