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
elif evt.eventKey.endswith('Monitor-Status'):
    monitor_id = evt.component.replace('zmMonitor_', '')
    evt.summary = 'ZM monitor {0} process {1}'.format(monitor_id, state)
    severities = {
        0: SEVERITY_WARNING,
        1: SEVERITY_CLEAR,
        }
elif evt.eventKey.endswith('Daemon-RunState'):
    # Run State has changed, remodel to get new monitor functions
    # Model in background so transform isn't delayed
    device.collectDevice(background=True)

if 'Daemon-RunState' not in evt.eventKey:
    # ZPL Components look for events in /Status rather than
    # /Status/ClassName to determine up/down status
    evt.eventClass = '/Status'
    evt.severity = severities.get(current, SEVERITY_WARNING)
