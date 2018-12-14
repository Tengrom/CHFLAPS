import multiprocessing
from time import sleep
import pprint
import requests
from requests.auth import HTTPBasicAuth
import ldap
from datetime import datetime, timedelta, tzinfo
from calendar import timegm
import psycopg2
import sys, getopt
import ipaddress
import nmap
import csv
import psutil
import os
import logging
EPOCH_AS_FILETIME = 116444736000000000  # January 1, 1970 as MS file time
HUNDREDS_OF_NANOSECONDS = 10000000
period = datetime.utcnow() - timedelta(days=30)
period2 = datetime.utcnow() - timedelta(days=7)

#User , Password and domain  for LDAP query
ADusers = ""
ADpass = ""
ADdomains = ""
#Initialize Port Scanner
nm=nmap.PortScanner()
#Class for information from smb-os-discovery nmap script
class SMB_host:
    def __init__(self, ip):
        self.ip = ip
        self.OS=""
        self.Computer_name=""
        self.Domain=""
        self.Workgroup=""
        self.CPE=""
        self.Dialects=""
        self.SMBv1=""
    def add_OS(self, OS):
        self.OS=OS

    def add_Computer_name(self, Computer_name):
        self.Computer_name=Computer_name

    def add_Domain(self, Domain):
        self.Domain=Domain

    def add_Workgroup(self, Workgroup):
        self.Workgroup=Workgroup

    def add_CPE(self, CPE):
        self.CPE=CPE

    def add_Dialects(self, Dialects):
        self.Dialects=Dialects

    def add_SMBv1(self, SMBv1):
        self.SMBv1=SMBv1
#function to checking from with subnets is scanned IP( need to be moved from file to DB)
def sites_continent(ip):
    site_res=""
    with open('/root/script/Subnets_NA.csv' ) as csvfile:
        spamreader = csv.reader(csvfile, delimiter=',', quotechar='|')
        for row in spamreader:
            value=row[0]
            value2=value

            if(ipaddress.ip_address(ip) in ipaddress.ip_network(value2, False)):
                site_res="NA"
    return site_res

#function to checking from with subnets is scanned IP( need to be moved from file to DB)
def sites_count(ip):
    site_res=""
    with open('/root/script/sites_list.csv' ) as csvfile:
        spamreader = csv.reader(csvfile, delimiter=',', quotechar='|')
        for row in spamreader:
            value=row[3]+'/'+row[4]
            value2=value

            
            if (row[3]!="Network"):
                if(ipaddress.ip_address(ip) in ipaddress.ip_network(value2, False)):
                    site_res=row[5]
    return site_res
#function to parse info from smb-os-discovery
def smb_info_parser(nmap_results,host_ip):
    output_list=[]
    test=nmap_results._scan_result['scan'][host_ip]['hostscript']
    Check_for_attributes=('OS:','Computer name:','Domain name:','Workgroup','CPE:','dialects:','SMBv1')
    Network_class=SMB_host(host_ip)
    output_list.append(Network_class)
    for output in test:
        test_output=str(output)
        part22=test_output.split("\\n")
        for parts in part22:
            if any(attrib in parts for attrib in Check_for_attributes):
                if (Check_for_attributes[0] in parts):
                    parts_split=parts.split(":")
                    OS_part=parts_split[1].strip()
                    Network_class.add_OS(OS_part)

                elif (Check_for_attributes[1] in parts):
                    parts_split=parts.split(":")
                    Computer_name_part=parts_split[1].strip()
                    Network_class.add_Computer_name(Computer_name_part)

                elif (Check_for_attributes[2] in parts):
                    parts_split=parts.split(":")
                    Domain_part=parts_split[1].strip()
                    Network_class.add_Domain(Domain_part)

                elif (Check_for_attributes[3] in parts):
                    parts_split=parts.split(":")
                    Workgroup_part=parts_split[1].strip()
                    Network_class.add_Workgroup(Workgroup_part)

                elif (Check_for_attributes[4] in parts):
                    parts_split=parts.split(":",1)
                    CPE_part=parts_split[1].strip()
                    Network_class.add_CPE(CPE_part)

                elif (Check_for_attributes[5] in parts):
                    output_str=str(output)

                    Dialects_part_fin=""
                    parts_split=output_str.split(":")
                    Dialects_part=parts_split[2].split("'")
                    Dialects_small_part=Dialects_part[0].split("\\n")
                    for dialect_parts in Dialects_small_part:
                        if Check_for_attributes[6] in dialect_parts:
                            dialect_parts_split=dialect_parts.split(",")
                            Dialects_part_fin=Dialects_part_fin+dialect_parts_split[0]

                        else:
                            Dialects_part_fin=Dialects_part_fin+dialect_parts

                    Network_class.add_Dialects(Dialects_part_fin)

                elif (Check_for_attributes[6] in parts):
                    Network_class.add_SMBv1("Enabled")
    return output_list
#function to scan IP using Python nmap
def nmap_scan(ip,name,domain,conn,port_range):
    cur=conn.cursor()
    counter=1
    counter_test=1
    counter_rescan=1
    counter_str=""
    Check_read = "READ"
    #print("=======================================")
    #print(ip)
    #print("=======================================")

    #Starting scan for 445 and 139 smb ports
    nm.scan(ip,port_range,"-sV --host-timeout 60m")
    for host in nm.all_hosts():
        testhost=nm._scan_result['scan'][host]
        r2=nm._scan_result['scan'][host]['status']['state']
        r3=""
        r4=""
        if r2=="up":	
            
            sites_results=sites_count(host)
            continent_results=sites_continent(host)
            
            try:
                
                for port in nm._scan_result['scan'][host]['tcp']:
                    p1=nm._scan_result['scan'][host]['tcp'][port]['state']
                    p2=nm._scan_result['scan'][host]['tcp'][port]['name']
                    p3=nm._scan_result['scan'][host]['tcp'][port]['product']
                    p4=nm._scan_result['scan'][host]['tcp'][port]['version']
                    p5=nm._scan_result['scan'][host]['tcp'][port]['extrainfo']
                    p6=nm._scan_result['scan'][host]['tcp'][port]['cpe']
                    details=p2+" "+p3+" "+p4+" "+p5+" "+p6
                    # Add info about ports to DB
                    postgres_ports(host,port,p1,name,domain,p2,details,conn)
                    if port == 445:
                        r3 = p1
                    if port == 139:
                        r4 = p1
                dt = datetime.now()
                # if host has been scanned update time_scan info in DB 
                cur.execute("UPDATE Hosts SET time_scan = '{0}' ,IP='{1}' , Site = '{2}' , Continent = '{3}'  where name = '{4}' and domain= '{5}'".format(dt,host,sites_results,continent_results,name,domain))
                conn.commit()
            except:
                postgres_ports(host,0,"filtered",name,domain,"firewall","all ports blocked by firewall",conn)
        
        if r2=="up" and (r3 == "open" or r4 == "open"):
            #print("---------------------start scan --------------------------------")
            if r3 == "open" :
                port_str = "445"
            else:
                port_str = "139"
            nm.scan(host,port_str,"--script smb-os-discovery.nse")
            test_scan_finished=nm.all_hosts()
            test_scan_finished_len=len(test_scan_finished)
            # Check if the host has not been  switched off in the middle of scan 
            if test_scan_finished_len==0:
                #print(host+","+port_str+",Scan_error")
                postgres_vuln(host,sites_results,"",name,domain,"","","Script_scan_error",continent_results,conn)
                lists_ip=host
                lists_Computer_name=None
                lists_Domain=domain
                lists_OS=None

            else:
                output_scan=nm._scan_result['scan'][host]
                output_scan=str(output_scan)
                #check if script smb discovery script  list was able to got any info 
                scan_results_test="hostscript"
                if scan_results_test in output_scan:

                    output=smb_info_parser(nm,host)
                    for lists in output:
                         #writing info from netbios to DB
                        postgres_vuln(lists.ip,sites_results,"SMB_INFO",name,lists.Computer_name,lists.Domain,lists.OS,"",continent_results,conn)
                        lists_ip=lists.ip
                        lists_Computer_name=lists.Computer_name
                        lists_Domain=lists.Domain
                        lists_OS=lists.OS

                else:
                    lists_ip=host
                    lists_Computer_name=None
                    lists_Domain=domain
                    lists_OS=None

                    postgres_vuln(host,sites_results,"SMB_INFO",name,domain,"no_smb_info","no_smb_info","no_smb_info",continent_results,conn) 
            #scanning for additional vulns 
            nm.scan(host,port_str,"--script smb-protocols.nse,smb-vuln-ms17-010.nse ")
           

            test_scan_finished=nm.all_hosts()
            test_scan_finished_len=len(test_scan_finished)
            # Check if the host has not been  switched off in the middle of scan 
            if test_scan_finished_len!=0:
                output_scan=nm._scan_result['scan'][host]
                output_scan=str(output_scan)
                #check if script script  list was able to got any info 
                scan_results_test="SMBv1"
                
                if scan_results_test in output_scan:
                    postgres_vulns(lists_ip,sites_results,"SMBv1",name,lists_Computer_name,lists_Domain,lists_OS,"",continent_results,conn)
                    print("SMBv1")
                scan_results_test="VULNERABLE"
                
                if scan_results_test in output_scan:
                    postgres_vulns(lists_ip,sites_results,"MS17-010",name,lists_Computer_name,lists_Domain,lists_OS,"",continent_results,conn)
                    print("VULNERABLE")

            #print("---------------------end scan --------------------------------")


#Function that converts MS time format (filetime) to standard datetime
def filetime_to_dt(ft):
    return datetime.utcfromtimestamp((ft - EPOCH_AS_FILETIME) / HUNDREDS_OF_NANOSECONDS)


adhosts = []
#Function to record ports to DB
def postgres_ports(ip_port,port,state,name,domain,service,details,conn):
    dt = datetime.now()
    cur=conn.cursor()
    cur.execute("select port,state,name,domain from Hosts_tcp where name = '{0}' AND domain ='{1}' AND port ='{2}' AND state = '{3}' ".format(name,domain,port,state))
    rows=cur.fetchall()
    if not rows:
        

    
        cur.execute("INSERT INTO Hosts_tcp(ip,port,state,name,domain,service,details,time_scan) VALUES('{0}','{1}','{2}','{3}','{4}','{5}','{6}','{7}')".format(ip_port,port,state,name,domain,service,details,dt))
        conn.commit()
    else:
        cur.execute("Update Hosts_tcp SET time_scan='{0}' where name = '{1}' AND domain ='{2}' AND port ='{3}' AND state = '{4}' ".format(dt,name,domain,port,state))
        conn.commit()

# DB with information taken from smb discovery script
def postgres_vuln(ip,site,vulnerable,name,netbios,domain,os,scan_error,continent,conn):
    cur=conn.cursor() 
    dt = datetime.now()
    cur.execute("SELECT time_scan,name from Hosts_vuln where name = '{0}' AND domain = '{1}' AND VULNERABLE = '{2}'".format(name,domain,vulnerable))
    rows=cur.fetchall()
    Null=None
    if not rows:
        cur.execute("INSERT INTO Hosts_vuln (IP,site,continent,VULNERABLE,name,netbios,domain,os,time_scan,scan_error,remediated , incident ) VALUES('{0}','{1}','{2}','{3}','{4}','{5}','{6}','{7}','{8}','{9}','{10}','{11}')".format(ip,site,continent,vulnerable,name,netbios,domain,os,dt,scan_error,None,None))
        conn.commit()
    else:
        cur.execute('UPDATE Hosts_vuln SET IP = %s ,site = %s  , continent = %s ,time_scan =%s  where name = %s AND domain = %s',(ip,site,continent,dt,name,domain))


#DB with information taken from other script like SMBv1 or MS17
def postgres_vulns(ip,site,vulnerable,name,netbios,domain,os,scan_error,continent,conn):
    cur=conn.cursor() 
    dt = datetime.now()
    #print("==========================================")
    #print("dodane")
    cur.execute("SELECT time_scan,name from Hosts_vulns where name = '{0}' AND domain = '{1}' AND VULNERABLE = '{2}'".format(name,domain,vulnerable))
    rows=cur.fetchall()
    Null=None
    if not rows:
        cur.execute("INSERT INTO Hosts_vulns (IP,site,continent,VULNERABLE,details,name,netbios,domain,os,time_scan,scan_error,remediated , incident ) VALUES('{0}','{1}','{2}','{3}','{4}','{5}','{6}','{7}','{8}','{9}','{10}','{11}','{12}')".format(ip,site,continent,vulnerable,None,name,netbios,domain,os,dt,scan_error,None,None))
        conn.commit()
    else:
        cur.execute('UPDATE Hosts_vulns SET IP = %s ,site = %s  , continent = %s ,time_scan =%s  where name = %s AND domain = %s',(ip,site,continent,dt,name,domain))



#function to checking if host has been scanned or scanns are old and need to be rescanned
def postgress(process_name,tasks,result_multi):
    results_ports="start"
 #adding task to process 
    print('[%s] evaluation routine starts' % process_name)
    while True:
        new_value = tasks.get()
        #print(type(new_value))
        if type(new_value) == int:
            print('[%s] evaluation routine quits' % process_name)
            result_multi.put(-1)
            logging.debug('[%s] evaluation routine quits' % process_name)

            break
        else:
            conn=psycopg2.connect(dbname='ldap', user='', password='' ,host = "127.0.0.1", port = "5432")

            cur = conn.cursor()
            lastlogontime=new_value[0]
            name=new_value[1]
            dnshostname=new_value[2]
            domain=new_value[3]
            cur.execute("SELECT time_scan,name from hosts where name = '{0}' AND domain = '{1}'".format(name,domain))
            rows=cur.fetchall()
            dt = datetime.now()
            Null=None
            port_range='1-49151' 

            if not rows:
                cur.execute('INSERT INTO Hosts (lastLogonTimestamp,ip,site,continent,name,DNS,domain,time_scan)    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',(lastlogontime,None,None,None,name,dnshostname,domain,None)) 
                conn.commit()
                results_ports="new"
                
                try:
                    nmap_scan(dnshostname,name,domain,conn,port_range) 
                except Exception as n:
                    logging.warning("nmap_scan error "+results_ports+" error: "+str(n)) 
               

            elif rows[0][0] is None:
                cur.execute('UPDATE Hosts SET lastLogonTimestamp = %s where name = %s AND domain = %s',(lastlogontime,name,domain))
                conn.commit()
                results_ports="scanned"

                try:
                    nmap_scan(dnshostname,name,domain,conn,port_range) 
                except Exception as n:
                    logging.warning("nmap_scan error "+results_ports+" error: "+str(n)) 
               
            else:
                print(rows[0][0])
                print(period)
                if (rows[0][0] < period2):
                        print("rescanned")
                        results_ports="rescaned"
                        cur.execute('UPDATE Hosts SET lastLogonTimestamp = %s where name = %s AND domain = %s',(lastlogontime,name,domain))
                        conn.commit()
                        port_range='139,445'
                        try:
                            nmap_scan(dnshostname,name,domain,conn,port_range) 
                        except Exception as n:
                            logging.warning("nmap_scan error "+results_ports+" error: "+str(n)) 

                       
                else:
                        cur.execute('UPDATE Hosts SET lastLogonTimestamp = %s where name = %s AND domain = %s',(lastlogontime,name,domain))
                        conn.commit()
                        results_ports="ignored"
    cur.close()
    conn.close()
    result_multi.put(results_ports)
    return
  #function to query LDAP   
def queryLDAP(user,passwd,domain):
        l = ldap.initialize("ldap://"+domain)
        l.protocol_version = ldap.VERSION3
        l.set_option(ldap.OPT_REFERRALS, 0)
        bind = l.simple_bind_s(user + "@" + domain, passwd)
        base = "dc=" + domain.split(".")[0] + ", dc=" + domain.split(".")[1] + ", dc=" + domain.split(".")[2]
        criteria = "(&(&(objectClass=computer)))"
        attributes = ['dNSHostName','Name', 'lastLogonTimestamp']
        result = l.search_s(base, ldap.SCOPE_SUBTREE, criteria, attributes)
        results = [entry for dn, entry in result if isinstance(entry, dict)]
        return results


flag=0
mypid=os.getpid()
#logging function 
logging.basicConfig(filename='/var/log/ldap_scanning.log',format='%(asctime)s %(message)s',level=logging.DEBUG)
#function to checking if script is not already running ( used when script is added to crontab)
for pid in psutil.pids():
    p = psutil.Process(pid)
    if (mypid == pid ):
        print("mypid")
    elif p.name() == "python3" and len(p.cmdline()) > 1 and "CHFLAPS.py" in p.cmdline()[1]:
        #print ("running")
        flag=1
count_sum=0
if (flag ==  0):
    #else:
    logging.debug("Script started") 

    try:

        conn=psycopg2.connect(dbname='ldap', user='', password='' ,host = "127.0.0.1", port = "5432")
        logging.debug("Postgresql connected") 
 
        
    except:
        #print "I am unable to connect to the database."
        logging.warning("Postgresql connection error") 
 

    if conn:
        conn.close()
        try:
            results2=queryLDAP(ADusers, ADpass, ADdomains)
            logging.debug("ldap import finished")
           
        except Exception as l:
            dt = datetime.now()
            dt_str=str(dt)
            logging.warning("ldap import failed: "+str(l))
        # Define IPC manager
        manager = multiprocessing.Manager()
        # Define a list (queue) for tasks and computation results
        tasks = manager.Queue()
        result_multi = manager.Queue()
        # Create process pool with four processes
        num_processes = 10
        pool = multiprocessing.Pool(processes=num_processes)
        processes = []
        for i in range(num_processes):
        # Set process name
            process_name = 'P%i' % i
            # Create the process, and connect it to the worker function
            new_process = multiprocessing.Process(target=postgress, args=(process_name,tasks,result_multi))
            # Add new process to the list of processes
            processes.append(new_process)
            # Start the process
            new_process.start()
            # Fill task queue

        


# listing hosts exported from ldap 
        for r in results2:
               
            try:
                y = int(r['lastLogonTimestamp'][0])
            except:
                y=0
            if (y != 0):
                ldap_name_results=r['name'][0]
                ldap_name_decoded=ldap_name_results.decode('utf-8')

                ptime = filetime_to_dt(y)
                try:
                    ldap_dns_results=r['dNSHostName'][0]
                    ldap_dns_decoded=ldap_dns_results.decode('utf-8')

                    dns=ldap_dns_decoded
                except:
                    dns=ldap_name_decoded+ADdomains
                try:
                    line=[ptime,ldap_name_decoded,dns,ADdomains]
                    #logging.debug("start task "+dns+" "+str(count_sum)+" from "+str(len(results2)))
#That function put hosts to waiting  postgress function in previusly opened process   ( with is checking if host need to be scanned )
                    tasks.put(line)
                    sleep(1)
                except Exception as e:
                    logging.warning("nmap scan failed "+dns+" error: "+str(e))    
                #logging.debug("end task "+dns+" "+str(count_sum)+" from+ "+str(len(results2)))

                
      #Closing all opened processes if array with hosts from LDAP ends
            count_sum += 1
        logging.debug("ldap list  finished,"+str(count_sum)) 

        for i in range(num_processes):
            tasks.put(-1)						
            # Read calculation results
        num_finished_processes = 0
        while True:
            sleep(1)
            new_result = result_multi.get()
            if new_result == -1:
                num_finished_processes += 1
                if num_finished_processes == num_processes:
                    break
                else:
                    # Output result
                    print('Result:' + str(new_result))

    
 
    count_sum_str=str(count_sum)
    logging.debug("script finished,"+count_sum_str) 



        


