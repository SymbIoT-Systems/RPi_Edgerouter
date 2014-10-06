from pyudev import Context, Monitor, MonitorObserver, Device
from time import sleep
import sys
import subprocess 
import os

from requests import Session
session = Session()

port1 = "8080"

#device1 = Device.from_device_file(context,'/dev/ttyUSB1')

def print_device_event(device):
	print('background event {0.action}: {0.device_path}'.format(device))
	if device.action=='add':
		print "\nDevice Added..."
		proc = subprocess.Popen(['motelist'],stdout=subprocess.PIPE,shell=True)
		(out,err) = proc.communicate()
		dev = out.find("/dev/ttyUSB")
		#print dev
		out = out[dev:dev+12]
		print "\n"+out
		usb_status_file=open("usb_status","w+")
		usb_status_file.write(out)
		usb_status_file.close()
		#os.environ["motepath"]=out
		# session.head('http://localhost:5000/automount')

		# response = session.post(
		# url='http://localhost:'+port1+'/automount',
		# data={
		# 'port':out,
		# 'status':'Added'
		# }
		# )



	elif device.action == 'remove':
		print "\nDevice Removed\n"
		usb_status_file=open("usb_status","w+")
		usb_status_file.write("")
		usb_status_file.close()
		# session.head('http://localhost:5000/automount')

		# response = session.post(
		# url='http://localhost:'+port1+'/automount',
		# data={
		# 'port':'null',
		# 'status':'Removed'
		# }
		# )

def initialize():
	context = Context()
	monitor = Monitor.from_netlink(context)
	monitor.filter_by(subsystem='tty')
	observer = MonitorObserver(monitor, callback=print_device_event, name = 'monitor-observer')
	observer.daemon
	observer.start()

initialize()



while True:
	a = 1
# 	try:
# 		print "."
# 		sleep(2)

# 	except KeyboardInterrupt:
# 		print "\n\nExiting gracefully"
# 		for i in range(1,19):
# 			sys.stdout.write('.')

# 		print "\n"
# 		sys.exit(0)


if __name__ == "__main__":
	print "\nModule is being run directly\n"

# print device1.subsystem 
# print device1.driver
# print device1.device_type
# print device1.device_node
# print device1.sys_name
# print_device_event(device1)
# if device1.action == 'add':
# print "\nDevice added"
# print device1.tags

#Ensure that the initial base path while launching the server is correct
proc = subprocess.Popen(['motelist'],stdout=subprocess.PIPE,shell=True)
(out,err) = proc.communicate()
dev = out.find("/dev/ttyUSB")
#print dev
out = out[dev:dev+12]
# print "\n"+out
usb_status_file=open("usb_status","w+")
usb_status_file.write(out)
usb_status_file.close()
