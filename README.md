Introduction
============

This is a python module providing a basic python
interface to interact with a Hikvision IP Camera

This is licensed under the MIT license.

Getting started
===============

Make sure to see the [camera API guide](http://bit.ly/1RuyUuF)

Some example usage:

```python
>>> import hikvision.api
>>> cam = hikvision.api.CreateDevice( "10.250.250.208", username="admin", password="PASSWORDHERE")
>>> cam.get("System/time.timeMode")
'manual'
>>> cam.get("System/deviceInfo.deviceName")
'D03'
>>> cam.set("System/deviceInfo.deviceName","notD03")
1
>>> cam.get("System/deviceInfo.deviceName")
'notD03'
```



Requirements
------------

module requires:
 * requests>=2.0


Install
-------
```python
git clone --recursive git@github.com:mach327/hikvision.git
cd hikvision
# NOTE: You might need administrator privileges to install python modules.
pip install -r requirements.txt
pip install -e .
```

# Usage

Variables:

```python
import hikvision.api

# This will use http by default (not https)
hik_camera = hikvision.api.CreateDevice('192.168.2.5', username='admin', password='12345')
hik_camera.enable_motion_detection()
hik_camera.disable_motion_detection()
hik_camera.is_motion_detection_enabled()
```

host
*Required
This is the IP address of your Hikvision camera. Example: 192.168.1.32

username
*Required
Your Hikvision camera username

password
*Required
Your Hikvision camera username



TODO
------------
Add more functions

Developer
=========

Copyright (c) 2015-2016 Finbarr Brady, Mike McGinty
