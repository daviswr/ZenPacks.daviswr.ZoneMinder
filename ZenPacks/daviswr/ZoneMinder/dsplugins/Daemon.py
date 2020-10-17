"""Monitors the ZoneMinder daemon using its JSON API"""

import logging
LOG = logging.getLogger('zen.ZoneMinder')

import json
import re
import urllib

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import getPage

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import (
    PythonDataSourcePlugin
    )

from ZenPacks.daviswr.ZoneMinder.lib import zmUtil


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
            # LOG.debug('%s: parameters\n%s', config.id, datasource.params)
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

            base_url = zmUtil.generate_zm_url(
                hostname=hostname or config.id,
                port=port or 443,
                path=path or '/zm/',
                ssl=ssl or True,
                url=base_url
                )

            if re.match(zmUtil.url_regex, base_url) is None:
                LOG.error('%s: %s is not a valid URL', config.id, base_url)
                returnValue(None)
            else:
                LOG.debug(
                    '%s: using base ZoneMinder URL %s',
                    config.id,
                    base_url
                    )

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
                elif not cookies:
                    LOG.error('%s: No cookies received', config.id)
                    returnValue(None)

                output = dict()

                # Console
                # Session cookies on 1.34 require view=login on action=login
                # This returns a 302 to the console page
                # rather than just the console
                response = yield getPage(
                    '{0}index.php?view=console'.format(base_url),
                    method='GET',
                    cookies=cookies
                    )

                # Scrape shared memory utilization from HTML
                output['devshm'] = zmUtil.scrape_console_shm(response)

                # Scrape DB connection counts from HTML
                output['db'] = zmUtil.scrape_console_db(response)

                # Scrape total capture bandwidth from HTML
                output['bandwidth'] = zmUtil.scrape_console_bandwidth(response)

                # Scrape system capturing percentage from HTML
                output['capturing'] = zmUtil.scrape_console_capturing(response)

                # Daemon status
                response = yield getPage(
                    api_url + 'host/daemonCheck.json',
                    method='GET',
                    cookies=cookies
                    )
                output.update(json.loads(response))

                # Run state
                response = yield getPage(
                    api_url + 'states.json',
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

                # Five-minute event counts
                response = yield getPage(
                    api_url + 'events/consoleEvents/300%20second.json',
                    method='GET',
                    cookies=cookies
                    )
                output.update(json.loads(response))

                # Versions
                response = yield getPage(
                    api_url + 'host/getVersion.json',
                    method='GET',
                    cookies=cookies
                    )
                versions = zmUtil.dissect_versions(json.loads(response))

                # Version-specific API calls
                if (versions['daemon']['major'] >= 1
                        and versions['daemon']['minor'] >= 32):
                    # API logout
                    yield getPage(
                        api_url + 'host/logout.json',
                        method='POST',
                        cookies=cookies
                        )
                else:
                    # Browser-style log out
                    # Doesn't work with 1.34.21
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
            # Daemon status ("result")
            stats['result'] = output.get('result', '0')

            states = output.get('states', list())
            if len(states) > 0:
                for state in states:
                    if state.get('State', dict()).get('IsActive', '0') == '1':
                        stats['state'] = state['State']['Id']
                        break

            load = output.get('load', list())
            if len(load) >= 3:
                (stats['load-1'], stats['load-5'], stats['load-15']) = load

            stats.update(output.get('db', dict()))

            for metric in ['bandwidth', 'capturing', 'devshm']:
                if metric in output:
                    stats[metric] = output[metric]

            # Event counts ("results", plural)
            events = output.get('results', list())
            stats['events'] = 0
            # "results" will be an empty *list* if no monitors have events
            if len(events) > 0:
                for key in events.keys():
                    stats['events'] += int(events.get(key, 0))

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
