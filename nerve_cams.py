#!/usr/bin/env python

import hikvision.api
import nmap
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

import sys
import os
import json
import xml.etree.ElementTree as ET

#There's a 32 degree clockwise rotation from north, from cameras point of view looking down when mounted normally
# So to get a "0 0 0" PTZ centered on the "front" where the tab is, pan to 3020 (302+32-90), plus a tenth degree precision less the decimal point


class NERVECams:
    def __init__(self,user,pw,net):
        self.user = user
        self.pw = pw
        self.net = net
        self.cams = []
        self.camobjs = {}

    #def provision(self):
        #nm = nmap.PortScanner()
        #nm.scan(hosts="192.168.1.64", arguments="-sP")
        #hosts_list = [(x, nm[x]['status']['state']) for x in nm.all_hosts()]
        #for host, status in hosts_list:
            #if status == "up" and is_hikvision_camera(host):
                #newcam = hikvision.api.CreateDevice( host, username=self.user, password=self.pw)

    def scanhosts(self,findcams=True):
        self.nm = nmap.PortScanner()
        self.nm.scan(hosts=self.net, arguments="-sP")
        if findcams:
            self.findcams()

    def findcams(self):
        hosts_list = [(x, self.nm[x]['status']['state']) for x in self.nm.all_hosts()]
        for host, status in hosts_list:
            if status == "up" and is_hikvision_camera(host):
                self.addcam(host)

        return self.cams
    def addnet(self,netstring):
        pass

    def addcam(self,host):
        """provide an IP or hostname to a camera you want to add"""
        self.cams.append(host)

    #def setname(self,host):
        #name = input('Enter hostname for ' + host + ": ")
        #cam = self.camobjs[ host ]
        #cam.set("System/deviceInfo.deviceName", name)
        #print("deviceName is now ", cam.get("System/deviceInfo.deviceName") )

    def inventory(self,csv=True):
        for host in self.camobjs:
            cam = self.camobjs[host]
            name= cam.get("System/deviceInfo.deviceName")
            mac = cam.get("System/deviceInfo.macAddress")
            serial = cam.get("System/deviceInfo.serialNumber")
            model = cam.get("System/deviceInfo.model")
            if csv:
                print(",".join([name,mac,serial,model]))
            else:
                print(host + "\t" +name)
                print("\t" + mac)
                # print("\t" + serial)
                # print("\t" + model)

    def setdefaults(self):
        for host in self.camobjs:
            cam = self.camobjs[host]
            if cam.get("System/time.timeMode") != "NTP":
                print("setting ntp")
                print(cam.setNTP())
            if cam.get("Network/interfaces/1/ipAddress.addressingType") != "dynamic":
                print("setting dhcp")
                print(cam.setDHCP())
                #print("rebooting for dhcp")
                #cam.reboot()

    def connectcams(self):
        for host in self.cams:
            self.camobjs[ host ] = hikvision.api.CreateDevice( host, username=self.user, password=self.pw)

    def flipimage(self,host,style):
        cam = self.camobjs[ host ]
        cam.setImageFlip(style)

    def verifyprofiles(self, profile):
        #see setprofile() for what a profile should look like

        pass
    def setprofile(self, profile):
        #profile should be a dict where 
        #   the key is the identifier to set, 
        #   and the value is, well, the value 
        for k,v in profile.items():
            print(k,v)

    def hostcb(self, host, scan_result):
        if scan_result['scan'] != {}:
            sys.stdout.write("^")
        else:
            sys.stdout.write("-")

class NERVEConfig:
    def open_spreadsheet(self, spreadsheet):
        try:
            self.wks = self.gc.open_by_key(spreadsheet).sheet1
        except:
            pass
        try:
            if not self.wks:
                self.wks = self.gc.open_by_url(spreadsheet).sheet1
        except:
            pass
        try:
            if not self.wks:
                self.wks = self.gc.open(spreadsheet).sheet1
        except:
            raise( Exception("Could not find spreadsheet by name, key, or url."))
        return self.wks

    def __init__(self, credfile, spreadsheet, nvr):
        #https://github.com/burnash/gspread
        self.credfile = credfile
        self.spreadsheet = spreadsheet
        self.nvr = nvr

        scope = ['https://spreadsheets.google.com/feeds']
        self.credentials = ServiceAccountCredentials.from_json_keyfile_name(credfile, scope)
        self.gc = gspread.authorize( self.credentials )

        self.wks = None
        self.open_spreadsheet( spreadsheet )
        self.parse_configs()
    
    def parse_configs(self):
        taskrunset_row = self.wks.find("TaskAndRunSet").row
        alltaskrun_rowvalues = self.wks.row_values( taskrunset_row )
        self.config_row = self.wks.find("Config_1").row
        self.configtasks = {}
        for i in range(len(alltaskrun_rowvalues)):
            val = alltaskrun_rowvalues[ i ]
            try:
                ctaskset = TRParse( val )
                self.configtasks[ i+1 ] = ctaskset
                # configtasks key is the column id for that task set
                # value in that dict is the task set dict for that config, where a task num is a key,
                # which has an array for a value representing the run numbers
            except:
                pass
    def set_taskrun(self,trstring):
        cams = self.get_by_taskrun(trstring)
        xmlstr = self.generate_eventtrigger_xml()
        self.nvr.putrequest("/ISAPI/Event/triggers/IO-1",xmlstr)
        self.verify_taskrun(trstring)

    def verify_taskrun(self,trstring):
        valid = True
        fetched_xml = self.nvr.get("/ISAPI/Event/triggers/IO-1")
        tree = ET.ElementTree( ET.fromstring( fetched_xml ) )
        namespace = tree.getroot().tag[1:].split("}")[0] #http://stackoverflow.com/questions/1319385/need-help-using-xpath-in-elementtree
        root = tree.getroot()
        setcams = []
        for x in root.findall('.//{%s}dynVideoInputID' % namespace):
            setcams.append(x.text.zfill(2))

        cams = self.get_by_taskrun(trstring)
        for c in cams:
            if c not in setcams:
                valid = False
                print("D%s is not set!" % c)
        for c in setcams:
            if c not in cams:
                print("D%s may be extraneous" %c)
        if valid:
            print(setcams,cams)

        return valid


    def get_by_taskrun(self,trstring):
        tr = TRParse(trstring)
        config = self.find_config_from_taskrun( tr )
        return self.get_by_config( config )

    def tr_in_trset(self, tr, trset ):
        findt,findr = list(tr.items())[0]
        findr = findr[0]
        for t,r in trset.items():
            if t == findt and findr in r:
                return True

        return False

    def find_config_from_taskrun(self, tr):
        found = False
        config_cell = None
        for configcellcol, trset in self.configtasks.items():
            if self.tr_in_trset( tr, trset ):
                config_cell = self.wks.cell( self.config_row, configcellcol )
                found = True
                break
        if not found:
            raise( Exception("Configuration not found for given Task and Run"))

        return config_cell.value

    def get_start_and_end_aisles(self):
        start_row = self.wks.find("StartAisle").row
        end_row = self.wks.find("EndAisle").row
        start_aisle = self.wks.cell(start_row, config_col).value
        end_aisle = self.wks.cell(end_row, config_col ).value
        return ( start_aisle, end_aisle )

    def get_by_config(self, configname):
        config_cell = self.wks.find(configname)
        config_col = config_cell.col
        config = self.wks.col_values(config_col)

        camcol_cell = self.wks.find("Camera")
        camcol = camcol_cell.col
        camnames = self.wks.col_values(camcol)
        self.cams = []
        for x in range(self.config_row,len(config)):
            if not camnames[x]:
                break
            if camnames[x] and config[x]:
                self.cams.append( camnames[x] )
        # for c in self.cams:
            # print(c)
        return self.cams

    def generate_eventtrigger_xml(self):
        xmlstr = """
        <EventTrigger>
            <id>IO-1</id>
            <eventType>IO</eventType>
            <inputIOPortID>1</inputIOPortID>
            <EventTriggerNotificationList>
            """
        for c in self.cams:
            xmlstr += """
            <EventTriggerNotification>
                <id>record-%s</id>
                <notificationMethod>record</notificationMethod>
                <dynVideoInputID>%s</dynVideoInputID>
            </EventTriggerNotification>
            """ % (c,c)
        xmlstr += "</EventTriggerNotificationList></EventTrigger>"
        return xmlstr



def TRParse(trstring):
    rawtasks = trstring.split(",")
    tasks = {}
    for t in rawtasks:
        runs = parseRange("1-10")
        try:
            task, runs = t.split(".")
        except:
            task = t
        task = int(task)
        if isinstance(runs, str):
            runs = parseRange( runs )
        if not task in tasks:
            tasks[ task ] = []
        for run in runs:
            tasks[ task ].append( run)
    return tasks

def parseRange(rangestring):
    try:
        start, end = rangestring.split("-")
        return list( range( int( start ), int( end ) + 1 ) )
    except:
        return [ int(rangestring) ]


def is_hikvision_camera(ip):
    try:
        r = requests.get("http://" + ip + "/System/status")
        if r.status_code == 401:
            return True
        else:
            return False
    except requests.exceptions.RequestException as e:
        print(e)
        return False

def printhelp():
    print("./nerve_cams.py")
    print("\twill scan for and connect to all found hikvision cameras in 10.250.249.0/24")
    print("./nerve_cams.py 192.168.1.0/24")
    print("\tor do the same to the specified network (passed to nmap, all nmap syntax valid)")
    print("\t both then print an inventory and set some default options.")
    print("\nor you can set an individual camera's settings:")
    print("./nerve_cams.py 10.250.249.101 flip center")
    print("./nerve_cams.py 10.250.249.101 name D01")
    print("./nerve_cams.py 10.250.249.101 reboot")
    print("./nerve_cams.py 10.250.249.101 dhcp")
    print("./nerve_cams.py 10.250.249.101 ntp")

if __name__ == "__main__":
    configfile = "config.json"
    with open(configfile) as fp:
        config = json.load(fp)
    user = config['user']
    pw = config['pw']
    net = config['net']
    nerve = NERVECams(user,pw,net)

    if len(sys.argv) <= 1:
        nerve.scanhosts()
        print(nerve.cams)
        nerve.connectcams()
        nerve.inventory()
        nerve.setdefaults()
    else:
        try:
            host = sys.argv[1]
            action = sys.argv[2].lower()
            args = sys.argv[3:]
            if host == "net":
                nerve.scanhosts()
                nerve.connectcams()
                cams = nerve.camobjs
            elif host == "nvr" or host == "hiknvr":
                #nocams, just "hiknvr" or it's IP
                nvr = hikvision.api.CreateDevice( host, username=nerve.user, password=nerve.pw)
                credfile = config['google_oauth_creds_file']
                spreadsheet = config['google_cams_spreadsheet']
            else:
                cam = hikvision.api.CreateDevice( host, username=nerve.user, password=nerve.pw)
                cams = {}
                cams[host] = cam
            if "flip" in action:
                try:
                    style = args[0]
                    for ip,cam in cams.items():
                        print(cam.getImageFlip())
                        c = cam.setImageFlip( style.upper() )
                        print(c, cam.getImageFlip())
                except Exception as e:
                    print(e)
                    print("flip False,LEFTRIGHT, UPDOWN, CENTER")
            elif 'aptz' in action:
                p,t,z = args
                print(p,t,z)
                for ip,cam in cams.items():
                    cam.setPTZAbs(t,p,z)
            elif 'profile' in action:
                profilename = args[0]
                with open(profilename) as f:
                    profiledata = json.load(f)
                nerve.setprofile(profiledata)

            elif 'verify-taskrun' in action:
                taskrun = args[0]
                nrv = NERVEConfig( credfile, spreadsheet, nvr )
                nrv.verify_taskrun( taskrun )
            elif 'loop-verify-taskrun' in action:
                taskrun = args[0]
                sleep = args[1]
                nrv = NERVEConfig( credfile, spreadsheet, nvr )
                while True:
                    nrv.verify_taskrun( taskrun )
                    time.sleep(int(sleep))


            elif 'taskrun' in action:
                taskrun = args[0]
                nrv = NERVEConfig( credfile, spreadsheet, nvr )
                nrv.set_taskrun( taskrun )

            elif 'camconfig' in action:
                taskrun = args[0]
                nrv = NERVEConfig( credfile, spreadsheet, nvr )
                nrv.get_by_taskrun( taskrun )
                

            elif 'preset' in action:
                presetid = args[0]
                for ip,cam in cams.items():
                    cam.runPreset(presetid)
            elif "name" in action:
                name = args[0]
                cam.setName(name)
            elif "reboot" in action:
                for ip,cam in cams.items():
                    cam.reboot()
            elif "ntp" in action:
                for ip,cam in cams.items():
                    print(cam.setNTP())
                    print(cam.getNTPServer())
                    print(cam.setNTPServer(1,config['ntp_server']))
                    print(cam.getNTPServer())
            elif "dhcp" in action:
                for ip,cam in cams.items():
                    print(cam.setDHCP())
            elif "sendxml" in action:
                pass
            elif 'trparsetest' in action:
                TRParse("8.3-5,9.3-5,11.1-2,1,1.6,8.2")
            else:
                print("action " + action + " not supported")
        except IndexError as e:
            print(e)
            printhelp()


