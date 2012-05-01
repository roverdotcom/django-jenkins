
def add_cdata(xml_document, content, append_to=None):
    """
    Protect from CDATA inside CDATA
    """
    results = list()
    content = content.split(']]>')
    for index, entry in enumerate(content):
        if not entry:
            continue
        if index < len(content) - 1:
            entry += ']]'
        results.append(xml_document.createCDATASection(entry))
        if index < len(content) - 1:
            results.append(xml_document.createCDATASection('>'))
    if append_to:
        for result in results:
            append_to.appendChild(result)


def report_testcase(suite_name, test_result, xml_testsuite, xml_document,
        timing):
    "Appends a testcase section to the XML document."
    testcase = xml_document.createElement('testcase')
    xml_testsuite.appendChild(testcase)

    testcase.setAttribute('classname', suite_name)
    testcase.setAttribute('name', test_result[0].test_method.id)
    testcase.setAttribute('time', '%.3f' % test_result.get_elapsed_time())

    if (test_result.outcome != 0):
        elem_name = ('failure', 'error')[test_result.outcome - 1]
        failure = xml_document.createElement(elem_name)
        testcase.appendChild(failure)

        failure.setAttribute('type', test_result.err[0].__name__)
        failure.setAttribute('message', str(test_result.err[1]))

        error_info = test_result.get_error_info()
        add_cdata(xml_document, error_info, failure)


def report_testsuite(suite_name, tests, xml_document, timing):
    """
    Appends the testsuite section to the XML document.
    """
    testsuite = xml_document.createElement('testsuite')
    xml_document.appendChild(testsuite)

    testsuite.setAttribute('name', suite_name)
    testsuite.setAttribute('tests', str(len(tests)))

    testsuite.setAttribute('time', '%.3f' % sum([
        timing[test[0]] for test in tests]))
    """
    failures = filter(lambda e: e.outcome == 0, tests)
    testsuite.setAttribute('failures', str(len(failures)))

    errors = filter(lambda e: e.outcome == 0, tests)
    testsuite.setAttribute('errors', str(len(errors)))
    """

    return testsuite
