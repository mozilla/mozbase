.. MozBase documentation master file, created by
   sphinx-quickstart on Mon Oct 22 14:02:17 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

mozbase
=======

Mozbase (normally written as `mozbase` except at the beginning of a
sentence) is a set of easy to use python libraries designed to be used
in the creation of automated testing software. It is used at least to some
degree by all of Mozilla's test harnesses including Talos_, mochitest_,
reftest_, Peptest_ and Eideticker_.

.. _Talos: http://hg.mozilla.org/build/

.. _mochitest: https://developer.mozilla.org/en-US/docs/Mochitest

.. _reftest: https://developer.mozilla.org/en-US/docs/Creating_reftest-based_unit_tests

.. _Peptest: https://github.com/mozilla/peptest/

.. _Eideticker: https://github.com/mozilla/eideticker/

In the course of writing automated tests at Mozilla, we found that
the same tasks needed to be performed occurred over and over, no
matter what the specific nature of what we were testing. We figured
that consolidating this code into a set of libraries would save us a
good deal of time, and so we spent some effort factoring out the best
of breed automation code into mozbase.

The documentation for mozbase is organized by category, then by
module. Figure out what you want to do then dive in!

.. toctree::
   :maxdepth: 2

   overview
   mozfile
   mozprocess
   manifestdestiny
   mozinfo
   setuprunning
   mozhttpd
   loggingreporting

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

