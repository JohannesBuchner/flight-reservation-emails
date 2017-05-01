import notmuch
import BeautifulSoup
import datetime
import dateutil.parser
import emailparser
from tzlocal import get_localzone

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
	all_reservations += emailparser.parse_email_message(m)

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
arriving %(arrivalTime)s
To   %(arrival)s %(arrivalTerminal)s %(arrivalGate)s
Flight number %(flightNumber)s with %(airline)s%(operator)s
%(ticketNumber)s %(ticketText)s %(ticketDownload)s %(ticketPrint)s

Email %(emailday)s "%(emailSubject)s"


""" % info
			
