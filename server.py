'''
Web application to interact with the WSN Testbed. 
Features:

1.Ping all nodes
2.Upload tos_image.xml files
3.Listen mode: Basestation sniffer and show output in a console online
4.Switch images on all nodes and show image details of current slot after switching
5.Detect changes in port,status of basestation plugged into laptop
6.Read basestation's contents in the eeprom slots
'''

import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, Response, send_file, make_response
from werkzeug import secure_filename
import serial
from flask.ext.socketio import SocketIO, emit
from time import sleep
import subprocess
import sys
import json
import sqlite3
import re #String replacements
# import mosquitto, os, urlparse
from gevent import monkey
monkey.patch_all()
import paho.mqtt.client as mqtt
import urlparse
import zlib

#Global variable declarations
node_list = []
cluster_id = 1
node_list_alive=[]
templateData = {
    'consoledata':"Nothing yet"+"\n",
    'baseimagedata':"BaseStation offline"+"\n",
    'flashstarted' : "False"
}

slotnum = 1
imagepath = "uploads/"

# Initialize the Flask application
app = Flask(__name__)
app.debug=True

#Code uploading
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = set(['xml'])

#Packet sniffing
app.config['SECRET_KEY']="secret!"
socketio=SocketIO(app)
listenrequest=False
flashresponse=False
ackrequired=False
checksumvalid=True
mqttc = mqtt.Client()

#Database initialisation
file_status = os.path.isfile('gateway.db')

if (file_status == False):
    conn = sqlite3.connect('gateway.db')
    conn.execute('''CREATE TABLE NODEDETAILS 
        (ID INTEGER PRIMARY KEY AUTOINCREMENT,
        NODE_NUM    INT NOT NULL,
        DEV_ID    TEXT,
        NODE_TYPE   TEXT,
        SPECIAL_PROP    TEXT,
        BATTERY_STATUS  TEXT );''')
    conn.execute('''CREATE TABLE LISTENDATA
        (ID INTEGER PRIMARY KEY AUTOINCREMENT,
            DATE TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            DATA TEXT NOT NULL);''')
    conn.execute('''CREATE TABLE ACTIVITYLOG
        (ID INTEGER PRIMARY KEY AUTOINCREMENT,
            ACTIVITY TEXT NOT NULL,
            DATE TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);''')
    conn.close()
  
conn=sqlite3.connect('gateway.db')
#Function Definitions
def BaseStationAllDetails():
    basepathdetect()
    data = {
    'Basenodeid': '0',
    'Progname1':'1',
    'Progname2':'2',
    'Progname3':'3',
    'Gatewaymac':'12:34:56:78:90:ab',
    'Gatewayip':'0.0.0.0'
    }
    for i in range (1,4):
        a = ImageDetails(i)
        if a == "BaseStation Disconnected!":
            data['Basenodeid'] = "0"
            data['Progname'+str(i)] = str(i)
        else:
            data['Basenodeid'] = a[0]
            data['Progname'+str(i)] = a[1]+"\n"+a[2]

    proc = subprocess.Popen(["ifconfig"],stdout=subprocess.PIPE, shell=True)
    (out,err) = proc.communicate()

    mac_index = out.find("HWaddr ")+len("HWaddr ")
    mac = out[mac_index:mac_index+len("b8:27:eb:64:5c:6f")]
    # print "MAC Address: " + mac +"\n"
    data['Gatewaymac']=mac
    ip_index = out.find("inet addr:")+len("inet addr:")
    ip = out[ip_index:ip_index+len("192.168.137.103")]
    data['Gatewayip']=ip
    print data
    return data


def ImageDetails(imagenum):
    data = []
    # usb_path_base = '/dev/ttyUSB0'
    global usb_path_base
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

def MQTTInit():
    # Assign event callbacks
    mqttc.on_message = on_message
    mqttc.on_connect = on_connect
    mqttc.on_publish = on_publish
    # mqttc.on_subscribe = on_subscribe

    url_str = 'mqtt://192.168.137.103:1883'
    url = urlparse.urlparse(url_str)
    mqttc.connect(url.hostname, url.port)

    #Channels to subscribe
    mqttc.subscribe("register_response",0)
    mqttc.loop_start()
    
def gateway_init():
    MQTTInit()    
    data=BaseStationAllDetails()
    mqttc.publish('register',json.dumps(data))

#MQTT Functions
def on_connect(mosq, obj,flags,rc):
    print("rc: " + str(rc))
    mqttc.subscribe("commands/" +str(cluster_id), 0)
    mqttc.subscribe("files/"+str(cluster_id),0)

    global flashresponse
    if flashresponse:
        output = {'data':"Injection complete,Flash initiated!"}
        print output
        mqttc.publish("response/"+str(cluster_id),"flash " + json.dumps(output))
        flashresponse=False

def on_message(mosq, obj, msg):
    print(msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
    if (msg.topic) == "files/"+str(cluster_id):
        fd=open("uploads/tos_image_1.xml","w+")

        checksum = zlib.crc32(msg.payload, 0xFFFF)
        print "Checksum is: " + str(checksum)
        fd.write(msg.payload)
        fd.close()
       
    if "files/" in msg.topic:
        pass
    else:
        conn.execute('INSERT INTO ACTIVITYLOG (ACTIVITY) VALUES (\''+msg.topic+':'+msg.payload+'\')')
        conn.commit()

    if str(msg.payload) == "usbbasepath":
        basepathdetect()
    elif "ping" in str(msg.payload):
        imagenum=str(msg.payload).replace("ping ",'')
        pingall(imagenum)
    elif "switch" in str(msg.payload):
        imagenum=str(msg.payload).replace("switch ",'')
        switch(imagenum)
    elif "startlisten" in str(msg.payload):
        startlisten()
    elif "stoplisten" in str(msg.payload):
        stoplisten()
    elif "flash" in str(msg.payload):
        slotnum=str(msg.payload).replace("flash ",'')
        #global imagepath
        if checksumvalid == True:
            uploadtomote(slotnum,"uploads/tos_image_1.xml")
        else:
            output = {'data':"Injection Not complete, Please Reflash"}
            conn.execute('INSERT INTO ACTIVITYLOG (ACTIVITY) VALUES (\''+"response/"+str(cluster_id)+"flash " + json.dumps(output)+'\')')
            mqttc.publish("response/"+str(cluster_id),"flash " + json.dumps(output))
    elif "acitivitydelete" in str(msg.payload):
    	conn.execute('DELETE FROM ACTIVITYLOG')
    	conn.commit()

    elif "ackreceived" in str(msg.payload):
        ackreceived()
    elif "checksum" in str(msg.payload):
        checksum=str(msg.payload).replace("checksum ",'')
        print checksum
        fd=open("uploads/tos_image_1.xml")
        datastring = fd.read()
        checksum_file = zlib.crc32(datastring, 0xFFFF)
        global checksumvalid
        if str(checksum) != str(checksum_file):
            checksumvalid=False
        print checksumvalid
    elif "activitylog" in str(msg.payload):
        cursor=conn.execute("SELECT * FROM ACTIVITYLOG")
        mqttc.publish("response/"+str(cluster_id),"activitylog ")
        tosend=""
        for i in cursor.fetchall():
            tosend+=str(i)
            tosend+="\n"
        mqttc.publish("response/"+str(cluster_id),tosend)

    elif msg.topic == "register_response":
        print msg.payload
        a=json.loads(msg.payload)

        global node_list,cluster_id

        node_list = a['listofnodes']
        cluster_id = a['clusterid']

def on_publish(mosq, obj, mid):
    print("mid: " + str(mid))
    conn.commit()

# def on_subscribe(mosq, obj, mid, granted_qos):
#     print("Subscribed: " + str(mid) + " " + str(granted_qos))

def uploadtomote(slotnum,imgpath):

    print "Uploading to slot number "+slotnum
    proc = subprocess.Popen(["sym-deluge flash " + slotnum + " "  + imgpath], stdout=subprocess.PIPE,shell=True)
    (out,err) = proc.communicate()
    # out.replace()
    # out = "Hello"
    # out = out.replace("\n",'</br>')
    output = {'data':"Injection complete,Flash initiated!"}
    print output
    conn.execute('INSERT INTO ACTIVITYLOG (ACTIVITY) VALUES (\'response/'+str(cluster_id)+"flash "+json.dumps(output)+'\')')
    mqttc.publish("response/"+str(cluster_id),"flash " + json.dumps(output))
    global flashresponse
    flashresponse=True

def isNodeAlive(nodenum):
    
    proc=subprocess.Popen(["tos-deluge serial@"+usb_path_base+":115200 -pr "+str(nodenum)],stdout=subprocess.PIPE,shell = True)
    #proc=subprocess.Popen(["sym-deluge ping "+str(nodenum)],stdout=subprocess.PIPE,shell = True)
    out=proc.communicate()[0]
    print out
    if "Battery:" in out:
        out=out[84:]
    if "Command sent" in out:
        # battery=(int(out.split('\n')[0])/4095)*100
        # conn = sqlite3.connect('gateway.db')
        # conn.execute("UPDATE NODEDETAILS SET BATTERY_STATUS = \'" + str(battery) + "%\' WHERE NODE_NUM='"+str(nodenum)+"'")
        # conn.commit()
        # conn.close()
        # #out="\nPinged " + str(nodenum) + " successfully!"
        out = "Alive "
        global node_list_alive
        if str(nodenum) not in node_list_alive:
	        node_list_alive.append(str(nodenum))
    else:
        #out="\nPing of node no. " + str(nodenum) + " failed!"
        out = "Dead "
    return out

def BaseStationDetails(imagenum):
    proc = subprocess.Popen(["tos-deluge serial@" +usb_path_base+":115200 -p "+str(imagenum)],stdout=subprocess.PIPE,shell = True)
    (out,err) = proc.communicate()
    if "ERROR" in out:
        out = "BaseStation Disconnected!" 
    return out

def basepathdetect():
    global usb_path_base,usb_path_sniffer
    usb_status_file=open("usb_status","r")
    usb_path_base=usb_status_file.read(12)
    print usb_path_base
    usb_status_file.read(1)
    usb_path_sniffer=usb_status_file.read(12)
    print usb_path_sniffer
    usb_status_file.close()

    if usb_path_sniffer == "":
        usb_path_sniffer="/dev/ttyUSB1"

    if usb_path_base == "":
        usb_path_base="/dev/ttyUSB0"
        global templateData
        templateData['consoledata']="Basestation Disconnected\n"
        templateData['baseimagedata']="Basestation Disconnected\n"
    else:
        templateData['consoledata']="Basestation connected at "+ usb_path_base+"\n"
        templateData['baseimagedata']="Basestation connected at "+ usb_path_base+"\n"
    conn.execute('INSERT INTO ACTIVITYLOG (ACTIVITY) VALUES (\'response/'+str(cluster_id)+"usbbasepath"+json.dumps(templateData)+'\')')
    mqttc.publish("response/"+str(cluster_id),"usbbasepath"+json.dumps(templateData))

gateway_init()

def pingall(imagenum):
    basepathdetect()
    status=[]
    status.append(isNodeAlive(imagenum))
    status.append(imagenum)
    conn.execute('INSERT INTO ACTIVITYLOG (ACTIVITY) VALUES (\''+"response/"+str(cluster_id)+"ping "+str(json.dumps(status))+'\')')
    mqttc.publish("response/"+str(cluster_id),"ping "+json.dumps(status))

def switch(imagenum):
    basepathdetect()
    proc = subprocess.Popen(["sym-deluge switch " + str(imagenum)],stdout=subprocess.PIPE,shell = True)
    (out,err) = proc.communicate()
    out += "\nSwitched to image number " + str(imagenum)
    imageinfo = BaseStationDetails(imagenum)
    switchData = {
        'consoledata':out,
        'baseimagedata':imageinfo
    }
    conn.execute('INSERT INTO ACTIVITYLOG (ACTIVITY) VALUES (\''+"response/"+str(cluster_id),"switch "+json.dumps(switchData)+'\')')
    mqttc.publish("response/"+str(cluster_id),"switch "+json.dumps(switchData))

def startlisten():
    basepathdetect()
    # global ser
    # ser=serial.Serial(port=usb_path_base,baudrate=115200)
    global listenrequest
    listenrequest=True
    # serial_socket()

def stoplisten():
    # global ser
    global listenrequest
    listenrequest=False
    # ser.close()

def ackreceived():
    basepathdetect()
    global ackrequired
    ackrequired = True


@app.route('/data_manage/')
def data_manage():
    return render_template('data_manage.html')

@app.route('/data_add/', methods=['POST'])
def data_add():
    table=request.form['data']
    conn = sqlite3.connect('gateway.db')
    if table == "nodeadd":
        nodeid=(request.form['nodeid'])
        dev_id=(request.form['dev_id'])
        node_prop=request.form['nodeprop']
        node_type=request.form['nodetype']
        # conn.execute("INSERT INTO NODESTATUS (NODE_NUM, CLUSTER_HEAD, NODE_TYPE, SPECIAL_PROP) VALUES (%d,%d,\'%s\',\'%s\')" % (int(request.form['nodeid']), int(request.form['clusterh_id']),request.form['nodetype'],request.form['nodeprop']))
        conn.execute("INSERT INTO NODEDETAILS (NODE_NUM, DEV_ID, NODE_TYPE, SPECIAL_PROP) VALUES (" + nodeid + ",'" + dev_id + "','" + node_type + "','" + node_prop + "')")
    conn.commit()
    conn.close()
    return '0'

@app.route('/data_get/',methods=['POST'])
def data_get():
    table=request.form['data']
    conn = sqlite3.connect('gateway.db')
    if table == "nodesdata":
        cursor=conn.execute("SELECT * from NODEDETAILS")
        a = cursor.fetchall()
    print a
    conn.close()
    # print "after"+a
    return json.dumps(a)

@app.route('/data_edit/',methods=['POST'])
def data_edit():
    conn = sqlite3.connect('gateway.db')
    idno=(request.form['idno'])
    table=request.form['data']
    if table == "nodeedit":
        nodeid=(request.form['nodeid'])
        dev_id=(request.form['dev_id'])
        node_prop=request.form['nodeprop']
        node_type=request.form['nodetype']
        conn.execute("UPDATE NODEDETAILS SET NODE_NUM = "+nodeid+" ,DEV_ID = "+dev_id+", NODE_TYPE = '"+node_type+"', SPECIAL_PROP = '" + node_prop + "' WHERE ID="+ idno +";")
        print "done"
    conn.commit()
    conn.close()
    return "Done"

#If a user initiates the listen process this function reads data from serial and pushes it to the client through the socket
def serial_socket():
    line=[]
    numberofacksreceived=0
    ser = serial.Serial(port=usb_path_sniffer,baudrate=115200)
    global ackrequired,listenrequest
    while True:
        for c in ser.read(1):
            line.append(c.encode('hex'))
            if c.encode('hex')=="7e":
                if line.count('7e')==2:
                    packetdata=''.join(line)
                    if packetdata.count('00')>8:
                        packetdata = re.sub('[00]', '', packetdata)

                    if listenrequest == True:
                        mqttc.publish("listen/"+str(cluster_id),packetdata)
                        
                        conn.execute("INSERT INTO LISTENDATA (DATA) VALUES (\'"+packetdata+"\')")
                        conn.commit()
                        
                    elif ackrequired == True:
                        print packetdata
                        print (node_list_alive)
                        if packetdata.find("3f53")>0:
                            ack_index = packetdata.find("3f53")
                            numberofacksreceived+=1
                            if numberofacksreceived == len(node_list_alive):
                            	ackrequired = False
                            	numberofacksreceived=0
                            mqttc.publish("response/"+str(cluster_id),"ackreceived "+str(packetdata[ack_index-4:ack_index-2]))
                            
                    else:
                        if packetdata.find("3f53")>0:
                            ack_index = packetdata.find("3f53")
                            if packetdata[ack_index+11]=="b":
                                datapacket={
                                    'nodeid':packetdata[ack_index+4:ack_index+8],
                                    'batterystatus':packetdata[ack_index+12:ack_index+16]
                                }
                                mqttc.publish("response/"+str(cluster_id),"batterystatus "+json.dumps(datapacket))
                    ser.flush()
                    line=[]
                                    
serial_socket()

if __name__ == '__main__':
    subprocess.Popen(["python USBAutoDetect.py"],stdout=subprocess.PIPE,shell = True)
    socketio.run(app,host='0.0.0.0',port=8088)    