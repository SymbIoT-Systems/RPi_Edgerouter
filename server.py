'''
Web application to interact with the WSN Testbed. 
Features:

1.Ping selective nodes
2.Upload tos_image.xml files
3.Listen mode: Basestation sniffer? Show output in a console online --DONE!
4.Switch images on all nodes --DONE!
5.Detect a basestation plugged into laptop 
6.Read basestation's contents in the eeprom slots (later)

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

#Global variable declarations

templateData = {
    'consoledata':"Nothing yet",
    'baseimagedata':"BaseStation offline"
}

slotnum = 1
imagepath = "uploads/"

#Ensure that the initial base path while launching the server is correct
usb_path_base = os.getenv('motepath', "/dev/ttyUSB0")

# Initialize the Flask application
app = Flask(__name__)
app.debug=True

#Code uploading
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = set(['xml'])

#Packet sniffing
app.config['SECRET_KEY']="secret!"
socketio=SocketIO(app)
dataneed=False

#Function Definitions
# For a given file, return whether it's an allowed type or not
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']

def uploadtomote(slotnum,imgpath):

    print "Uploading to slot number "+slotnum
    proc = subprocess.Popen(["sym-deluge flash " + slotnum + " "  + imgpath], stdout=subprocess.PIPE,shell=True)
    (out,err) = proc.communicate()
    #out=proc.stdout.read()upl
    return out
    #print out 


def serial_socket():
	line=[]
	while dataneed:
		if dataneed==True:
			for c in ser.read():
				line.append(c.encode('hex'))
				if c.encode('hex')=="7e":
					if line.count('7e')==2:
						#print (''.join(line))
						socketio.emit('my response',{'data':''.join(line)},namespace='/test')
						line=[]

def isNodeAlive(nodenum):
    if nodenum==1:
        proc1=subprocess.Popen(["tos-deluge serial@"+usb_path_base+":115200 -sr 0"],stdout=subprocess.PIPE,shell = True)
        out1 = proc1.communicate()[0]
    
    proc=subprocess.Popen(["tos-deluge serial@"+usb_path_base+":115200 -pr "+str(nodenum)],stdout=subprocess.PIPE,shell = True)    
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


#App routes         
@app.route('/')
def index():
    return render_template('main.html',**templateData)

@app.route('/cluster_status/',methods=['POST'])
def pingall():
    status=[]
    imagenum=request.form['data']
    status.append(isNodeAlive(imagenum))
    status.append(imagenum)
    return json.dumps(status)

@app.route('/ping/', methods=['POST'])
def ping():
    if request.method == "POST":
        nodenum = request.form['nodenum']
        proc = subprocess.Popen(["sym-deluge ping " + str(nodenum)],stdout=subprocess.PIPE,shell = True)
        (out,err) = proc.communicate()
        out += "\nPinged node number " + str(nodenum)
        if "Command sent" in out:
            out="\nPinged " + str(nodenum) + " successfully!"
            #print out
        else:
            out="\nPing of node no. " + str(nodenum) + " failed!"
        return out
    else:
        return redirect('/')    

    
@app.route('/switch/', methods=['POST'])
def switch():
    if request.method == "POST":
        imagenum = request.form['imagenumberswitch']

        proc = subprocess.Popen(["sym-deluge switch " + str(imagenum)],stdout=subprocess.PIPE,shell = True)
        (out,err) = proc.communicate()
        out += "\nSwitched to image number " + str(imagenum)
        imageinfo = BaseStationDetails(imagenum)
        templateData = {
            'consoledata':out,
            'baseimagedata':imageinfo
        }

        return json.dumps(templateData)   

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
        #return redirect(url_for('uploaded_file',
        #                        filename=filename))
    
    # data1=uploadtomote(request.form['imagenumber'],imagepath)
    
    # thread = threading.Thread(target=uploadtomote,args=(request.form['imagenumber'],imagepath))
    # thread.start()

    data1 = "Flash Initiated"
    global templateData

    templateData = {
     'consoledata':data1
    }
    return redirect('/')

@app.route('/flashnode/', methods=['POST'])
def flashnode():
    global imagepath,slotnum
    data1=uploadtomote(slotnum,imagepath)
    return data1

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)

@socketio.on('listen',namespace='/test')
def test_message():
    global ser
    ser=serial.Serial(port=usb_path_base,baudrate=115200)
    subprocess.call(["tos-deluge serial@"+usb_path_base+":115200 -sr 1"],shell=True)
    global dataneed
    dataneed=True
    #print dataneed
    serial_socket()

@app.route('/savelog/',methods=['POST'])
def savedata():
    log_file=open(app.config['UPLOAD_FOLDER']+"log.txt","w+")
    log_file.write(request.form['filedata'])
    log_file.close()
    headers = {"Content-Disposition":"attachment; filename=log.txt"}
    with open("uploads/log.txt",'r') as f:
        body=f.read()
        return make_response((body,headers))
    # return send_file(app.config['UPLOAD_FOLDER']+"log.txt",as_attachment=True)
    #return "Done"
    #stop listening

@app.route('/stop/',methods=['POST'])
def stop():
    global ser
    global dataneed
    dataneed=False
    ser.close()
	
	#print dataneed
    return "0"


@app.route('/ackreceived/',methods=['POST'])
def ackreceived():
    
    line=[]
    ser1=serial.Serial(port=usb_path_base,baudrate=115200)
    while True:
        try:
            for c in ser1.read():
                line.append(c.encode('hex'))
                if c.encode('hex')=="7e":
                    if line.count('7e')==2:
                        packet=''.join(line)
                        print packet

                        if packet[24:30]=="003f53":
                            print packet[22:24]
                            ser1.close()
                            return packet[22:24]
                            line=[] 

        except serial.serialutil.SerialException:
            pass

                


if __name__ == '__main__':
    proc = subprocess.Popen(["python USBAutoDetect.py"],stdout=subprocess.PIPE,shell = True)
    socketio.run(app,host='0.0.0.0',port=8080)


