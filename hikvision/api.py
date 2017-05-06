"""
hikvision.api
~~~~~~~~~~~~~~~~~~~~

Provides methods for interacting with hikvision IP cameras

Copyright (c) 2015 Finbarr Brady <https://github.com/fbradyirl>
Licensed under the MIT license.
"""

import logging
import requests
import re
from xml.etree import ElementTree
from hikvision.error import HikvisionError, MissingParamError
from hikvision.constants import DEFAULT_PORT, DEFAULT_HEADERS, XML_ENCODING
from hikvision.constants import DEFAULT_SENS_LEVEL
from hikvision.constants import STATUS_CODES
from requests.exceptions import ConnectionError as ReConnError
from requests.auth import HTTPBasicAuth

_LOGGING = logging.getLogger(__name__)

# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes


def build_url_base(host, port, is_https):
    """
    Make base of url based on config
    """
    base = "http"
    if is_https:
        base += 's'

    base += "://"
    base += host

    if port:
        base += ":"
        base += str(port)

    return base


def log_response_errors(response):
    """
    Logs problems in a response
    """

    _LOGGING.error("status_code %s", response.status_code)


def enable_logging():
    """ Setup the logging for home assistant. """
    logging.basicConfig(level=logging.DEBUG)


def remove_namespace(response):
    """ Removes namespace element from xml"""
    return re.sub(' xmlns="[^"]+"', '', response, count=1)


class CreateDevice(object):

    """
    Creates a new camera api device
    """

    def __init__(self, host=None, port=DEFAULT_PORT,
                 username=None, password=None, is_https=False,
                 sensitivity_level=DEFAULT_SENS_LEVEL):
        # enable_logging()
        _LOGGING.info("Initialising new hikvision camera client")

        if not host:
            _LOGGING.error('Missing hikvision host!')
            raise MissingParamError('Connection to hikvision failed.', None)

        self._username = username
        self._host = host
        self._password = password
        self._sensitivity_level = sensitivity_level
        self.xml_motion_detection_off = None
        self.xml_motion_detection_on = None
        self.timesettings = None
        self._responsecache = None

        # Now build base url
        self._base = build_url_base(host, port, is_https)

        # need to support different channel
        self.motion_url = '%s/MotionDetection/1' % self._base
        _LOGGING.info('motion_url: %s', self.motion_url)

        self._xml_namespace = "http://www.hikvision.com/ver10/XMLSchema"
        # Required to parse and change xml with the host camera
        _LOGGING.info(
            'ElementTree.register_namespace: %s', self._xml_namespace)
        ElementTree.register_namespace("", self._xml_namespace)

        try:
            _LOGGING.info("Going to probe device to test connection")
            # version = self.get_version()
            # enabled = self.is_motion_detection_enabled()
            _LOGGING.info("Connected OK!")
            # _LOGGING.info("Camera firmware version: %s", version)
            # _LOGGING.info("Motion Detection enabled: %s", enabled)

        except ReConnError as conn_err:
            # _LOGGING.exception("Unable to connect to %s", host)
            raise HikvisionError('Connection to hikvision failed.', conn_err)

    def get_version(self):
        """
        Returns the firmware version running on the camera
        """
        return self.get_about(element_to_query='firmwareVersion')
    
    #services:
        #system
        #network
        #IO
        #video
        #audio
        #two way audio
        #serial
        #security
        #streaming
        #motion detection
        #event
        #ptz
    #i care about:
        #system
        #network
        #video
        #security
        #ptz
        #maybe streaming
    def responsecached(self, path ):
        if self._responsecache[path]:
            return self._responsecache[path]
        else:
            return False

    def cacheresponse(self, path, response):
        self._responsecache[path] = response.text
        #tree = ElementTree.fromstring(xmltext)
    def dictset( self, d ):
        pass

    def set(self, identifier, value=None, **kwargs ):
        #trickier! Some stuff requires more xml around it
        #probably just implement it very naively for now, our needs aren't complicated

        #current imlementation through example
        #   identifier: "System/deviceInfo.deviceName"
        #   value:      "mikewuzhere"
        #
        #   will generate a path of "/System.deviceInfo"
        #   a root XML element of "deviceInfo"
        #   a sub element of "deviceName"
        #   and a value for deviceName of "mikewuzhere"
        #
        if "flags" in kwargs and "sendexact" in kwargs["flags"]:
            sendexact = True
        else:
            sendexact = False

        if "/" in identifier and "." in identifier:
            path, searchelements = identifier.split(".",1)
            elements = searchelements.split(".") #if identifier has more separators, split on them
        elif "/" in identifier:
            path = identifier
            searchelements = None
            elements = None
        else:
            pass #it's fine (reboot, for example, uses this)

        if path[0] != "/":
            path = "/" + path
        if elements and not sendexact:
            xmldata = ElementTree.Element( path.split("/")[-1] )
            last = ElementTree.SubElement(xmldata, elements[0]) #absolutely required to have something to set
            for e in elements[1:]: #and for any subidentifiers, generate the xmltags for it
                last = ElementTree.SubElement(xmldata, e)
            last.text = value #and set the value once we're at the correct identifier
            data = ElementTree.tostring(xmldata)
            _LOGGING.debug("Sending xml:\t", data)
        else:
            data = None
        
        if sendexact:
            data = value

        _LOGGING.debug("Sending data:\t", data)

        text = self.putrequest(path, data)
        if text is None:
            raise Exception("You messed up on setting something!")
        value = self.parse( text, "statusCode" )
        return int(value)


    def putrequest(self, path, data=None):
        url = self._base + path
        _LOGGING.info('url: %s', url)
        _LOGGING.info('data: %s', data)
        
        response = requests.put( url, data, auth=HTTPBasicAuth(self._username, self._password))

        _LOGGING.debug('response: %s', response)
        _LOGGING.debug("status_code %s", response.status_code)

        if response.status_code != 200:
            #TODO should raise an exception, and get and whatever should handle it
            log_response_errors(response)
            raise Exception(response.text)
        return response.text

    def get(self,identifier):
        #e.g. "System/deviceInfo.deviceName"
        if "." in identifier:
            path, searchelements = identifier.split(".",1)
            elements = searchelements.split(".")
            justreturntext = False
        else:
            path = identifier
            justreturntext = True

        if path[0] != "/":
            path = "/" + path

        text = self.getrequest(path)
        if text is None:
            raise Exception("You messed up!")
        if justreturntext:
            value = text
        else:
            value = self.parse( text, elements[0] )
        return value

    def getrequest(self, path ):
        url = self._base + path
        _LOGGING.info('url: %s', url)

        response = requests.get( url, auth=HTTPBasicAuth(self._username, self._password))

        _LOGGING.debug('response: %s', response)
        _LOGGING.debug("status_code %s", response.status_code)

        if response.status_code != 200:
            #TODO should raise an exception, and get and whatever should handle it
            log_response_errors(response)
            return None
        return response.text

    def parse(self,xmltext,element_to_query=None):
        if element_to_query is None:
            return response.text
        else:
            try:
                tree = ElementTree.fromstring(xmltext)

                element_to_query = './/{%s}%s' % ( self._xml_namespace, element_to_query)

                result = tree.findall(element_to_query)

                if len(result) > 0:
                    _LOGGING.debug('element_to_query: %s result: %s', element_to_query, result[0])
                    return result[0].text.strip()
                else:
                    _LOGGING.error( 'There was a problem finding element: %s', element_to_query)
                    _LOGGING.error('Entire response: %s', xmltext)

            except AttributeError as attrib_err:
                _LOGGING.error('Entire response: %s', xmltext)
                _LOGGING.error( 'There was a problem finding element: %s AttributeError: %s', 
                        element_to_query, attrib_err)
                return
            return

    def get_about(self, element_to_query=None):
        """
        Returns ElementTree containing the result of
        <host>/System/deviceInfo
        or if element_to_query is not None, the value of that element
        """

        url = '%s/System/deviceInfo' % self._base
        _LOGGING.info('url: %s', url)

        response = requests.get(
            url, auth=HTTPBasicAuth(self._username, self._password))

        _LOGGING.debug('response: %s', response)
        _LOGGING.debug("status_code %s", response.status_code)

        if response.status_code != 200:
            log_response_errors(response)
            return None

        if element_to_query is None:
            return response.text
        else:
            try:
                tree = ElementTree.fromstring(response.text)

                element_to_query = './/{%s}%s' % (
                    self._xml_namespace, element_to_query)
                result = tree.findall(element_to_query)
                if len(result) > 0:
                    _LOGGING.debug('element_to_query: %s result: %s',
                                   element_to_query, result[0])

                    return result[0].text.strip()
                else:
                    _LOGGING.error(
                        'There was a problem finding element: %s',
                        element_to_query)
                    _LOGGING.error('Entire response: %s', response.text)

            except AttributeError as attib_err:
                _LOGGING.error('Entire response: %s', response.text)
                _LOGGING.error(
                    'There was a problem finding element:'
                    ' %s AttributeError: %s', element_to_query, attib_err)
                return
        return
    def is_enabled(specifier):
        print("is_enabled is not implemented yet")
        print(specifier)

        return false

    def is_motion_detection_enabled(self):
        """ Get current state of Motion Detection """

        response = requests.get(self.motion_url, auth=HTTPBasicAuth(
            self._username, self._password))
        _LOGGING.debug('Response: %s', response.text)

        if response.status_code != 200:
            _LOGGING.error(
                "There was an error connecting to %s", self.motion_url)
            _LOGGING.error("status_code %s", response.status_code)
            return

        try:

            tree = ElementTree.fromstring(response.text)
            enabled_element = tree.findall(
                './/{%s}enabled' % self._xml_namespace)
            sensitivity_level_element = tree.findall(
                './/{%s}sensitivityLevel' % self._xml_namespace)
            if len(enabled_element) == 0:
                _LOGGING.error("Problem getting motion detection status")
                return
            if len(sensitivity_level_element) == 0:
                _LOGGING.error("Problem getting sensitivityLevel status")
                return

            result = enabled_element[0].text.strip()
            _LOGGING.info(
                'Current motion detection state? enabled: %s', result)

            if int(sensitivity_level_element[0].text) == 0:
                _LOGGING.warn(
                    "sensitivityLevel is 0.")
                sensitivity_level_element[0].text = str(
                    self._sensitivity_level)
                _LOGGING.info(
                    "sensitivityLevel now set to %s", self._sensitivity_level)

            if result == 'true':
                # Save this for future switch off
                self.xml_motion_detection_on = ElementTree.tostring(
                    tree, encoding=XML_ENCODING)
                enabled_element[0].text = 'false'
                self.xml_motion_detection_off = ElementTree.tostring(
                    tree, encoding=XML_ENCODING)
                return True
            else:
                # Save this for future switch on
                self.xml_motion_detection_off = ElementTree.tostring(
                    tree, encoding=XML_ENCODING)
                enabled_element[0].text = 'true'
                self.xml_motion_detection_on = ElementTree.tostring(
                    tree, encoding=XML_ENCODING)
                return False

        except AttributeError as attib_err:
            _LOGGING.error(
                'There was a problem parsing '
                'camera motion detection state: %s', attib_err)
            return

    def enable_motion_detection(self):
        """ Enable Motion Detection """

        self.put_motion_detection_xml(self.xml_motion_detection_on)

    def disable_motion_detection(self):
        """ Disable Motion Detection """

        self.put_motion_detection_xml(self.xml_motion_detection_off)

    def put_motion_detection_xml(self, xml):
        """ Put request with xml Motion Detection """

        _LOGGING.debug('xml:')
        _LOGGING.debug("%s", xml)

        headers = DEFAULT_HEADERS
        headers['Content-Length'] = len(xml)
        headers['Host'] = self._host
        response = requests.put(self.motion_url, auth=HTTPBasicAuth(
            self._username, self._password), data=xml, headers=headers)
        _LOGGING.debug('request.headers:')
        _LOGGING.debug('%s', response.request.headers)
        _LOGGING.debug('Response:')
        _LOGGING.debug('%s', response.text)

        if response.status_code != 200:
            _LOGGING.error(
                "There was an error connecting to %s", self.motion_url)
            _LOGGING.error("status_code %s", response.status_code)
            return

        try:
            tree = ElementTree.fromstring(response.text)
            enabled_element = tree.findall(
                './/{%s}statusString' % self._xml_namespace)
            if len(enabled_element) == 0:
                _LOGGING.error("Problem getting motion detection status")
                return

            if enabled_element[0].text.strip() == 'OK':
                _LOGGING.info('Updated successfully')

        except AttributeError as attib_err:
            _LOGGING.error(
                'There was a problem parsing the response: %s', attib_err)
            return
    def reboot(self):
        self.set("System/reboot",None)

    def getImageFlip(self,channel=1):
        c = self.get("Image/channels/" + str(channel) + "/ImageFlip")
        return c

    def setImageFlip(self,value=False,channel=1):
        """set imageFlip to False (disabled), "LEFTRIGHT", "UPDOWN", or "CENTER" """
        enabled = True if value and not value.lower() in ["false","0","f","disable","disabled"] else False
        enablestring = "true" if enabled else "false"
        xmlstr = "<ImageFlip>" + "<enabled>" + enablestring + "</enabled>"
        if enabled:
                xmlstr += "<ImageFlipStyle>"  + value + "</ImageFlipStyle>"

        xmlstr += "</ImageFlip>"
        c = self.set("Image/channels/" + str(channel) + "/ImageFlip", xmlstr,flags="sendexact")
        return c

    def setPTZAbs(self,elevation,azimuth,zoom,channel=1):
        #in tenths of a degree, so 90.0* == 900 input
        #elevation only accepts values between 0 and 900
        #azimuth will only accept values between 0 and 3600
        #zoom, i don't know. haven't tested at all
        #values past those limits get converted to the limit they are closest to, e.g. negatives to 0, elevation > 900 to 900

        xmlstr = "<PTZData><AbsoluteHigh>" +\
                "<elevation>" + str(elevation) + "</elevation>"+\
                "<azimuth>"  + str(azimuth) + "</azimuth>"+\
                "<absoluteZoom>" + str(zoom) + "</absoluteZoom>"+\
                "</AbsoluteHigh></PTZData>"
        c = self.set("ptzctrl/channels/" + str(channel) + "/absolute", xmlstr,flags="sendexact")
        return c

    def setDHCP(self):
        c = self.set("Network/interfaces/1/IPAddress.addressingType",
                "<IPAddress><ipVersion>v4</ipVersion><addressingType>dynamic</addressingType></IPAddress>",
                flags="sendexact")
        if c == 7:
            self.rebootneeded = True
            return True
        else:
            return

    def setNTP(self,ntp_server="0.north-america.pool.ntp.org",tz="EST-5:00:00"):
        c1 = self.set("System/time.timeMode",
                "<Time><timeMode>NTP</timeMode><timeZone>" + tz + "</timeZone></Time>",
                flags="sendexact")
        return c1

    def setNTPServer(self,id=1,ntp_server="10.250.249.1"):
        c1 = self.set("System/time/ntpServers/" + str(id) ,
                "<NTPServer><id>" + str(id) + "</id><addressingFormatType>ipaddress</addressingFormatType><ipAddress>" + ntp_server + "</ipAddress></NTPServer>", flags="sendexact")
        return c1

    def getNTPServer(self,id=1):
        c1 = self.get("System/time/ntpServers/" + str(id))
        return c1

    def setSSH(self, enable):
        """ not tested"""
        if enable:
            enablestr = "true"
        else:
            enablestr = "false"
        return self.set("ISAPI/System/Network/ssh.enabled",enablestr)

    def getSSH(self):
        """ not tested"""
        return self.get("ISAPI/System/Network/ssh")

    def setName(self,name):
        return self.set("System/deviceInfo.deviceName",name)

    def getPresets(self):
        #/PTZCtrl/channels/ <ID> /presets
        pass

    def addPreset(self):
        pass

    def setPreset(self,presetid):
        #/PTZCtrl/channels/ <ChannelID> /presets/ <PresetID>
        #if already exists (use getPresets)
            #then make new preset by posting to /presets
        pass

    def delPreset(self,presetid):
        pass

    def runPreset(self,presetid=1,channelid=1):
        # /PTZCtrl/channels/ <ChannelID> /presets/ <PresetID> /goto
        #PUT to that URL, no data to make it go to that preset
        return self.set("/PTZCtrl/channels/" + str(channelid) + "/presets/" + str(presetid) + "/goto")

    def delHomePosition(self):
        #DELETE to /PTZCtrl/channels/ <ChannelID> /homeposition
        pass

    def setHomePosition(self):
        #PUT to /PTZCtrl/channels/ <ChannelID> /homeposition, no data
        return self.put("/PTZCtrl/channels/" + str(channelid) + "/homeposition")

    def runHomePosition(self):
        #PUT to /PTZCtrl/channels/ <ChannelID> /homeposition/goto, no data
        return self.set("/PTZCtrl/channels/" + str(channelid) + "/homeposition/goto")

    def ptzRelative(self,posX,posY,relZ, channel=1):
        """Move the position (expressed in pixels, posX and posY) to the center of the image by pan and tilt, and set the relative zoom (-100:100)"""
        """untested"""
        xmlstr = "<PTZData><Relative>" +\
                "<positionX>" + str(posX) + "</positionX>"+\
                "<positionY>"  + str(posY) + "</positionY>"+\
                "<relativeZoom>" + str(relZ) + "</relativeZoom>"+\
                "</Relative></PTZData>"
        c = self.set("ptzctrl/channels/" + str(channel) + "/relative", xmlstr,flags="sendexact")
        return c

