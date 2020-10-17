"""Monitors ZoneMinder storage volumes using the JSON API"""

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


class Storage(PythonDataSourcePlugin):
    """ZoneMinder storage data source plugin"""

    @classmethod
    def config_key(cls, datasource, context):
        return(
            context.device().id,
            datasource.getCycleTime(context),
            context.id,
            'zoneminder-storage',
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
            comp_id = datasource.component.replace('zmStorage_', '')

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

                # Console
                # Session cookies on 1.34 require view=login on action=login
                # This returns a 302 to the console page
                # rather than just the console
                response = yield getPage(
                    '{0}index.php?view=console'.format(base_url),
                    method='GET',
                    cookies=cookies
                    )

                # Scrape storage info from HTML
                volumes = zmUtil.scrape_console_volumes(response)

                if comp_id not in volumes:
                    LOG.warn(
                        '%s: %s not found in ZM web console',
                        config.id,
                        datasource.component
                        )

                # Versions
                response = yield getPage(
                    api_url + 'host/getVersion.json',
                    method='GET',
                    cookies=cookies
                    )
                versions = zmUtil.dissect_versions(json.loads(response))

                storage = list()
                # 1.32+ required for storage.json
                if (versions['daemon']['major'] >= 1
                        and versions['daemon']['minor'] >= 32):
                    # Storage
                    response = yield getPage(
                        api_url + 'storage.json',
                        method='GET',
                        cookies=cookies
                        )
                    storage = json.loads(response).get('storage', list())

                    # API logout
                    yield getPage(
                        api_url + 'host/logout.json',
                        method='GET',
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
                LOG.exception('%s: failed to get store data', config.id)
                continue

            # Combine storage info from API with that scraped from Console
            for item in storage:
                store = item['Storage']
                if store['Name'] in volumes:
                    volumes[store['Name']].update(store)
                    if volumes[store['Name']]['DiskSpace']:
                        volumes[store['Name']]['events'] = int(
                            volumes[store['Name']]['DiskSpace']
                            )

            LOG.debug('%s: ZM storage output:\n%s', config.id, volumes)

            stats = volumes.get(comp_id, dict())

            for datapoint_id in (x.id for x in datasource.points):
                if datapoint_id not in stats:
                    continue

                value = stats.get(datapoint_id)
                dpname = '_'.join((datasource.datasource, datapoint_id))
                data['values'][datasource.component][dpname] = (value, 'N')

        returnValue(data)
