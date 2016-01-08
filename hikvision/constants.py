"""
hikvision.constants
~~~~~~~~~~~~~~~~~~~~

List of constants

Copyright (c) 2015 Finbarr Brady <https://github.com/fbradyirl>
Licensed under the MIT license.
"""

DEFAULT_PORT = None
XML_ENCODING = 'UTF-8'

# Motion Detection
# 1 = 20%
# 4 = 80%
DEFAULT_SENS_LEVEL = 1

DEFAULT_HEADERS = {
    'Content-Type': "application/xml; charset='UTF-8'",
    'Accept': "*/*"
}
STATUS_CODES = {
        1:"OK",
        2:"Busy",
        3:"DeviceError",
        4:"InvalidOperation",
        5:"InvalidXMLFormat",
        6:"InvalidXMLContent",
        7:"RebootRequired"
}
