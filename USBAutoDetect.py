from pyudev import Context, Monitor, MonitorObserver, Device
from time import sleep
import sys
import subprocess 
import os

from requests import Session
session = Session()

port1 = "8088"

#device1 = Device.from_device_file(context,'/dev/ttyUSB1')

def print_device_event(device):
	print('background event {0.action}: {0.device_path}'.format(device))
	if device.action=='add':

		print "\nDevice Added..."
		proc = subprocess.Popen(['motelist|grep "/dev/ttyUSB"'],stdout=subprocess.PIPE,shell=True)
		(out,err) = proc.communicate()
		# dev = out.find("/dev/ttyUSB")

		dev = out.split("\n")
		# print dev

		base_index = dev[0].find("/dev/ttyUSB")
		base_add = dev[0][base_index:base_index+12]
		print base_add

		sniff_index = dev[1].find("/dev/ttyUSB")
		sniff_add = dev[1][sniff_index:sniff_index+12]
		print sniff_add

		proc = subprocess.Popen(['tos-deluge serial@'+base_add+":115200 -id"],stdout=subprocess.PIPE,shell=True)
		(out,err) = proc.communicate()

		if "ERROR" in out:
			#This is not the basestation, swap the addresses
			(base_add,sniff_add) = (sniff_add,base_add) 

		usb_status_file=open("usb_status","w+")
		usb_status_file.write(base_add+"\n")
		usb_status_file.write(sniff_add)
		usb_status_file.close()
		


	elif device.action == 'remove':
		print "\nDevice Removed\n"
		usb_status_file=open("usb_status","w+")
		usb_status_file.write("")
		usb_status_file.close()
		
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
	# try:
	# 	print "."
	# 	sleep(2)

	# except KeyboardInterrupt:
	# 	print "\n\nExiting gracefully"
	# 	for i in range(1,19):
	# 		sys.stdout.write('.')

	# 	print "\n"
	# 	sys.exit(0)


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
proc = subprocess.Popen(['motelist|grep "/dev/ttyUSB"'],stdout=subprocess.PIPE,shell=True)
(out,err) = proc.communicate()

dev = out.split("\n")
# print dev

base_index = dev[0].find("/dev/ttyUSB")
base_add = dev[0][base_index:base_index+12]
print base_add

sniff_index = dev[1].find("/dev/ttyUSB")
sniff_add = dev[1][sniff_index:sniff_index+12]
print sniff_add
proc = subprocess.Popen(['tos-deluge serial@'+base_add+":115200 -id"],stdout=subprocess.PIPE,shell=True)
(out,err) = proc.communicate()

if "ERROR" in out:
	#This is not the basestation, swap the addresses
	(base_add,sniff_add) = (sniff_add,base_add)

usb_status_file=open("usb_status","w+")
usb_status_file.write(base_add+"\n")
usb_status_file.write(sniff_add)
usb_status_file.close()
