""" A library of ZoneMinder-related functions """

import re


def dissect_versions(versions):
    """ Dissects version JSON returned by the API """
    version_tokens = versions.get('version', '').split('.')
    if len(version_tokens) > 1:
        (major, minor, rev) = version_tokens
    else:
        major = 0
        minor = 0
        rev = 0

    apiver_tokens = versions.get('apiversion', '').split('.')
    if len(apiver_tokens) > 1:
        (api_major, api_minor) = apiver_tokens
    else:
        api_major = 0
        api_minor = 0

    return {
        'daemon': {
            'major': major,
            'minor': minor,
            'rev': rev,
            },
        'api': {
            'major': api_major,
            'minor': api_minor,
            }
        }


def generate_zm_url(hostname=None,
                    port=443,
                    path='/zm/',
                    ssl=True,
                    url=None):
    """ Returns ZoneMinder base URL from given parameters """
    # If valid custom URL not provided, assemble one
    url_regex = r'^https?:\/\/\S+:?\d*\/?\S*\/$'
    if hostname and (not url or not re.match(url_regex, url)):
        if '.' not in hostname:
            hostname = hostname.replace('_', '.')
        port_str = ':' + str(port) if port else ''
        if not path.startswith('/'):
            path = '/' + path
        if not path.endswith('/'):
            path = path + '/'
        protocol = 'https' if ssl else 'http'
        url = '{0}://{1}{2}{3}'.format(
            protocol,
            hostname,
            port_str,
            path
            )

    return url


def scrape_console_bandwidth(html):
    """ Scrapes total capture bandwidth from HTML """
    bandwidth_regex = r'<td class="colFunction">(\S+)B\/s'
    match = re.search(bandwidth_regex, html)
    if match:
        bandwidth_str = match.groups()[0]
        if bandwidth_str[-1] not in '0123456789':
            unit_multi = {
                'K': 1000,
                'M': 1000000,
                'G': 1000000000,
                }
            bandwidth = float(bandwidth_str[:-1])
            bandwidth = bandwidth * unit_multi.get(
                bandwidth_str[-1],
                1
                )
        else:
            bandwidth = float(bandwidth_str)
    else:
        bandwidth = ''

    return bandwidth


def scrape_console_monitor(html, monitor_id):
    """ Scrapes monitor connectivity status from Console page HTML """
    online_regex = r'<td class="colSource">.*<span class="(\w+)Text">'
    online_map = {
        'error': 0,
        'info': 1,
        }
    output = ''

    # 1.30
    if 'zmWatch' in html:
        watch_prefix = 'zmWatch'
        watch_offset = 2
    # 1.34
    elif 'zmMonitor' in html:
        watch_prefix = 'zmMonitor'
        watch_offset = 0
    # 1.32
    elif 'monitor_id-' in html:
        watch_prefix = 'monitor_id-'
        watch_offset = 9
    else:
        watch_prefix = ''

    watch_id = watch_prefix + monitor_id

    if watch_id in html:
        watch_index = -1
        console = html.splitlines()
        for ii in range(0, len(console) - 1):
            if watch_id in console[ii]:
                watch_index = ii
                break
        if watch_index > -1:
            online_line = console[watch_index + watch_offset]
            online_match = re.search(online_regex, online_line)
            if online_match:
                online_state = online_match.groups()[0]
                output = online_map.get(online_state, 2)

    return output


def scrape_console_storage(html):
    """ Scrape disk and (/dev/shm|/run/shm) utilization from HTML """
    # TODO: Report multiple storage volumes

    stats_130_regex = r'Load.?\s+\d+\.\d+.*Disk.?\s+(\d+)%?.*\/w+\/shm.?\s(\d+)%?'  # noqa
    stats_132_regex = r'Storage.?\s+(\d+)%?<?\/?[span]*>?.*\/\w+\/shm.?\s+(\d+)%?'  # noqa
    storage_regex = r'Storage.?\s+(\d+)%?'
    shm_regex = r'/\w+\/shm.?\s+(\d+)%?'

    match = (re.search(stats_130_regex, html)
             or re.search(stats_132_regex, html))
    if match:
        console = {
            'disk': match.groups()[0],
            'devshm': match.groups()[1],
            }
    else:
        storage_match = re.search(storage_regex, html)
        shm_match = re.search(shm_regex, html)
        console = {
            'disk': storage_match.groups()[0] if storage_match else '',
            'devshm': shm_match.groups()[0] if shm_match else '',
            }

    return console
