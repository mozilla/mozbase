# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import time
import unittest

try:
    import psutil
except ImportError:
    psutil = None

from mozsysteminfo.resourcemonitor import (
    SystemResourceMonitor,
    SystemResourceUsage,
)


@unittest.skipIf(psutil is None, 'Resource monitor requires psutil.')
class TestResourceMonitor(unittest.TestCase):
    def test_basic(self):
        monitor = SystemResourceMonitor(poll_interval=0.5)

        monitor.start()
        time.sleep(2)

        monitor.stop()

        data = list(monitor.range_usage())
        self.assertGreater(len(data), 3)

        self.assertIsInstance(data[0], SystemResourceUsage)

    def test_phases(self):
        monitor = SystemResourceMonitor(poll_interval=0.1)

        monitor.start()
        time.sleep(1)

        with monitor.phase('phase1'):
            time.sleep(1)

            with monitor.phase('phase2'):
                time.sleep(1)

        monitor.stop()

        self.assertEqual(len(monitor.phases), 2)
        self.assertEqual(['phase2', 'phase1'], monitor.phases.keys())

        all = list(monitor.range_usage())
        data1 = list(monitor.phase_usage('phase1'))
        data2 = list(monitor.phase_usage('phase2'))

        self.assertGreater(len(all), len(data1))
        self.assertGreater(len(data1), len(data2))

        # This could fail if time.time() takes more than 0.1s. It really
        # shouldn't.
        self.assertAlmostEqual(data1[-1].end, data2[-1].end, delta=0.1)

    def test_no_data(self):
        monitor = SystemResourceMonitor()

        data = list(monitor.range_usage())
        self.assertEqual(len(data), 0)

    def test_events(self):
        monitor = SystemResourceMonitor(poll_interval=0.1)

        monitor.start()
        time.sleep(0.2)

        t0 = time.time()
        monitor.record_event('t0')
        monitor.stop()

        events = monitor.events
        self.assertEqual(len(events), 1)

        event = events[0]

        self.assertEqual(event[1], 't0')
        self.assertAlmostEqual(event[0], t0, delta=0.1)



