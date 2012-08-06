# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


import time
import os
import mozinfo


class TestContext(object):
    """ Stores context data about the test """

    attrs = ['hostname', 'arch', 'env', 'os', 'os_version']

    def __init__(self, hostname='localhost'):
        self.hostname = hostname
        self.arch = mozinfo.processor
        self.env = os.environ.copy()
        self.os = mozinfo.os
        self.os_version = mozinfo.version

    def __str__(self):
        return '%s (%s, %s)' % (self.hostname, self.os, self.arch)

    def __repr__(self):
        return '<%s>' % self.__str__()

    def __eq__(self, other):
        if not isinstance(other, TestContext):
            return False
        diffs = [a for a in self.attrs if getattr(self, a) != getattr(other, a)]
        return len(diffs) == 0

    def __hash__(self):
        def get(attr):
            value = getattr(self, attr)
            if isinstance(value, dict):
                value = frozenset(value.items())
            return value
        return hash(frozenset([get(a) for a in self.attrs]))


class TestResult(object):
    """ Stores test result data """

    POSSIBLE_RESULTS = [
        'START',
        'PASS',
        'UNEXPECTED-PASS',
        'UNEXPECTED-FAIL',
        'KNOWN-FAIL',
        'SKIPPED',
        'ERROR',
    ]

    def __init__(self, name, test_class='', time_start=None, context=None,
                 result_expected='PASS'):
        """ Create a TestResult instance.
        name = name of the test that is running
        test_class = the class that the test belongs to
        time_start = timestamp (seconds since UNIX epoch) of when the test started
                     running; if not provided, defaults to the current time
        context = TestContext instance; can be None
        result_expected = string representing the expected outcome of the test"""

        msg = "Result '%s' not in possible results: %s" %\
                    (result_expected, ', '.join(self.POSSIBLE_RESULTS))
        assert isinstance(name, basestring), "name has to be a string"
        assert result_expected in self.POSSIBLE_RESULTS, msg

        self.name = name
        self.test_class = test_class
        self.context = context
        self.time_start = time_start if time_start is not None else time.time()
        self.time_end = None
        self.result_expected = result_expected
        self.result_actual = None
        self.filename = None
        self.description = None
        self.output = []
        self.reason = None

    def __str__(self):
        return '%s | %s (%s) | %s' % (self.result_actual or 'PENDING',
                                      self.name, self.test_class, self.reason)

    def __repr__(self):
        return '<%s>' % self.__str__()

    def finish(self, result, time_end=None, output=None, reason=None):
        """ Marks the test as finished, storing its end time and status """
        msg = "Result '%s' not in possible results: %s" %\
                    (result, ', '.join(self.POSSIBLE_RESULTS))
        assert result in self.POSSIBLE_RESULTS, msg

        # use lists instead of multiline strings
        if isinstance(output, basestring):
            output = output.splitlines()

        self.time_end = time_end if time_end is not None else time.time()
        self.output = output or self.output
        self.result_actual = result
        self.reason = reason

    @property
    def finished(self):
        """ Boolean saying if the test is finished or not """
        return self.result_actual is not None

    @property
    def duration(self):
        """ Returns the time it took for the test to finish. If the test is
        not finished, returns the elapsed time so far """
        if self.result_actual is not None:
            return self.time_end - self.time_start
        else:
            # returns the elapsed time
            return time.time() - self.time_start

    @property
    def successful(self):
        """ Boolean saying if the test was successful or not. None in
        case the test is not finished """
        if self.result_actual is not None:
            return self.result_expected == self.result_actual
        else:
            return None


class TestResultCollection(list):
    """ Container class that stores test results """

    def __init__(self, suite_name, time_taken=0):
        list.__init__(self)
        self.suite_name = suite_name
        self.time_taken = time_taken

    def __str__(self):
        return "%s (%.2fs)\n%s" % (self.suite_name, self.time_taken,
                                list.__str__(self))

    @property
    def contexts(self):
        """ List of unique contexts for the test results contained """
        cs = [tr.context for tr in self]
        return list(set(cs))

    def filter(self, predicate):
        """ Returns a generator of TestResults that satisfy a given predicate """
        return (tr for tr in self if predicate(tr))

    def tests_with_result(self, result):
        """ Returns a generator of TestResults with the given result """
        return self.filter(lambda t: t.result_actual == result)

    @property
    def successful(self):
        """ Returns a generator of successful TestResults"""
        return self.filter(lambda t: t.successful)

    @property
    def unsuccessful(self):
        """ Returns a generator of unsuccessful TestResults"""
        return self.filter(lambda t: not t.successful)

    @property
    def tests(self):
        """ Generator of all tests in the collection """
        return (t for t in self)

    def add_unittest_result(self, result, context=None):
        """ Adds the python unittest result provided to the collection"""

        def get_class(test):
            return test.__class__.__module__ + '.' + test.__class__.__name__

        def add_test_result(test, result_expected='PASS',
                            result_actual='PASS', output=''):
            t = TestResult(name=str(test).split()[0], test_class=get_class(test),
                           time_start=0, result_expected=result_expected,
                           context=context)
            t.finish(result_actual, time_end=0, reason=relevant_line(output),
                     output=output)
            self.append(t)

        self.time_taken += result.time_taken

        for test, output in result.errors:
            add_test_result(test, result_actual='ERROR', output=output)

        for test, output in result.failures:
            add_test_result(test, result_actual='UNEXPECTED-FAIL',
                            output=output)

        for test in result.unexpectedSuccesses:
            add_test_result(test, result_expected='KNOWN-FAIL',
                            result_actual='UNEXPECTED-PASS')

        for test, output in result.skipped:
            add_test_result(test, result_expected='SKIPPED',
                            result_actual='SKIPPED', output=output)

        for test, output in result.expectedFailures:
            add_test_result(test, result_expected='KNOWN-FAIL',
                            result_actual='KNOWN-FAIL', output=output)

        # unittest does not store these by default
        if hasattr(result, 'tests_passed'):
            for test in result.tests_passed:
                add_test_result(test)

    @classmethod
    def from_unittest_results(cls, results_list):
        """ Creates a TestResultCollection containing the given python
        unittest results """

        # so we can pass in a single unittest result instance as well
        if type(results_list) is not list:
            results_list = list(results_list)

        # all the TestResult instances share the same context
        context = TestContext()

        collection = cls('from %s' % results_list[0].__class__.__name__)

        for result in results_list:
            collection.add_unittest_result(result, context)

        return collection


# used to get exceptions/errors from tracebacks
def relevant_line(s):
    KEYWORDS = ('Error:', 'Exception:', 'error:', 'exception:')
    lines = s.splitlines()
    for line in lines:
        for keyword in KEYWORDS:
            if keyword in line:
                return line
    return 'N/A'
