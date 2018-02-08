'''
Metadata is represented as key-value pairs
Keys may be repeated so in YAML format, values are contained in string and list objects

File manifest data are contained in string, list, and dictionary objects
'''

import yaml
from uuid import UUID
import sqlite3

conn = sqlite3.connect('imas.db')
#con = sqlite3.connect(":memory:")
#con.isolation_level = None
c = conn.cursor();

def sqlQuery(sql):
   print(sql)
   return 0;

def sqlDrop():
   c.execute("DROP TABLE main.simulations;")
   c.execute("DROP TABLE main.metadata;")
                 
'''   c.execute("DROP TABLE main.simulations; "+
             "DROP TABLE main.metadata; "+
             "DROP TABLE main.simulation_files; "+
             "DROP TABLE main.files;")                     
'''   
def sqlCreate():
   c.execute("CREATE TABLE main.simulations (simulation_id INTEGER UNIQUE NOT NULL PRIMARY KEY ASC AUTOINCREMENT, "+ 
                                            "simulation_uuid TEXT NOT NULL, "+
			                    "status TEXT NOT NULL, "+
			                    "current_date TEXT NOT NULL, "+ 
			                    "current_time TEXT NOT NULL);") 
					    
   c.execute("CREATE TABLE main.metadata (metadata_id INTEGER UNIQUE NOT NULL PRIMARY KEY ASC AUTOINCREMENT, "+ 
                                         "metadata_set_uuid TEXT NOT NULL, "+ 
			                 "element TEXT NOT NULL, "+
			                 "value TEXT);")

   c.execute("CREATE TABLE main.files (file_id INTEGER UNIQUE NOT NULL PRIMARY KEY ASC AUTOINCREMENT, "+ 
                                      "file_uuid TEXT NOT NULL, "+ 
			              "metadata_set_uuid TEXT FOREIGN KEY, "+ 
			              "useage TEXT, "+
			              "filename TEXT NOT NULL, "+
			              "directory TEXT, "+
			              "checksum TEXT, "+
			              "type TEXT, "+
			              "purpose TEXT, "+
			              "sensitivity TEXT, "+
			              "access TEXT, "+
			              "embargo TEXT, "+
			              "current_date TEXT NOT NULL, "+ 
			              "current_time TEXT NOT NULL, "+
				      "FOREIGN KEY(metadata_set_uuid) REFERENCES main.metadata(metadata_set_uuid));")

   c.execute("CREATE TABLE main.simulation_files (simulation_files_id INTEGER UNIQUE NOT NULL PRIMARY KEY ASC AUTOINCREMENT, "+ 
                                                 "simulation_uuid TEXT NOT NULL FOREIGN KEY, "+ 
				                 "file_uuid TEXT NOT NULL, "+
						 "FOREIGN KEY(simulation_uuid) REFERENCES main.simulations(simulation_uuid), "+
						 "FOREIGN KEY(file_uuid) REFERENCES main.files(file_uuid));")
				      
				            
   
def sqlBegin():
   print('BEGIN TRANSACTION;')
def sqlCommit():
   print('COMMIT;')   

def sqlInsert(table, uuid, name, value):
   print("INSERT INTO "+table+" (UUID, NAME, VALUE) VALUES ('"+uuid+"', '"+name+"', '"+value+"');") 
   return 1
    
def sqlUpdate(table, uuid, name, value):
   print("UPDATE "+table+" SET VALUE = '"+value+"' WHERE UUID='"+uuid+"' AND NAME='"+name+"';")
   return 1
   
def validateUUID(uuid):
    try:
        val = UUID(uuid, version=4)
    except ValueError:
        return False
    return True
   
def ingestFile(fileClass, fileName):

   fd = open(fileName,"r")
   x = yaml.load(fd)           # x is a dictionary

   print(yaml.dump(x))
 
# read the UUID for the simulation. If it is not given in the YAML file, then it needs to be 
# accessed from the user's .imasdb file or simulation DBMS

   uuid = ''
   alias = ''
   isValidUUID = False

   if fileClass == 'metadata':
   
      key = 'identifier'
   
      if isinstance(x[key], str):
         uuid = x[key]   # May not be defined in the YAML file
         isValidUUID = validateUUID(uuid)
         if not isValidUUID:
            uuid = ''
   
      if not isValidUUID and isinstance(x[key], list):             # Must be a maximum of 2 - a UUID and an Alias
      
         if len(x[key]) > 2:
            print('ERROR ... Too many IDENTIFIERS specified in the METADATA file')
            return 1
      
         for i in range(0, len(x[key])):

            if isValidUUID:
               alias = x[key][i]
            else:
               uuid = x[key][i]
               isValidUUID = validateUUID(uuid)
               if not isValidUUID:
                  uuid = ''
                  alias = x[key][i]

   if fileClass == 'manifest':

      key = 'uuid'
      if isinstance(x[key], str):
         uuid = x[key]
         isValidUUID = validateUUID(uuid)

      key = 'alias'
      if isinstance(x[key], str):
         alias = x[key]    
   
   if not isValidUUID:
      if fileClass == 'manifest':
         print('ERROR ... The simulation uuid has not been specified in your simulation file manifest. Please use the UUID key for this identifier.')
      else:
         print('ERROR ... The simulation uuid has not been specified in your simulation metadata file. Please use the IDENTIFIER key for this parameter.') 
      return 1;
      
# Validate the uuid

   if sqlQuery("select * from main.simulations where simulation_uuid = '"+uuid+"';'"):
      print('ERROR ... The simulation uuid provided is not registered in your IMAS database!')
      return 1;
    
   
   #print(isValidUUID)
   #print(uuid)
   #print(alias)
   #quit()       
   
# Extract all keys - each is unique

   if fileClass == 'metadata' and isValidUUID:
   
      for key in x:
         print(key)
	 
         if isinstance(x[key], str):
            print('STRING:'+ x[key])
            if sqlUpdate('metadata', uuid, key, x[key]):
               sqlInsert('metadata', uuid, key, x[key])

         #continue
      
         if isinstance(x[key], list):
            xlist = x[key]
            #print('LIST:')
            #print(len(xlist))
            #print(xlist)
 
            for i in range(0, len(xlist)):
               #print('--------')
               #print(i)
               #print(type(xlist[i]))
         
               if isinstance(xlist[i],str):
                  print('STRING:'+ xlist[i])
                  if sqlUpdate('metadata', uuid, key, xlist[i]):
                     sqlInsert('metadata', uuid, key, xlist[i])
	    	    	    
               if isinstance(x[key][i], list):
                  print('LIST:')
                  #print(len(x[key][i]))
                  #print(x[key][i])
	    
               if isinstance(x[key][i], dict):
                  print('DICT-1:')
                  print(len(x[key][i]))
                  print(x[key][i])
               #print('--------')
	  
         if isinstance(x[key], dict):
            print('DICT-2:')
            print(len(x[key]))
            print(x[key])

   if fileClass == 'manifest' and isValidUUID:
   
      for key in x:
         print(key)
	 
         if isinstance(x[key], str):
            print('STRING:'+ x[key])
            if sqlUpdate('metadata', uuid, key, x[key]):
               sqlInsert('metadata', uuid, key, x[key])
	       
         if isinstance(x[key], list):
            xlist = x[key]
            print('LIST:')
            print(len(xlist))
            print(xlist)
	       

         continue
      
         if isinstance(x[key], list):
            xlist = x[key]
            #print('LIST:')
            #print(len(xlist))
            #print(xlist)
 
            for i in range(0, len(xlist)):
               #print('--------')
               #print(i)
               #print(type(xlist[i]))
         
               if isinstance(xlist[i],str):
                  print('STRING:'+ xlist[i])
                  if sqlUpdate('metadata', uuid, key, xlist[i]):
                     sqlInsert('metadata', uuid, key, xlist[i])
	    	    	    
               if isinstance(x[key][i], list):
                  print('LIST:')
                  #print(len(x[key][i]))
                  #print(x[key][i])
	    
               if isinstance(x[key][i], dict):
                  print('DICT-1:')
                  print(len(x[key][i]))
                  print(x[key][i])
               #print('--------')
	  
         if isinstance(x[key], dict):
            print('DICT-2:')
            print(len(x[key]))
            print(x[key])


   return 0


#fileName = './test0.yaml'
#fileClass = 'metadata'

sqlDrop()
sqlCreate()

fileName = './manifest'
fileClass = 'manifest'

print(ingestFile(fileClass, fileName))
