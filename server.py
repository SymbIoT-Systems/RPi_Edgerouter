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
from pyudev import Context, Monitor, MonitorObserver, Device
import sys
import json
import sqlite3

#Global variable declarations

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

#Database initialisation
file_status = os.path.isfile('gateway.db')

if (file_status == False):
    conn = sqlite3.connect('gateway.db')
    conn.execute('''CREATE TABLE NODESTATUS 
        (ID INTEGER PRIMARY KEY AUTOINCREMENT,
        NODE_NUM    INT NOT NULL,
        CLUSTER_HEAD    TEXT NOT NULL,
        NODE_TYPE   TEXT,
        SPECIAL_PROP    TEXT,
        BATTERY_STATUS  TEXT );''')
    conn.close()

    

#Function Definitions
# For a given file, return whether it's an allowed type or not
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']

def uploadtomote(slotnum,imgpath):

    print "Uploading to slot number "+slotnum
    proc = subprocess.Popen(["sym-deluge flash " + slotnum + " "  + imgpath], stdout=subprocess.PIPE,shell=True)
    (out,err) = proc.communicate()
    return out

#If a user initiates the listen process this function reads data from serial and pushes it to the client through the socket
def serial_socket():
    line=[]
    while listenrequest:
        
        if listenrequest==True:
            for c in ser.read(1):

                line.append(c.encode('hex'))
                if c.encode('hex')=="7e":
                    if line.count('7e')==2:
                        print ''.join(line)
                        socketio.emit('my response',{'data':''.join(line)},namespace='/listen')
                        ser.flush()
                        line=[]

def isNodeAlive(nodenum):
    if nodenum==1:
        proc1=subprocess.Popen(["tos-deluge serial@"+usb_path_base+":115200 -sr 0"],stdout=subprocess.PIPE,shell = True)
        out1 = proc1.communicate()[0]
    
    #proc=subprocess.Popen(["tos-deluge serial@"+usb_path_base+":115200 -pr "+str(nodenum)],stdout=subprocess.PIPE,shell = True)
    proc=subprocess.Popen(["sym-deluge ping "+str(nodenum)],stdout=subprocess.PIPE,shell = True)
    out=proc.communicate()[0]

    if "Command sent" in out:
        #out="\nPinged " + str(nodenum) + " successfully!"
        out = "Alive "
    else:
        #out="\nPing of node no. " + str(nodenum) + " failed!"
        out = "Dead "

    if nodenum==8:
        subprocess.Popen(["tos-deluge serial@"+usb_path_base+":115200 -sr 1"],stdout=subprocess.PIPE,shell = True)
    return out

def BaseStationDetails(imagenum):
    proc = subprocess.Popen(["tos-deluge serial@" +usb_path_base+":115200 -p "+str(imagenum)],stdout=subprocess.PIPE,shell = True)
    (out,err) = proc.communicate()
    if "ERROR" in out:
        out = "BaseStation Disconnected!"
    
    return out

def basepathdetect():
    global usb_path_base
    usb_status_file=open("usb_status","r")
    usb_path_base=usb_status_file.read(12)
    print usb_path_base
    usb_status_file.close()

    if usb_path_base == "":
        usb_path_base="/dev/ttyUSB0"
        global templateData
        templateData['consoledata']+="Basestation Disconnected\n"
        templateData['baseimagedata']="Basestation Disconnected\n"
    else:
        templateData['consoledata']+="Basestation connected at "+ usb_path_base+"\n"
        templateData['baseimagedata']="Basestation connected at "+ usb_path_base+"\n"

#App routes         
@app.route('/')
def index():
    basepathdetect()
    return render_template('main.html',**templateData)

@app.route('/cluster_status/',methods=['POST'])
def pingall():
    basepathdetect()
    status=[]
    imagenum=request.form['data']
    status.append(isNodeAlive(imagenum))
    status.append(imagenum)
    return json.dumps(status)
    
@app.route('/switch/', methods=['POST'])
def switch():
    if request.method == "POST":
        basepathdetect()
        imagenum = request.form['imagenumberswitch']

        proc = subprocess.Popen(["sym-deluge switch " + str(imagenum)],stdout=subprocess.PIPE,shell = True)
        (out,err) = proc.communicate()
        out += "\nSwitched to image number " + str(imagenum)
        imageinfo = BaseStationDetails(imagenum)
        switchData = {
            'consoledata':out,
            'baseimagedata':imageinfo
        }
        return json.dumps(switchData)   

# Route that will process the file upload
@app.route('/upload', methods=['POST'])
def upload():
    global imagepath,slotnum
    slotnum=request.form['imagenumber']

    # Get the name of the uploaded file
    file = request.files['file']
    # Check if the file is one of the allowed types/extensions
    if file and allowed_file(file.filename):
        # Make the filename safe, remove unsupported chars
        filename = secure_filename(file.filename)
        imagepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(imagepath)

    global templateData
    templateData['flashstarted']="True"
    return redirect('/')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename,as_attachment=True)

@app.route('/flashnode/', methods=['POST'])
def flashnode():
    global imagepath,slotnum
    reply=uploadtomote(slotnum,imagepath)
    templateData['flashstarted']="False"
    return reply

@app.route('/startlisten/',methods=['POST'])
def startlisten():
    basepathdetect()
    global ser
    ser=serial.Serial(port=usb_path_base,baudrate=115200)
    global listenrequest
    listenrequest=True
    serial_socket()
    return "Listen Start Done"    

@app.route('/savelog/',methods=['POST'])
def savedata():
    log_file=open(app.config['UPLOAD_FOLDER']+request.form['filename'],"w")
    log_data = request.form['filedata']
    log_data1=((log_data.replace("<p>","\n")).replace("</p>","")).replace("<br>","\n")
    log_file.write(log_data1)
    log_file.close()
    #return redirect(url_for('uploaded_file',filename="log.txt"))
    return "Uploaded"

@app.route('/stoplisten/',methods=['POST'])
def stoplisten():
    global ser
    global listenrequest
    listenrequest=False
    ser.close()
    return "0"


@app.route('/ackreceived/',methods=['POST'])
def ackreceived():
    basepathdetect()
    line=[]
    ser1=serial.Serial(port=usb_path_base,baudrate=115200)
    while True:
        for c in ser1.read():
            line.append(c.encode('hex'))
            if c.encode('hex')=="7e":
                if line.count('7e')==2:
                    packet=''.join(line)
                    print packet
                    if packet[24:30]=="003f53":
                        print packet[22:24]
                        ser1.close()
                        global templateData
                        templateData['consoledata']="Nothing yet"
                        return packet[22:24]
                    line=[] 
                    packet=""

@app.route('/data_manage/')
def data_manage():

    return render_template('data_manage.html')

@app.route('/data_add/', methods=['POST'])
def data_add():
    conn = sqlite3.connect('gateway.db')
    nodeid=(request.form['nodeid'])
    clusterh_id=(request.form['clusterh_id'])
    node_prop=request.form['nodeprop']
    node_type=request.form['nodetype']
    # conn.execute("INSERT INTO NODESTATUS (NODE_NUM, CLUSTER_HEAD, NODE_TYPE, SPECIAL_PROP) VALUES (%d,%d,\'%s\',\'%s\')" % (int(request.form['nodeid']), int(request.form['clusterh_id']),request.form['nodetype'],request.form['nodeprop']))
    conn.execute("INSERT INTO NODESTATUS (NODE_NUM, CLUSTER_HEAD, NODE_TYPE, SPECIAL_PROP) VALUES (" + nodeid + "," + clusterh_id + ",'" + node_type + "','" + node_prop + "')")
    conn.commit()
    conn.close()
    return '0'

@app.route('/data_get/',methods=['POST'])
def data_get():
    conn = sqlite3.connect('gateway.db')
    cursor=conn.execute("SELECT * from NODESTATUS")
    a = cursor.fetchall()
    print a
    conn.close()
    # print "after"+a
    return json.dumps(a)

#NOT REDUNDANT!
@socketio.on('listen',namespace='/listen')
def handle_message(message):
    print('received message: ' + message)


if __name__ == '__main__':
    proc = subprocess.Popen(["python USBAutoDetect.py"],stdout=subprocess.PIPE,shell = True)
    socketio.run(app,host='0.0.0.0',port=8088)



