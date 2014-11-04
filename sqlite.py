#File for managing database

import sqlite3

conn=sqlite3.connect('gateway.db')
print "Connection Opened"

conn.execute('''CREATE TABLE nodestatus 
		(ID INT PRIMARY KEY NOT NULL,
		NODE_NUM	INT NOT NULL,
		CLUSTER_HEAD	TEXT NOT NULL,
		NODE_TYPE	TEXT NOT NULL,
		SPECIAL_PROP	TEXT NOT NULL,
		BATTERY_STATUS	TEXT NOT NULL);''')

print "Table Created"
conn.close()
