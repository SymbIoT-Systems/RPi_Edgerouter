#File for managing database

import sqlite3
import json

conn=sqlite3.connect('gateway.db')
print "Connection Opened"

# conn.execute('''CREATE TABLE nodestatus 
# 		(ID INT PRIMARY KEY NOT NULL,
# 		NODE_NUM	INT NOT NULL,
# 		CLUSTER_HEAD	TEXT NOT NULL,
# 		NODE_TYPE	TEXT NOT NULL,
# 		SPECIAL_PROP	TEXT NOT NULL,
# 		BATTERY_STATUS	TEXT NOT NULL);''')

# conn.execute("INSERT INTO NODESTATUS (NODE_NUM,CLUSTER_HEAD,NODE_TYPE,SPECIAL_PROP) VALUES (1,2,'123','334')")
# conn.commit()

cursor=conn.execute("SELECT * from NODESTATUS")
print json.dumps(cursor.fetchall())
print "Table Created"
conn.close()
