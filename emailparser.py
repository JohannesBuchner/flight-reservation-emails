#!/usr/bin/python
# -*- coding: utf-8 -*-
import notmuch
import BeautifulSoup
import datetime
import dateutil.parser
import dateparser
import logging
from tzlocal import get_localzone
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

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

def parse_field(v):
	# split td field into components
	h = HTMLParser()
	vs = []
	#for el in list(v) + list(v.findChildren()):
	for el in list(v.recursiveChildGenerator()) + list(v):
		if hasattr(el, 'text'):
			el = el.text
		el = h.unescape(el.strip())
		if '<' in el or '>' in el: 
			continue
		if len(el) != 0 and len(el) < 200:
			vs.append(el)
	return vs

def shorten_airport(name):
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

def parsedate(s, default=None):
	logf = logging.getLogger('emailparser.parsedate')
	logf.info('date parsing "%s"...' % s)
	try:
		if default is None:
			return dateutil.parser.parse(s)
		else:
			return dateutil.parser.parse(s, default=default)
	except ValueError as e:
		if any([n in s for n in '0123456789']) and len(s) > 4:
			if default is None:
				r = dateparser.parse(s)
			else:
				r = dateparser.parse(s, settings=dateparser.conf.Settings().replace(RELATIVE_BASE=default))
			if r is None:
				raise e
			else:
				return r
		else:
			raise e

previous_dates = {}

def parsedate_cached(s, default=None):
	s = s.replace('\n', ' ').replace('\t', ' ').replace('      ', ' ').replace('  ', ' ').replace('  ', ' ')
	if len(s) > 50:
		raise ValueError('too long for a date')
	k = (s, default)
	if k not in previous_dates:
		try:
			d = parsedate(s, default=default)
			previous_dates[k] = d
		except OverflowError as e:
			previous_dates[k] = None
		except Exception as e:
			previous_dates[k] = None
	if previous_dates[k] is None:
		raise ValueError(s)
	else:
		return previous_dates[k]

def parse_flight(columns, values, global_info):
	logf = logging.getLogger('emailparser.parse_flight')
	info = {}
	defaultdate = global_info['emailTime']
	for c, v in zip(columns, values):
		logf.debug('parsing row: column %s: "%s"' % (c, v))
		if c.lower() in ['departs', 'departure', 'departure city and time']:
			logf.debug('parsing departure: "%s"' % v)
			for vi in parse_field(v):
				logf.debug('parsing departure component: "%s"' % vi)
				# try to parse as time
				try:
					time = parsedate_cached(vi, default=defaultdate)
					logf.info('departureTime <- %s' % time)
					info['departureTime'] = time
				except ValueError:
					# could be a location
					logf.info('departure (location) <- %s' % shorten_airport(vi))
					info['departure'] = shorten_airport(vi)
		elif c.lower() in ['arrives', 'arrival', 'arrival city and time']:
			logf.debug('parsing arrival: "%s"' % v)
			for vi in parse_field(v):
				logf.debug('parsing arrival component: "%s"' % vi)
				# try to parse as time
				try:
					time = parsedate_cached(vi, default=defaultdate)
					logf.info('arrivalTime <- %s' % time)
					info['arrivalTime'] = time
				except ValueError:
					# could be a location
					logf.info('arrival (location) <- %s' % shorten_airport(vi))
					info['arrival'] = shorten_airport(vi)
		elif c.lower() in ['day, date']:
			day = HTMLParser().unescape(v.text)
			logf.debug('parsing day "%s"' % day)
			try:
				defaultdate = parsedate_cached(day)
				logf.info('defaultdate <- %s' % defaultdate)
			except ValueError as e:
				try:
					defaultdate = datetime.datetime.strptime(day, '%a, %d%b%y')
					logf.info('defaultdate <- %s' % defaultdate)
				except ValueError as e:
					logf.warn('failed to parse day "%s"' % day[:100])
					pass
		elif c.lower() in ['flight']:
			flight = v.text.strip()
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
				logf.info('flightNumber <- "%s"' % flightNumber.strip())
				info['airline'] = airline.strip()
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

def is_flight(info):
	required_keys = ['departureTime', 'departure', 'arrivalTime', 'arrival']
	if not all([k in info and info[k] != '' for k in required_keys]):
		return False
	for k in 'departure', 'arrival':
		#if info[k] in ['Manage Flight']:
		#	return False
		if any([n in info[k] for n in '0123456789']):
			return False
		if len(info[k].split()) > 5:
			return False
	return True

def parse_flight_info(columns, values):
	global_info = {}
	logf = logging.getLogger('emailparser.parse_flight_info')
	logf.debug('parsing row: %s %s' % (columns, [str(v)[:200] for v in values]))
	for c, v in zip(columns, values):
		number = v.text
		if c.lower() in ['eticket number', 'flight confirmation number', 'airline booking number', 'reservation number', 'código de reserva', 'buchungsnummer']:
			if is_airline_booking_number(number):
				global_info['ticketNumber'] = number
				logf.info('ticketNumber <- %s' % number)
	for c, v in zip(columns, values):
		if c.lower() in ['eticket number', 'booking id', 'booking number']:
			number = v.text
			if is_ticket_number(number) and 'bookingNumber' not in global_info:
				global_info['bookingNumber'] = number
				logf.info('bookingNumber <- %s' % number)
			if is_airline_booking_number(number) and 'ticketNumber' not in global_info:
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

def parse_email_message(m):
	logf = logging.getLogger('emailparser')
	reservations = []
	for mp in m.get_message_parts():
		logf.info('Subject:' + m.get_header('Subject'))
		t = mp.get_payload(decode=True)
		if mp.get_content_type() == 'text/html':
			if 'schema.org' in t: 
				logf.info('parsing with schema.org information')
				b = BeautifulSoup.BeautifulSoup(t)
				for fr in b.findAll('div', itemtype="http://schema.org/FlightReservation"):
					fl = fr.find('div', itemprop="reservationFor", itemtype="http://schema.org/Flight")
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
						boardingTime = get_value(fl, 'meta', 'boardingTime', ''),
						departureTime = get_value(fl, 'meta', 'departureTime', ''),
						departureGate = get_value(fl, 'meta', 'departureGate', ''),
						departureTerminal = get_value(fl, 'meta', 'departureTerminal', ''),
						arrival = get_code(fl, 'arrivalAirport', 'http://schema.org/Airport', ''),
						arrivalTime = get_value(fl, 'meta', 'arrivalTime', ''),
						arrivalGate = get_value(fl, 'meta', 'arrivalGate', ''),
						arrivalTerminal = get_value(fl, 'meta', 'arrivalTerminal', '')
					)
					if info['departureTime'] == '':
						logf.info('skipping: not enough schema.org information, missing departureTime')
						logf.debug(str(info))
						continue
					# add email subject and date
					info['emailTime'] = datetime.datetime.fromtimestamp(m.get_date())
					info['emailSubject'] = m.get_header('Subject')
					reservations.append(info)
			
			if len(reservations) == 0:
				b = BeautifulSoup.BeautifulSoup(t)
				logf.info('parsing html email')
				global_info = dict()
				global_info['emailTime'] = datetime.datetime.fromtimestamp(m.get_date())
				global_info['emailSubject'] = m.get_header('Subject')
				txt = b.text
				txtlower = txt.lower()
				for key in 'flight confirmation number', 'airline booking number', 'confirmation', 'digo de reserva':
					if key in txtlower:
						logf.debug('found key: "%s"' % key)
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
				for key in 'booking id', 'booking number', 'buchungsnummer':
					if key in txtlower:
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
							newheader.append(th.text.strip().strip(':'))
							override_header = True
						if len(newheader) == 0:
							for td in row.findChildren('td'):
								# has h1,h2,h3,h4 as child? probably a header
								header_names = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
								if any([c.name in header_names 
									for c in td.recursiveChildGenerator() if hasattr(c, 'name')]):
									override_header = True
								newheader.append(td.text.strip().strip(':'))
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
							info = parse_flight(header, values, global_info)
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
							info = parse_flight(testheader, values, global_info)
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
							key = cell.rstrip(':')
							for v in cells:
								if len(v.text) > 0 and len(v.text) < 100:
									logf.info('learned fact: %s = %s' % (key, v.text))
									header.append(key)
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
					
					#for k, v in items:
					#	logf.info('learned following fact: %s = %s' % (k, v))
					info.update(global_info)
					info = parse_flight(header, values, info)
					if is_flight(info):
						if info not in reservations:
							reservations.append(info)
					
					
		elif mp.get_content_type() == 'text/plain':
			logf.debug('message: text/plain: %s' % t)
		else:
			logf.debug('message: other content type: %s' % mp.get_content_type())
	return reservations


























































































