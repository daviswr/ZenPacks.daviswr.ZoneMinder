""" Models the ZoneMinder daemon """

import json
import re
import urllib

from twisted.internet.defer \
    import inlineCallbacks, returnValue
from twisted.web.client \
    import getPage

from Products.DataCollector.plugins.CollectorPlugin \
    import PythonPlugin
from Products.DataCollector.plugins.DataMaps \
    import MultiArgs, RelationshipMap, ObjectMap


class ZoneMinder(PythonPlugin):
    """ZoneMinder daemon modeler plugin"""

    requiredProperties = (
        'zZoneMinderUsername',
        'zZoneMinderPassword',
        'zZoneMinderHostname',
        'zZoneMinderPort',
        'zZoneMinderPath',
        'zZoneMinderSSL',
        'zZoneMinderURL',
        'zZoneMinderIgnoreMonitorId',
        'zZoneMinderIgnoreMonitorName',
        'zZoneMinderIgnoreMonitorHostname',
        )

    deviceProperties = PythonPlugin.deviceProperties + requiredProperties

    @inlineCallbacks
    def collect(self, device, log):
        """Asynchronously collect data from device. Return a deferred."""
        log.info("%s: collecting data", device.id)

        username = getattr(device, 'zZoneMinderUsername', None)
        password = getattr(device, 'zZoneMinderPassword', None)
        if not username or not password or len(username) == 0:
            log.error(
                '%s: zZoneMinderUsername or zZoneMinderPassword not set',
                device.id
                )
            returnValue(None)

        base_url = getattr(device, 'zZoneMinderURL', None)
        # If custom URL not provided, assemble one
        if not base_url:
            hostname = getattr(device, 'zZoneMinderHostname', '')
            if not hostname:
                hostname = device.id or device.manageIp
                if '.' not in hostname:
                    hostname = hostname.replace('_', '.')
            log.debug('%s: ZoneMinder host is %s', device.id, str(hostname))
            port = getattr(device, 'zZoneMinderPort', 443)
            path = getattr(device, 'zZoneMinderPath', '/zm/')
            if not path.startswith('/'):
                path = '/' + path
            if not path.endswith('/'):
                path = path + '/'
            protocol = 'https' \
                if getattr(device, 'zZoneMinderSSL', True) else 'http'
            base_url = '{0}://{1}:{2}{3}'.format(
                protocol,
                hostname,
                port,
                path
                )

        url_regex = r'^https?:\/\/\S+:?\d*\/?\S*\/$'
        if re.match(url_regex, base_url) is None:
            log.error('%s: %s is not a valid URL', device.id, base_url)
            returnValue(None)

        log.info('%s: using base ZoneMinder URL %s', device.id, base_url)
        # Pre-1.32 compatibility
        login_params = urllib.urlencode({
            'action': 'login',
            'view': 'postlogin',
            'username': username,
            'password': password,
            })
        login_url = '{0}index.php?{1}'.format(base_url, login_params)
        api_url = '{0}api/'.format(base_url)

        cookies = dict()
        # Attempt login
        try:
            response = yield getPage(login_url, method='POST', cookies=cookies)

            if 'Invalid username or password' in response:
                log.error(
                    '%s: ZoneMinder login credentials invalid',
                    device.id
                    )
                returnValue(None)
            elif len(cookies) == 0:
                log.error('%s: No cookies received', device.id)
                returnValue(None)

            log.debug('%s: ZoneMinder cookies\n%s', device.id, cookies)

            output = dict()
            output['url'] = base_url

            # Versions
            response = yield getPage(
                api_url + 'host/getVersion.json',
                method='GET',
                cookies=cookies
                )
            output.update(json.loads(response))

            # Config
            response = yield getPage(
                api_url + 'configs.json',
                method='GET',
                cookies=cookies
                )
            output.update(json.loads(response))

            # Monitors
            response = yield getPage(
                api_url + 'monitors.json',
                method='GET',
                cookies=cookies
                )
            output.update(json.loads(response))

            # Monitor PTZ Types
            response = yield getPage(
                api_url + 'controls.json',
                method='GET',
                cookies=cookies
                )
            output.update(json.loads(response))

            # Servers
            response = yield getPage(
                api_url + 'servers.json',
                method='GET',
                cookies=cookies
                )
            output.update(json.loads(response))

            # Log out
            yield getPage(
                base_url + 'index.php?action=logout',
                method='POST',
                cookies=cookies
                )

        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)

        returnValue(output)

    def process(self, device, results, log):
        """Process results. Return iterable of datamaps or None."""

        maps = list()

        # ZoneMinder daemon (getVersion.json & configs.json)
        daemon = dict()

        # Expecting results to be a dict
        for key in ['url', 'version', 'apiversion']:
            daemon[key] = results.get(key)

        for item in results.get('configs', list()):
            config = item['Config']
            key = config['Name'].title().replace('_', '')
            value = config['Value']
            daemon[key] = value

        booleans = ['ZmOptControl', 'ZmOptFfmpeg', 'ZmOptFrameServer']
        for key in booleans:
            if key in daemon:
                daemon[key] = True if daemon[key] == '1' else False

        daemon['title'] = 'ZoneMinder'
        daemon['id'] = self.prepId(daemon['title'])

        rm = RelationshipMap(
            relname='zoneMinder',
            modname='ZenPacks.daviswr.ZoneMinder.ZoneMinder'
            )
        rm.append(ObjectMap(
            modname='ZenPacks.daviswr.ZoneMinder.ZoneMinder',
            data=daemon
            ))
        log.debug('%s ZoneMinder daemon:\n%s', device.id, rm)
        maps.append(rm)

        # Monitors
        rm = RelationshipMap(
            compname='zoneMinder/ZoneMinder',
            relname='zmMonitors',
            modname='ZenPacks.daviswr.ZoneMinder.ZMMonitor'
            )

        ptz = dict()
        for item in results.get('controls', list()):
            control = item['Control']
            key = control['Id']
            value = '{0} {1}'.format(control['Name'], control['Type'])
            ptz[key] = value

        ignore_ids = getattr(device, 'zZoneMinderIgnoreMonitorId', list())
        ignore_names = getattr(device, 'zZoneMinderIgnoreMonitorName', '')
        ignore_host = getattr(device, 'zZoneMinderIgnoreMonitorHostname', '')

        for item in results.get('monitors', list()):
            monitor = item['Monitor']
            monitor_id = monitor.get('Id') \
                or (int(monitor.get('Sequence')) + 1)
            monitor_name = monitor.get('Name') or monitor_id
            monitor['id'] = self.prepId('zmMonitor{0}'.format(monitor_id))
            monitor['title'] = monitor_name

            ignore_match = re.search(ignore_names, monitor_name)

            if ignore_ids and monitor_id in ignore_ids:
                log.info(
                    '%s: Skipping monitor %s in zZoneMinderIgnoreMonitorId',
                    device.id,
                    monitor_id
                    )
                continue
            elif ignore_names and ignore_match:
                log.info(
                    '%s: Skipping %s in zZoneMinderIgnoreMonitorName',
                    device.id,
                    monitor_name
                    )
                continue

            # We may or may not have a hostname/IP, port, protocol,
            # path, or full URL. Some of these may have passwords.
            full_url_regex = r'([A-Za-z]+):\/\/([^/]+)(\/.*)'
            path = monitor.get('Path', '')
            path_url_match = re.match(full_url_regex, path)
            if path_url_match:
                # Path attribute is a full URL with protocol, host, and port
                # so it's more believable than the individual attributes
                log.debug('%s: Path is full URL: %s', device.id, path)
                protocol = path_url_match.groups()[0]
                host_string = path_url_match.groups()[1]
                url_path = path_url_match.groups()[2]
            else:
                log.debug('%s: Path is NOT a full URL: %s', device.id, path)
                protocol = monitor.get('Protocol', '')
                host_string = monitor.get('Host', '')
                url_path = monitor.get('Path', '')

            if '@' in host_string:
                log.debug(
                    '%s: Credentials found in host: %s',
                    device.id,
                    host_string
                    )
                (credentials, host_string) = host_string.split('@')
                url_path = url_path.replace(credentials + '@', '')
                path = path.replace(credentials + '@', '')

            if ':' in host_string:
                log.debug('%s: Port found in host: %s', device.id, host_string)
                (host, port) = host_string.split(':')
            else:
                host = host_string
                port = monitor.get('Port', '')

            protocol_port = {
                'http': '80',
                'https': '443',
                'rtsp': '554',
                }

            # Invert the dictionary
            port_protocol = dict(map(reversed, protocol_port.items()))

            if not path_url_match:
                path = '{0}://{1}:{2}{3}'.format(
                    protocol,
                    host,
                    port,
                    url_path
                    )
                log.debug('%s: Assembled URL %s', device.id, path)

                if port:
                    if (not protocol
                            or protocol != port_protocol.get(port, protocol)):
                        protocol = port_protocol.get(port, protocol)
                        log.debug(
                            '%s: Fixing protocol: %s',
                            device.id,
                            protocol
                            )
                elif protocol:
                    port = protocol_port.get(protocol, port)
                    log.debug('%s: Fixing port: %s', device.id, port)

            # Getting protocol from the full URL path
            elif port != protocol_port.get(protocol, port):
                port = protocol_port.get(protocol, port)

            url_password_regex = r'(\S+)passw?o?r?d?=[^_&?]+[_&?](\S+)'
            url_password_match = re.match(url_password_regex, path)
            if url_password_match:
                log.debug('%s: Remove password from URL %s', device.id, path)
                path = '{0}{1}'.format(
                    url_password_match.groups()[0],
                    url_password_match.groups()[1]
                    )

            monitor['Path'] = path
            monitor['Host'] = host
            monitor['Port'] = port
            monitor['Protocol'] = protocol.upper()

            ignore_match = re.search(ignore_host, host)
            if ignore_host and ignore_match:
                log.info(
                    '%s: Skipping %s in zZoneMinderIgnoreMonitorHostname',
                    device.id,
                    host
                    )
                continue

            monitor['MonitorType'] = monitor.get('Type')
            if 'Ffmpeg' == monitor['MonitorType']:
                monitor['MonitorType'] = 'FFmpeg'

            integers = [
                'ServerId',
                'Port',
                'Width',
                'Height',
                ]

            for key in integers:
                value = monitor.get(key, 0)
                if isinstance(value, int) or isinstance(value, str):
                    monitor[key] = int(monitor.get(key, 0))
                else:
                    monitor[key] = 0

            color_map = {
                '1': '8-bit grayscale',
                '2': '24-bit color',
                '3': '32-bit color',
                '4': '32-bit color',
                }

            monitor['Color'] = color_map.get(
                monitor.get('Colours', 0),
                'Unknown'
                )

            if monitor['Width'] > 0 and monitor['Height'] > 0:
                monitor['Resolution'] = '{0}x{1}'.format(
                    monitor['Width'],
                    monitor['Height']
                    )
            else:
                monitor['Resolution'] = ''

            floats = [
                'AnalysisFPS',
                'MaxFPS',
                'AlarmMaxFPS',
                ]

            for key in floats:
                monitor[key] = float(monitor.get(key, 0.0))

            booleans = [
                'Enabled',
                'Controllable',
                ]

            for key in booleans:
                monitor[key] = True if monitor.get(key, '0') == '1' else False

            if (monitor['Controllable']
                    and monitor.get('ControlId', '0') != '0'):
                monitor['ControlId'] = ptz.get(monitor['ControlId'])
            else:
                monitor['ControlId'] = 'None'

            rm.append(ObjectMap(
                modname='ZenPacks.daviswr.ZoneMinder.ZMMonitor',
                data=monitor
                ))
            log.debug('%s ZoneMinder monitor:\n%s', device.id, rm)
        maps.append(rm)

        return maps
