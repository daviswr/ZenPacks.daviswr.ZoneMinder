from zenoss.protocols.protobufs.zep_pb2 import (
    SEVERITY_CLEAR,
    SEVERITY_WARNING,
    SEVERITY_ERROR
    )

current = int(float(evt.current))
states = {
    0: 'is not running',
    1: 'is running',
    }
state = states.get(current, 'status is unknown')

severities = dict()

if evt.eventKey.endswith('Daemon-Status'):
    evt.summary = 'ZoneMinder daemon {0}'.format(state)
    severities = {
        0: SEVERITY_ERROR,
        1: SEVERITY_CLEAR,
        }

elif evt.eventKey.endswith('Daemon-RunState'):
    # Run State has changed, remodel to get new monitor functions
    # Model in background so transform isn't delayed
    device.collectDevice(background=True)
    evt._action = 'history'

elif evt.eventKey.endswith('Daemon-Capturing'):
    if SEVERITY_CLEAR == evt.severity:
        evt.summary = 'All monitors are capturing'
    else:
        no_cap = 100 - current
        evt.summary = '{0}% of monitors are not capturing'.format(no_cap)

elif 'Monitor' in evt.eventKey:
    monitor_id = evt.component.replace('zmMonitor', '')
    severities = {
        0: SEVERITY_WARNING,
        1: SEVERITY_CLEAR,
        }
    if 'Status' in evt.eventKey:
        evt.summary = 'ZM monitor {0} process {1}'.format(monitor_id, state)
    elif 'Online' in evt.eventKey:
        online_map = {
            0: 'is offline',
            1: 'is online',
            }
        online = online_map.get(current, 'reachability unknown')
        evt.summary = 'ZM monitor {0} {1}'.format(monitor_id, online)
    elif 'Enabled' in evt.eventKey:
        enabled_map = {
            0: 'disabled',
            1: 'enabled',
            }
        enabled = enabled_map.get(current, 'unknown')
        evt.summary = 'ZM monitor {0} is {1}'.format(monitor_id, enabled)

        @transact
        def updateDb():
            component.Enabled = True if 1 == current else False
        updateDb()

# ZPL Components look for events in /Status rather than
# /Status/ClassName to determine up/down status
if ('Daemon-RunState' not in evt.eventKey
        and 'Daemon-Capturing' not in evt.eventKey):
    evt.eventClass = '/Status'
    if evt.severity != SEVERITY_CLEAR:
        evt.severity = severities.get(current, SEVERITY_WARNING)
