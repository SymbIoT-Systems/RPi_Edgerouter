'''
Web application to interact with the WSN Testbed. 
Features:

1.Ping selective nodes
2.Upload tos_image.xml files
3.Listen mode: Basestation sniffer? Show output in a console online
4.Switch images on all nodes
5.Detect a basestation plugged into laptop 
6.Read basestation's contents in the eeprom slots (later)

'''

import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory,Response
from werkzeug import secure_filename
import serial
from flask.ext.socketio import SocketIO, emit
from time import sleep
import subprocess
from pyudev import Context, Monitor, MonitorObserver, Device
import sys 
import threading

templateData = {
    'data':"Nothing yet"
}

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

def ackreceived():
    line=[]
    ser1=serial.Serial(port=usb_path_base,baudrate=115200)
    while True:
        for c in ser1.read():
            line.append(c.encode('hex'))
            if c.encode('hex')=="7e":
                if line.count('7e')==2:
                    packet=''.join(line)
                    if packet[24:30]=="003f53":
                        print packet[22:24]
                        ser1.close()
                        return 0
                    line=[]


def uploadtomote(slotnum,imgpath):

    print "Uploading to slot number "+slotnum
    proc = subprocess.Popen(["sym-deluge flash " + slotnum + " "  + imgpath], stdout=subprocess.PIPE,shell=True)
    #(out,err) = proc.communicate()
    out=proc.stdout.read()
    thread = threading.Thread(target=ackreceived)
    thread.start()
    print out 


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
    proc = subprocess.Popen(["sym-deluge ping " + str(nodenum)],stdout=subprocess.PIPE,shell = True)
    (out,err) = proc.communicate()
    #out += "\nPinged node number " + str(nodenum)

    if "Command sent" in out:
        #out="\nPinged " + str(nodenum) + " successfully!"
        out = "Alive "
            
    else:
        #out="\nPing of node no. " + str(nodenum) + " failed!"
        out = "Dead "
    return out


#App routes         
@app.route('/')
def index():

    return render_template('main.html',**templateData)

@app.route('/cluster_status/',methods=['POST'])
def pingall():
    cluster_status = []
    for i in range (1,8):
        cluster_status.append(isNodeAlive(i)) 

    status = ''.join(cluster_status)
    return status

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
        imagenum = request.form['imagenum']
        proc = subprocess.Popen(["sym-deluge ping " + str(imagenum)],stdout=subprocess.PIPE,shell = True)
        (out,err) = proc.communicate()
        out += "\nSwitched to image number " + str(imagenum)
        return out
        
    else:
        return redirect('/')   

# Route that will process the file upload

@app.route('/upload', methods=['POST'])
def upload():
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
    
    #data1 = uploadtomote(request.form['imagenumber'],imagepath)
    
    thread = threading.Thread(target=uploadtomote,args=(request.form['imagenumber'],imagepath))
    thread.start()

    # global templateData

    # templateData = {
    # 'data':data1
    # }
    return redirect('/')
	
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

#stop listening
@app.route('/stop/',methods=['POST'])
def stop():
    global ser
    global dataneed
    dataneed=False
    ser.close()
	
	#print dataneed
    return "0"

#USB auto-detection of BaseStation port and activities

# @app.route('/automount',methods=['POST'])
# def automount():
#     if request.form['status']=="Added":
#         port=request.form['port']
#         global usb_path_base
#         usb_path_base=port
#         print port
#     return "0"

if __name__ == '__main__':
    socketio.run(app,host='0.0.0.0',port=8080)