""" Models the ZoneMinder daemon """

# stdlib Imports
import json
import re
import urllib

# Twisted Imports
from twisted.internet.defer \
    import inlineCallbacks, returnValue
from twisted.web.client \
    import getPage

# Zenoss Imports
from Products.DataCollector.plugins.CollectorPlugin \
    import PythonPlugin


class ZoneMinder(PythonPlugin):
    """ZoneMinder daemon modeler plugin"""

    relname = 'zoneMinder'
    modname = 'ZenPacks.daviswr.ZoneMinder.ZoneMinder'

    requiredProperties = (
        'zZoneMinderUsername',
        'zZoneMinderPassword',
        'zZoneMinderHostname',
        'zZoneMinderPort',
        'zZoneMinderPath',
        'zZoneMinderSSL',
        'zZoneMinderURL',
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
                hostname = device.id.replace('_', '.') or device.manageIp
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
        api_url = b'{0}api/'.format(base_url)
        # Pre-1.32 compatibility
        login_params = urllib.urlencode({
            'action': 'login',
            'view': 'postlogin',
            'username': username,
            'password': password,
            })
        login_url = b'{0}index.php?{1}'.format(base_url, login_params)
        log.debug('%s: ZoneMinder login URL %s', device.id, login_url)

        cookies = dict()
        # Attempt login
        try:
            response = yield getPage(login_url, method='POST', cookies=cookies)
        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)

        if 'Invalid username or password' in response:
            log.error(
                '%s: ZoneMinder login credentials invalid',
                device.id
                )
            returnValue(None)

        log.debug('%s: ZoneMinder cookies\n%s', device.id, cookies)

        output = dict()
        output['url'] = base_url
        # Get versions
        try:
            response = yield getPage(
                api_url + 'host/getVersion.json',
                method='GET',
                cookies=cookies
                )
            output['versions'] = json.loads(response)
        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)

        # Get config
        try:
            response = yield getPage(
                api_url + 'configs.json',
                method='GET',
                cookies=cookies
                )
            output['config'] = json.loads(response)
        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)

        returnValue(output)

    def process(self, device, results, log):
        """Process results. Return iterable of datamaps or None."""

        data = dict()
        # Expecting results to be a dict
        if 'versions' in results:
            for key in results['versions']:
                data[key] = results['versions'][key]

        if 'config' in results:
            for param in results['config']['configs']:
                key = param['Config']['Name'].title().replace('_', '')
                value = param['Config']['Value']
                data[key] = value

        data['id'] = self.prepId('ZoneMinder')
        data['title'] = results['url']
        rm = self.relMap()
        rm.append(self.objectMap(data))

        log.debug('%s ZoneMinder relmap:\n%s', device.id, rm)
        return rm
