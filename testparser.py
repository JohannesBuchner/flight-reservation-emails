import notmuch
import os
import emailparser
import sys
import logging

dbpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test-private')
dbpath = sys.argv[1]
db = notmuch.Database(dbpath)
query = db.create_query(sys.argv[2])

if __name__ == '__main__':
	emailparser.default_logging()
	logging.getLogger('emailparser').setLevel(logging.DEBUG)
	for m in query.search_messages():
		r = emailparser.parse_email_message(m)
		f = os.path.basename(m.get_filename())
		txt = ""
		for info in r:
			txt += """
Flight %(departure)s --> %(arrival)s

Departing %(departureTime)s %(boardingTime)s
from %(departure)s %(departureTerminal)s %(departureGate)s
arriving %(arrivalTime)s
To   %(arrival)s %(arrivalTerminal)s %(arrivalGate)s
Flight number %(flightNumber)s with %(airline)s%(operator)s
%(ticketNumber)s %(ticketText)s %(ticketDownload)s %(ticketPrint)s


""" % info
		if txt != "":
			with open(os.path.join(dbpath, 'parsed', f), 'w') as fout:
				fout.write(txt.encode('utf8'))
		ftest = os.path.join(dbpath, 'expected', f)
		if os.path.exists(ftest):
			test = open(ftest).read()
			if txt == "":
				print "no parsing output for %s" % f
				print "expected:", ftest
				print test
				break
			elif txt != test:
				print "parsing difference for %s" % f
				print "expected:", ftest
				print test
				print "actual:", os.path.join(dbpath, 'parsed', f)
				print txt
				break
			else:
				print "result for %s" % f
				print txt
				print 'ok'
		else:
			if txt != "":
				print "unexpected parsing output for %s" % f
				print "actual:", os.path.join(dbpath, 'parsed', f)
				print txt
				break
			else:
				print "result for %s" % f
				print txt
				print 'ok'

		
	


