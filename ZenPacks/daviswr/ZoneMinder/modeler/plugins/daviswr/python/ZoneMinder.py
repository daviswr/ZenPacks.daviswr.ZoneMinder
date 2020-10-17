""" Models the ZoneMinder daemon """

import json
import re
import urllib

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import getPage

from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import (
    MultiArgs,
    RelationshipMap,
    ObjectMap
    )

from ZenPacks.daviswr.ZoneMinder.lib import zmUtil


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
        'zZoneMinderIgnoreStorageId',
        'zZoneMinderIgnoreStorageName',
        'zZoneMinderIgnoreStoragePath',
        )

    deviceProperties = PythonPlugin.deviceProperties + requiredProperties

    @inlineCallbacks
    def collect(self, device, log):
        """Asynchronously collect data from device. Return a deferred."""
        log.info("%s: collecting data", device.id)

        username = getattr(device, 'zZoneMinderUsername', None)
        password = getattr(device, 'zZoneMinderPassword', None)
        if not username or not password:
            log.error(
                '%s: zZoneMinderUsername or zZoneMinderPassword not set',
                device.id
                )
            returnValue(None)

        base_url = zmUtil.generate_zm_url(
            hostname=(getattr(device, 'zZoneMinderHostname', None)
                      or device.id
                      or device.manageIp
                      ),
            port=getattr(device, 'zZoneMinderPort', 443),
            path=getattr(device, 'zZoneMinderPath', '/zm/'),
            ssl=getattr(device, 'zZoneMinderSSL', True),
            url=getattr(device, 'zZoneMinderURL', None)
            )

        if re.match(zmUtil.url_regex, base_url) is None:
            log.error('%s: %s is not a valid URL', device.id, base_url)
            returnValue(None)

        log.info('%s: using base ZoneMinder URL %s', device.id, base_url)
        # Pre-1.32 compatibility
        login_params = urllib.urlencode({
            'action': 'login',
            'view': 'login',
            'username': username,
            'password': password,
            # 1.34+ requires OPT_USE_LEGACY_API_AUTH
            'stateful': 1,
            })
        login_url = '{0}index.php?{1}'.format(base_url, login_params)
        api_url = '{0}api/'.format(base_url)
        # log.debug('%s: ZoneMinder URL:%s', device.id, login_url)

        cookies = dict()
        try:
            # Attempt login
            response = yield getPage(login_url, method='POST', cookies=cookies)

            if 'Invalid username or password' in response:
                log.error(
                    '%s: ZoneMinder login credentials invalid',
                    device.id
                    )
                returnValue(None)
            elif not cookies:
                log.error('%s: No cookies received', device.id)
                returnValue(None)

            log.debug('%s: ZoneMinder cookies\n%s', device.id, cookies)

            output = dict()
            output['url'] = base_url

            # Versions
            log.debug('%s: ZoneMinder URL: host/getVersion.json', device.id)
            response = yield getPage(
                api_url + 'host/getVersion.json',
                method='GET',
                cookies=cookies
                )
            version_json = json.loads(response)
            versions = zmUtil.dissect_versions(version_json)
            output.update(version_json)

            # Config
            log.debug('%s: ZoneMinder URL: configs.json', device.id)
            response = yield getPage(
                api_url + 'configs.json',
                method='GET',
                cookies=cookies
                )
            output.update(json.loads(response))

            # Monitors
            log.debug('%s: ZoneMinder URL: monitors.json', device.id)
            response = yield getPage(
                api_url + 'monitors.json',
                method='GET',
                cookies=cookies
                )
            output.update(json.loads(response))

            # Monitor PTZ Types
            log.debug('%s: ZoneMinder URL: controls.json', device.id)
            response = yield getPage(
                api_url + 'controls.json',
                method='GET',
                cookies=cookies
                )
            output.update(json.loads(response))

            # Storage Volumes
            log.debug('%s: ZoneMinder URL: index.php?view=console', device.id)
            response = yield getPage(
                '{0}index.php?view=console'.format(base_url),
                method='GET',
                cookies=cookies
                )
            output['volumes'] = zmUtil.scrape_console_volumes(response)

            # Servers
            # response = yield getPage(
            #     api_url + 'servers.json',
            #     method='GET',
            #     cookies=cookies
            #     )
            # output.update(json.loads(response))

            # Version-specific API calls
            # 1.32+ required for storage.json
            if (versions['daemon']['major'] >= 1
                    and versions['daemon']['minor'] >= 32):
                # Storage
                log.debug('%s: ZoneMinder URL: storage.json', device.id)
                response = yield getPage(
                    api_url + 'storage.json',
                    method='GET',
                    cookies=cookies
                    )
                output.update(json.loads(response))

                # API logout
                log.debug('%s: ZoneMinder URL: host/logout.json', device.id)
                yield getPage(
                    api_url + 'host/logout.json',
                    method='GET',
                    cookies=cookies
                    )

            else:
                # Browser-style log out
                # Doesn't work with 1.34.21
                log.debug(
                    '%s: ZoneMinder URL: index.php?action=logout',
                    device.id
                    )
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

        booleans = ['ZmOptControl', 'ZmOptFfmpeg', 'ZmOptUseEventnotification']
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

            if ignore_ids and monitor_id in ignore_ids:
                log.info(
                    '%s: Skipping monitor %s in zZoneMinderIgnoreMonitorId',
                    device.id,
                    monitor_id
                    )
                continue
            elif ignore_names and re.search(ignore_names, monitor_name):
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
                value = monitor.get(key, None)
                monitor[key] = int(value) if value else 0

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
                'MaxFPS',
                'AlarmMaxFPS',
                ]

            for key in floats:
                monitor[key] = float(monitor.get(key, 0.0)) \
                    if monitor.get(key, None) \
                    else 0.0

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

        # Storage Volumes
        rm = RelationshipMap(
            compname='zoneMinder/ZoneMinder',
            relname='zmStorage',
            modname='ZenPacks.daviswr.ZoneMinder.ZMStorage'
            )
        ignore_ids = getattr(device, 'zZoneMinderIgnoreStorageId', list())
        ignore_names = getattr(device, 'zZoneMinderIgnoreStorageName', '')
        ignore_paths = getattr(device, 'zZoneMinderIgnoreStoragePath', '')

        volumes = results.get('volumes', dict())

        # Combine storage info from API with that scraped from Console
        for item in results.get('storage', list()):
            store = item['Storage']
            if store['Name'] in volumes:
                volumes[store['Name']].update(store)

        for store_name in volumes:
            store = volumes[store_name]
            store_id = store.get('Id')
            store_path = store.get('Path')
            store['id'] = self.prepId('zmStorage_{0}'.format(store_name))
            store['title'] = store_name

            if ignore_ids and store_id in ignore_ids:
                log.info(
                    '%s: Skipping storage %s in zZoneMinderIgnoreStorageId',
                    device.id,
                    store_id
                    )
                continue
            elif ignore_names and re.search(ignore_names, store_name):
                log.info(
                    '%s: Skipping %s in zZoneMinderIgnoreStorageName',
                    device.id,
                    monitor_name
                    )
                continue
            elif ignore_paths and re.search(ignore_paths, store_path):
                log.info(
                    '%s: Skipping %s in zZoneMinderIgnoreStoragePath',
                    device.id,
                    monitor_name
                    )
                continue

            if 'total' in store:
                store['DiskSpace'] = store['total']

            store['StorageType'] = store.get('Type', None)

            rm.append(ObjectMap(
                modname='ZenPacks.daviswr.ZoneMinder.ZMStorage',
                data=store
                ))
            log.debug('%s ZoneMinder storage:\n%s', device.id, rm)
        maps.append(rm)

        return maps
