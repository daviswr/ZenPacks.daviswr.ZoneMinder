# ZenPacks.daviswr.ZoneMinder

ZenPack to monitor the ZoneMinder daemon and monitors

## Requirements
* ZoneMinder 1.30.4 or newer
* ZoneMinder user with View access to most categories
  * Stream category not required
  * Events recommended but not required
    * Event-rate graphs will be empty
* [PythonCollector](https://help.zenoss.com/in/zenpack-catalog/open-source/pythoncollector) ZenPack
* [ZenPackLib](https://help.zenoss.com/in/zenpack-catalog/open-source/zenpacklib)

## zProperties
* `zZoneMinderUsername` - **required**
  * Username with which to authenticate to ZoneMinder
* `zZoneMinderPassword` - **required**
  * Password for the above user
* `zZoneMinderHostname`
  * Override ZoneMinder instance hostname
  * Device ID or Management IP if not set
* `zZoneMinderPort`
  * Override TCP port
  * Defaults to 443
* `zZoneMinderPath`
  * Override path component of URL
  * Defaults to `/zm/`
* `zZoneMinderSSL`
  * Override if HTTPS to be used
  * Defaults to True
* `zZoneMinderURL`
  * Override entire URL, bypasses zZoneMinderHostname/Port/Path/SSL
* `zZoneMinderIgnoreMonitorId`
  * List of numeric monitor IDs to ignore
* `zZoneMinderIgnoreMonitorName`
  * Regex of monitor names to ignore
* `zZoneMinderIgnoreMonitorHostname`
  * Regex of monitor hostnames or IPs to ignore
* `zZoneMinderIgnoreStorageId`
  * List of numeric storage volume IDs to ignore
* `zZoneMinderIgnoreStorageName`
  * Regex of storage volume names to ignore
* `zZoneMinderIgnoreStoragePath`
  * Regex of storage volume filesystem paths to ignore

## Usage
I'm not going to make any assumptions about your device class organization, so it's up to you to configure the `daviswr.python.ZoneMinder` modeler on the appropriate class or device.

## Special Thanks
* [JRansomed](https://github.com/JRansomed)
* [BaileyTJ](https://github.com/baileytj3)
