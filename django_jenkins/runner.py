# -*- coding: utf-8 -*-
"""
This module is intended to facilitate running Django TestCases in the
context of a Continuous Integration Server like Jenkins.

This module contains:
    - CITestSuiteRunner
        A DjangoTestSuiteRunner replacement for running in CI environments
    - XMLTestRunner
        A TestRunner subclass that produces XML in the jUnit style
    - XMLTestResult
        A TestResult subclass that helps in producing XMLResults,
        as well as storing added metadata associated with test runs,
        like per-test case runtimes & the ability to organize
        all test cases by their associated test suites.
"""
import os
import sys
import time
import unittest
from xml.dom.minidom import Document
from django.conf import settings
from django.test import TestCase
from django.test.simple import DjangoTestSuiteRunner, reorder_suite
from django_jenkins import signals
from django_jenkins import utils
try:
    from django.utils.unittest import TextTestRunner as TestRunner
except ImportError:
    from django.test.simple import DjangoTestRunner as TestRunner


class XMLTestResult(unittest.TestResult):
    def __init__(self, stream=sys.stderr, descriptions=1, verbosity=1,
            elapsed_times=True):
        self.successes = []
        self.timing = {}
        super(XMLTestResult, self).__init__(stream, descriptions, verbosity)

    def startTest(self, test):
        self.start_test_time = time.time()
        super(XMLTestResult, self).startTest(test)

    def stopTest(self, test):
        self.stop_test_time = time.time()
        self.timing[test] = self.stop_test_time - self.start_test_time
        super(XMLTestResult, self).stopTest(test)

    def addSuccess(self, test):
        "Called when a test executes successfully."
        self.successes.append((test, 'OK'))
        signals.test_add_success.send(sender=self, test=test)
        super(XMLTestResult, self).addSuccess(test)

    def addFailure(self, test, err):
        "Called when a test method fails."
        signals.test_add_failure.send(sender=self, test=test, err=err)
        super(XMLTestResult, self).addFailure(test)

    def addError(self, test, err):
        "Called when a test method raises an error."
        signals.test_add_error.send(sender=self, test=test, err=err)
        super(XMLTestResult, self).addError(test)

    def _get_info_by_testcase(self):
        """This method organizes test results by TestCase module. This
        information is used during the report generation, where a XML report
        will be generated for each TestCase.
        """
        tests_by_testcase = {}

        for tests in (self.successes, self.failures, self.errors):
            for test_info in tests:
                testcase = test_info[0]

                # Ignore module name if it is '__main__'
                module = testcase.__module__ + '.'
                if module == '__main__.':
                    module = ''
                testcase_name = module + testcase._testMethodName

                if testcase_name not in tests_by_testcase:
                    tests_by_testcase[testcase_name] = []
                tests_by_testcase[testcase_name].append(test_info)

        return tests_by_testcase

    def generate_reports(self, test_runner):
        "Generates the XML reports to a given XMLTestRunner object."
        all_results = self._get_info_by_testcase()

        if not os.path.exists(test_runner.output_dir):
            os.makedirs(test_runner.output_dir)

        for suite, tests in all_results.items():
            doc = Document()

            # Build the XML file
            testsuite = utils.report_testsuite(suite, tests, doc, self.timing)
            for test in tests:
                utils.report_testcase(suite, test, testsuite, doc, self.timing)
            utils.report_output(test_runner, testsuite, doc)
            xml_content = doc.toprettyxml(indent='\t')

            report_file = file('%s%sTEST-%s.xml' % (
                test_runner.output_dir, os.sep, suite), 'w')
            try:
                report_file.write(xml_content)
            finally:
                report_file.close()


class XMLTestRunner(TestRunner):
    """
    A test result class that can express test results in a XML report.
    """
    resultclass = XMLTestResult

    def __init__(self, output_dir, debug=False, with_reports=True, **kwargs):
        super(XMLTestRunner, self).__init__(**kwargs)
        self.with_reports = with_reports
        self.debug = debug
        self.output_dir = output_dir

    def run(self, test):
        result = super(XMLTestRunner, self).run(test)
        if self.with_reports:
            result.generate_reports(self)
        return result


class CITestSuiteRunner(DjangoTestSuiteRunner):
    """
    Continues integration test runner
    """
    def __init__(self, output_dir, debug=False, with_reports=True, **kwargs):
        super(CITestSuiteRunner, self).__init__(**kwargs)
        self.with_reports = with_reports
        self.debug = debug
        self.output_dir = output_dir

    def setup_test_environment(self, **kwargs):
        super(CITestSuiteRunner, self).setup_test_environment()
        signals.setup_test_environment.send(sender=self)

    def teardown_test_environment(self, **kwargs):
        super(CITestSuiteRunner, self).teardown_test_environment()
        signals.teardown_test_environment.send(sender=self)

    def setup_databases(self):
        if 'south' in settings.INSTALLED_APPS:
            from south.management.commands import patch_for_test_db_setup  # pylint: disable=F0401
            patch_for_test_db_setup()
        return super(CITestSuiteRunner, self).setup_databases()

    def build_suite(self, test_labels, **kwargs):
        suite = unittest.TestSuite()
        signals.build_suite.send(sender=self, suite=suite)
        return reorder_suite(suite, (TestCase,))

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        self.setup_test_environment()
        suite = self.build_suite(test_labels, extra_tests=extra_tests)
        if suite.countTestCases():
            old_config = self.setup_databases()
            result = self.run_suite(suite)
            self.teardown_databases(old_config)
            self.teardown_test_environment()
            return self.suite_result(suite, result)
        else:
            self.teardown_test_environment()
            return 0

    def run_suite(self, suite, **kwargs):
        signals.before_suite_run.send(sender=self)
        result = XMLTestRunner(
            verbosity=self.verbosity,
            output_dir=self.output_dir,
            debug=self.debug,
            with_reports=self.with_reports).run(suite)
        signals.after_suite_run.send(sender=self)

        return result
