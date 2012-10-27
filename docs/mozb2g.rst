MozB2G
=======

Mozb2g provides DeviceADB and DeviceSUT utility classes which can be used for testing b2g devices.

.. automodule:: mozb2g.b2gmixin
.. autoclass:: DeviceADB
   :members: cleanup, getAppInfo, restartB2G, restoreProfile, setupDHCP, setupMarionette, setupProfile, waitForPort

The DeviceSUT class provides the same methods described above.

Note that both the DeviceADB and DeviceSUT classes also inherit several device manager ADB and SUT methods accordingly, for more information about these methods see the documentation for `mozdevice <mozdevice.html>`_.
