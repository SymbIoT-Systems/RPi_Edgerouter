import subprocess

def GatewayDetails():
	proc = subprocess.Popen(["ifconfig"],stdout=subprocess.PIPE, shell=True)
	(out,err) = proc.communicate()

	mac_index = out.find("HWaddr ")+len("HWaddr ")
	mac = out[mac_index:mac_index+len("b8:27:eb:64:5c:6f")]
	# print "MAC Address: " + mac +"\n"

	ip_index = out.find("inet addr:")+len("inet addr:")
	ip = out[ip_index:ip_index+len("192.168.137.104")]
	# print "IP Address: " + ip +"\n"

	return (mac,ip)


def BaseStationDetails():
	data = {
	'Basenodeid': '0',
	'Progname1':'1',
	'Compiletime1':'1',
	'Progname2':'2',
	'Compiletime2':'2',
	'Progname3':'3',
	'Compiletime3':'3'
	}
	for i in range (1,4):
		a = ImageDetails(i)
		if a == "BaseStation Disconnected!":
			data['Basenodeid'] = "0"
			data['Progname'+str(i)] = str(i)
			data['Compiletime'+str(i)] = str(i)
		else:
			data['Basenodeid'] = a[0]
			data['Progname'+str(i)] = a[1]
			data['Compiletime'+str(i)] = a[2]

	return data


def ImageDetails(imagenum):
	data = []
	usb_path_base = '/dev/ttyUSB0'
	proc = subprocess.Popen(["tos-deluge serial@" +usb_path_base+":115200 -p "+str(imagenum)],stdout=subprocess.PIPE,shell = True)
	(out,err) = proc.communicate()
	
	img = out.split('\n') 
	data.append(img[8].replace("Node ID:    ",""))
	data.append((img[11].replace("Prog Name:   ","")).replace("\x00",""))
	data.append(img[13].replace("Compiled On: ",""))
	
	if "ERROR" in out:
		out = "BaseStation Disconnected!"
		return out
	else:
		return data

print "MAC Addr is: " + GatewayDetails()[0]
print "IP Addr is: " + GatewayDetails()[1]

print BaseStationDetails()