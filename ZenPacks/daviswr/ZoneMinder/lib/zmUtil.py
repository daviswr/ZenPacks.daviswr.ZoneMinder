""" A library of ZoneMinder-related functions """

import re

url_regex = r'^https?:\/\/\S+:?\d*\/?\S*\/$'


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
    # url_regex = r'^https?:\/\/\S+:?\d*\/?\S*\/$'
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
    """ Scrapes total capture bandwidth from Console page HTML """
    bandwidth_regex = r'<td class="colFunction">(\S+)B\/s'
    match = re.search(bandwidth_regex, html)
    if match:
        bandwidth_str = match.groups()[0].upper()
        if bandwidth_str[-1] not in '0123456789':
            unit_multi = {
                'K': 1000,
                'M': 1000**2,
                'G': 1000**3,
                'T': 1000**4,
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


def scrape_console_capturing(html):
    """ Scrapes system capturing percentage from Console page HTML """
    capturing_regex = r'Capturing.*\W+(\d+\.?\d*)%'
    capturing_match = re.search(capturing_regex, html)
    return float(capturing_match.groups()[0]) if capturing_match else ''


def scrape_console_db(html):
    """ Scrapes DB connection count from Console page HTML """
    db_regex = r'DB:(\d+)/(\d+)'
    db_match = re.search(db_regex, html)
    return {
        'db-used': int(db_match.groups()[0]) if db_match else '',
        'db-max': int(db_match.groups()[1]) if db_match else '',
        }


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


def scrape_console_shm(html):
    """ Scrape SHM utilization from Console page HTML """

    # stats_130_regex = r'Load.?\s+\d+\.\d+.*Disk.?\s+(\d+)%?.*\/w+\/shm.?\s(\d+)%?'  # noqa
    # stats_132_regex = r'Storage.?\s+(\d+)%?<?\/?[span]*>?.*\/\w+\/shm.?\s+(\d+)%?'  # noqa
    # SHM Example:
    # <span class="">/run/shm: 34%</span></li>
    shm_regex = r'/\w+\/shm.?\s+(\d+)%?'
    shm_match = re.search(shm_regex, html)
    return int(shm_match.groups()[0]) if shm_match else ''


def scrape_console_volumes(html):
    """ Scrapes storage volume information from HTML """

    multiplier = {
        'B': 1,
        'KB': 1024,
        'MB': 1024**2,
        'GB': 1024**3,
        'TB': 1024**4,
        'PB': 1024**5,
        'EB': 1024**6,
        'ZB': 1024**7,
        'YB': 1024**8,
        }

    # Storage volume Example:
    # <span class="" title="390.06GB of 2.69TB 249.93GB used by events">Storage2: 14%</span>  # noqa
    stores_regex = r'(\d+\.?\d*)(\w?B) of (\d+\.?\d*)(\w?B) (\d+\.?\d*)(\w?B) used by events.*\>(\w+):\s+(\d+)%'  # noqa
    disk130_regex = r'Disk.?\s+(\d+)%'
    stores = dict()

    store_matches = re.findall(stores_regex, html)
    for store_match in store_matches:
        # store_match tuple example:
        # ('3.37', 'TB', '3.58', 'TB', '2.6', 'TB', 'Default', '94')
        store_name = store_match[6]
        store = {
            'used': float(store_match[0]) * multiplier.get(store_match[1]),
            'total': float(store_match[2]) * multiplier.get(store_match[3]),
            'events': float(store_match[4]) * multiplier.get(store_match[5]),
            'percent': store_match[7],
            }
        for metric in store:
            store[metric] = int(store[metric])

        stores[store_name] = store

    # A volume named Default can be a dopplerganger of another volume,
    # but the event storage metric is associated with it instead of
    # the actual storage volume
    if 'Default' in stores:
        for store in stores:
            if (store != 'Default'
                    and 0 == stores[store]['events']
                    and stores[store]['used'] == stores['Default']['used']
                    and stores[store]['total'] == stores['Default']['total']):  # noqa
                stores[store]['events'] = stores['Default']['events']
                del stores['Default']
                break

    # Fake a storage volume based on 1.30's disk utilization percentage
    if not stores:
        disk_match = re.search(disk130_regex, html)
        if disk_match:
            stores['Default'] = {'percent': int(disk_match.groups()[0])}

    return stores
