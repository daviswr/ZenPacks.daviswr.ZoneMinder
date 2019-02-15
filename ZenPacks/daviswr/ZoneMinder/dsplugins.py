"""Monitors the ZoneMinder daemon using its JSON API"""

import logging
LOG = logging.getLogger('zen.ZoneMinder')

import json
import re
import urllib

from twisted.internet.defer \
    import inlineCallbacks, returnValue
from twisted.web.client \
    import getPage

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource \
    import PythonDataSourcePlugin


class Daemon(PythonDataSourcePlugin):
    """ZoneMinder daemon data source plugin"""

    @classmethod
    def config_key(cls, datasource, context):
        return(
            context.device().id,
            datasource.getCycleTime(context),
            context.id,
            'zoneminder-daemon',
            )

    @classmethod
    def params(cls, datasource, context):
        return {
            'username': context.zZoneMinderUsername,
            'password': context.zZoneMinderPassword,
            'hostname': context.zZoneMinderHostname,
            'port': context.zZoneMinderPort,
            'path': context.zZoneMinderPath,
            'ssl': context.zZoneMinderSSL,
            'base_url': context.zZoneMinderURL,
            }

    @inlineCallbacks
    def collect(self, config):
        data = self.new_data()

        for datasource in config.datasources:
            LOG.debug('%s: parameters\n%s', config.id, datasource.params)
            username = datasource.params['username']
            password = datasource.params['password']
            hostname = datasource.params['hostname']
            port = datasource.params['port']
            path = datasource.params['path']
            ssl = datasource.params['ssl']
            base_url = datasource.params['base_url']

            if not username or not password:
                LOG.error(
                    '%s: zZoneMinderUsername or zZoneMinderPassword not set',
                    config.id
                    )
                returnValue(None)

             # If custom URL not provided, assemble one
            if not base_url:
                if not hostname:
                    hostname = config.id
                    if '.' not in hostname:
                        hostname = hostname.replace('_', '.')
                port_str = ':' + str(port) if port else ''
                if not path.startswith('/'):
                    path = '/' + path
                if not path.endswith('/'):
                    path = path + '/'
                protocol = 'https' if ssl else 'http'
                base_url = '{0}://{1}{2}{3}'.format(
                    protocol,
                    hostname,
                    port_str,
                    path
                    )

            url_regex = r'^https?:\/\/\S+:?\d*\/?\S*\/$'
            if re.match(url_regex, base_url) is None:
                LOG.error('%s: %s is not a valid URL', config.id, base_url)
                returnValue(None)
            else:
                LOG.debug(
                    '%s: using base ZoneMinder URL %s',
                    config.id,
                    base_url
                    )

            api_url = b'{0}api/'.format(base_url)
            login_params = urllib.urlencode({
                'action': 'login',
                'view': 'postlogin',
                'username': username,
                'password': password,
                })
            login_url = b'{0}index.php?{1}'.format(base_url, login_params)

            cookies = dict()
            try:
                # Attempt login
                login_response = yield getPage(
                    login_url,
                    method='POST',
                    cookies=cookies
                    )

                if 'Invalid username or password' in login_response:
                    LOG.error(
                        '%s: ZoneMinder login credentials invalid',
                        config.id,
                        )
                    returnValue(None)
                elif len(cookies) == 0:
                    LOG.error('%s: No cookies received', config.id)
                    returnValue(None)

                output = dict()

                # Daemon status
                response = yield getPage(
                    api_url + 'host/daemonCheck.json',
                    method='GET',
                    cookies=cookies
                    )
                output.update(json.loads(response))

                # Host Load
                response = yield getPage(
                    api_url + 'host/getLoad.json',
                    method='GET',
                    cookies=cookies
                    )
                output.update(json.loads(response))

                # Scrape index.php for disk %?

                # Log out
                yield getPage(
                    base_url + 'index.php?action=logout',
                    method='POST',
                    cookies=cookies
                    )
            except Exception, e:
                LOG.exception('%s: failed to get daemon data', config.id)
                continue

            LOG.debug('%s: ZM daemon output:\n%s', config.id, output)

            stats = dict()
            stats['result'] = output.get('result', '0')
            load = output.get('load', list())
            if len(load) >= 3:
                (stats['load-1'], stats['load-5'], stats['load-15']) = load

            for datapoint_id in (x.id for x in datasource.points):
                if datapoint_id not in stats:
                    continue

                try:
                    if datapoint_id.startswith('load-'):
                        value = float(stats.get(datapoint_id))
                    else:
                        value = int(stats.get(datapoint_id))
                except (TypeError, ValueError):
                    continue

                dpname = '_'.join((datasource.datasource, datapoint_id))
                data['values'][datasource.component][dpname] = (value, 'N')

        returnValue(data)
