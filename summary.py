import notmuch
import BeautifulSoup
import datetime
import dateutil.parser
from tzlocal import get_localzone
#import xml
#import xml.etree.ElementTree

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

db = notmuch.Database()
query = db.create_query('schema.org/FlightReservation')

all_reservations = []

for m in query.search_messages():
	for mp in m.get_message_parts():
		if mp.get_content_type() != 'text/html':
			continue
		t = mp.get_payload(decode=True)
		if 'schema.org' not in t: 
			continue
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
				print 'skipping', info
				print
				continue
			# add email subject and date
			info['emailTime'] = datetime.datetime.fromtimestamp(m.get_date())
			info['emailSubject'] = m.get_header('Subject')
			all_reservations.append(info)

def dateConverter(dateText):
	day = dateutil.parser.parse(dateText)
	if day.tzinfo is not None:
		return day
	print 'Warning: Using local time zone to order %s' % dateText
	local_tz = get_localzone()
	return day.replace(tzinfo=local_tz)
	#pytz.utc.localize(day, local)

# sort by departure time
all_reservations.sort(key=lambda info: dateConverter(info['departureTime']))

previous = None

for info in all_reservations:
	prepend(info, 'departureGate', 'Gate ')
	prepend(info, 'arrivalGate', 'Gate ')
	prepend(info, 'arrivalTerminal', 'Terminal ')
	prepend(info, 'departureTerminal', 'Terminal ')
	prepend(info, 'boardingTime', 'Boarding ')
	prepend(info, 'ticketNumber', 'Ticket#')
	prepend(info, 'operator', ' operated by ')
	
	flightday = dateutil.parser.parse(info['departureTime']).date()
	if previous is not None and (flightday - previous).days > 14:
		print '=============', (flightday - previous).days, 'days later'
	previous = flightday
	info['flightday'] = flightday.isoformat()
	
	info['emailday'] = info['emailTime'].date().isoformat()
	print """
%(flightday)s Flight %(departure)s --> %(arrival)s

Departing %(departureTime)s %(boardingTime)s
from %(departure)s %(departureTerminal)s %(departureGate)s
arriving %(departureTime)s
To   %(arrival)s %(arrivalTerminal)s %(arrivalGate)s
Flight number %(flightNumber)s with %(airline)s%(operator)s
%(ticketNumber)s %(ticketText)s %(ticketDownload)s %(ticketPrint)s

Email %(emailday)s "%(emailSubject)s"


""" % info
			
