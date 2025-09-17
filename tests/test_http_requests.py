# Copyright 2025 NEC Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
#  under the License.

"""
Test program for _HTTPRequests class
"""

import io
import json
from unittest import TestCase, mock
import requests
from plugins.fm.reference.plugin import _ErrorCtrl, _ErrorType, _HTTPRequests


_DEFAULT_SPECIFIC_DATA = {
    "service_type": "http",
    "service_host": "localhost",
    "service_port": 5555,
    "service_root": "/redfish/v1",
    "timeout": 3.0,
}
_LOG_PREFIX = "WARNING:plugins.fm.reference.plugin:"


def _mock_response(code: int, data: str):
    """Mock the return data of the HTTP request method."""
    response = requests.models.Response()
    response.raw = io.BytesIO(bytes(data, encoding="utf-8"))
    response.status_code = code
    return response


class TestInit(TestCase):
    """Test class for constructor."""

    def setUp(self):
        self.err = _ErrorCtrl()

    def test___init___specific_data_is_none(self):
        """Test to ensure that no assertion is raised when specific_data is None."""
        req = _HTTPRequests(None, self.err)
        self.assertEqual(self.err, req.err)

    def test___init___specific_data_dose_not_have_service_type(self):
        """Test when service_type is not set in specific_data."""
        specific_data = {k: v for k, v in _DEFAULT_SPECIFIC_DATA.items() if k != "service_type"}
        req = _HTTPRequests(specific_data, self.err)
        self.assertIsNone(req.url)
        self.assertEqual([_ErrorType.ERROR_INCORRECT], req.err.error)

    def test___init___specific_data_dose_not_have_service_host(self):
        """Test when service_host is not set in specific_data."""
        specific_data = {k: v for k, v in _DEFAULT_SPECIFIC_DATA.items() if k != "service_host"}
        req = _HTTPRequests(specific_data, self.err)
        self.assertIsNone(req.url)
        self.assertEqual([_ErrorType.ERROR_INCORRECT], req.err.error)

    def test___init___specific_data_dose_not_have_service_port(self):
        """Test when service_port is not set in specific_data."""
        specific_data = {k: v for k, v in _DEFAULT_SPECIFIC_DATA.items() if k != "service_port"}
        req = _HTTPRequests(specific_data, self.err)
        self.assertIsNone(req.url)
        self.assertEqual([_ErrorType.ERROR_INCORRECT], req.err.error)

    def test___init___specific_data_dose_not_have_service_root(self):
        """Test when service_root is not set in specific_data."""
        specific_data = {k: v for k, v in _DEFAULT_SPECIFIC_DATA.items() if k != "service_root"}
        req = _HTTPRequests(specific_data, self.err)
        self.assertIsNone(req.root)
        self.assertEqual([_ErrorType.ERROR_INCORRECT], req.err.error)

    def test___init___specific_data_dose_not_have_timeout(self):
        """Test when service_timeout is not set in specific_data."""
        specific_data = {k: v for k, v in _DEFAULT_SPECIFIC_DATA.items() if k != "timeout"}
        req = _HTTPRequests(specific_data, self.err)
        self.assertEqual(1.0, req.timeout)
        self.assertEqual([], req.err.error)

    def test___init___normal(self):
        """Test when all parameters are set in specific_data."""
        req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, self.err)
        self.assertEqual(3.0, req.timeout)
        self.assertEqual("/redfish/v1", req.root)
        self.assertEqual("http://localhost:5555", req.url)
        self.assertEqual([], req.err.error)


class TestCheckResponse(TestCase):
    """Test class for _check_response method."""

    err: _ErrorCtrl
    req: _HTTPRequests

    @classmethod
    def setUpClass(cls):
        cls.err = _ErrorCtrl()
        cls.req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, cls.err)

    def tearDown(self):
        self.err.error = []

    def _mock_call(self, status_code: int, text: str, errno: _ErrorType, logmsg: str):
        with mock.patch("requests.get") as req_func:
            req_func.return_value = _mock_response(status_code, text)
            with self.assertLogs(level="WARNING") as _cm:
                self.assertIsNone(self.req.get(""))
            self.assertEqual([errno], self.err.error)
            self.assertIn(f"{_LOG_PREFIX}{logmsg}", _cm.output[0])

    def test__check_response_status_code_is_500(self):
        """Test when an HTTP status code 500 is returned."""
        logmsg = "Server error case response status code is 500"
        text = json.dumps({"message": "Internal Server Error"})
        self._mock_call(500, text, _ErrorType.ERROR_CONTROL, logmsg)

    def test__check_response_status_code_is_not_200(self):
        """Test when a status code other than 200 is returned."""
        logmsg = "Internal error case response status code is 404"
        text = json.dumps({"message": "Not Found"})
        self._mock_call(404, text, _ErrorType.ERROR_INTERNAL, logmsg)

    def test__check_response_text_is_not_json(self):
        """Test when the returned data is not in JSON format."""
        logmsg = "Invalid response text 'not json text'"
        self._mock_call(200, "not json text", _ErrorType.ERROR_CONTROL, logmsg)

    def test__check_response_normal(self):
        """Test when data retrieval is successful."""
        with mock.patch("requests.get") as req_func:
            data = {"sample": "sample"}
            req_func.return_value = _mock_response(200, json.dumps(data))
            with self.assertNoLogs(level="WARNING"):
                self.assertEqual(data, self.req.get(""))
            self.assertEqual([], self.err.error)


class TestRequests(TestCase):
    """Test class for _request method."""

    err: _ErrorCtrl

    @classmethod
    def setUpClass(cls):
        cls.err = _ErrorCtrl()

    def tearDown(self):
        self.err.error = []

    def _mock_call(self, specific_data: dict, method: str, errno: _ErrorType, logmsgs: list):
        with self.assertLogs(level="WARNING") as _cm:
            req = _HTTPRequests(specific_data, self.err)
            # pylint: disable=protected-access
            req._check_response = mock.Mock()  # type: ignore[method-assign]
            req._check_response.return_value = _mock_response(200, json.dumps({"data": "data"}))
            self.assertIsNone(req._request(method, ""))
            self.assertEqual([errno], self.err.error)
            for logmsg in logmsgs:
                self.assertIn(logmsg, _cm.output[0])

    def test__requests_url_is_none(self):
        """Test when the url attribute of the _HTTPRequests class is not set."""
        specific_data = {k: v for k, v in _DEFAULT_SPECIFIC_DATA.items() if k != "service_type"}
        logmsg = ["Invalid specific_data. None, localhost, 5555, /redfish/v1"]
        self._mock_call(specific_data, "get", _ErrorType.ERROR_INCORRECT, logmsg)

    def test__requests_unknown_method(self):
        """Test for specifying a method that does not exist in the requests module."""
        logmsg = ["Invalid method 'gett' specified.", "AttributeError"]
        self._mock_call(_DEFAULT_SPECIFIC_DATA, "gett", _ErrorType.ERROR_INTERNAL, logmsg)

    def test__requests_invalid_schema(self):
        """Test for specifying an invalid schema in service_type."""
        specific_data = _DEFAULT_SPECIFIC_DATA.copy()
        specific_data["service_type"] = "@@@"
        logmsg = ["Invalid specific data error @@@://localhost:5555/", "InvalidSchema"]
        self._mock_call(specific_data, "get", _ErrorType.ERROR_INCORRECT, logmsg)

    def test__requests_invalid_url(self):
        """Test for specifying an invalid host in service_host."""
        specific_data = _DEFAULT_SPECIFIC_DATA.copy()
        specific_data["service_host"] = "/"
        logmsg = ["Invalid specific data error http:///:5555/", "InvalidURL"]
        self._mock_call(specific_data, "get", _ErrorType.ERROR_INCORRECT, logmsg)

    def test__requests_exception(self):
        """Test for cases where an exception is raised."""
        specific_data = _DEFAULT_SPECIFIC_DATA.copy()
        specific_data["timeout"] = 0.0001
        # Either ReadTimeout or ConnectionError occurs.
        logmsg = ["Server error case", "requests.exceptions"]
        self._mock_call(specific_data, "get", _ErrorType.ERROR_CONTROL, logmsg)

    def test__requests_normal(self):
        """The test for normal operation is the same as TestCheckResponse.test_normal."""


class TestOtherMethods(TestCase):
    """Test class for get, patch, blkid2odata methods."""

    def setUp(self):
        err = _ErrorCtrl()
        self.req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, err)
        # pylint: disable=protected-access
        self.req._request = mock.Mock()
        self.req._request.return_value = {}

    def _check_args(self, expected: tuple):
        # pylint: disable=protected-access
        assert isinstance(self.req._request, mock.Mock)
        self.assertEqual(expected, self.req._request.call_args[0])

    def test_get_without_complete_path(self):
        """Test for the get method when complete_path is not specified."""
        self.req.get("sample")
        self._check_args(("get", "sample"))

    def test_get_complete_path_is_true(self):
        """Test for the get method when complete_path is set to true."""
        self.req.get("sample", True)
        self._check_args(("get", "/redfish/v1/sample"))

    def test_get_complete_path_is_false(self):
        """Test for the get method when complete_path is set to false."""
        self.req.get("sample", False)
        self._check_args(("get", "sample"))

    def test_patch_without_complete_path(self):
        """Test for the patch method when complete_path is not specified."""
        self.req.patch("sample", {"data": "data"})
        self._check_args(("patch", "sample", '{"data": "data"}'))

    def test_patch_complete_path_is_true(self):
        """Test for the patch method when complete_path is set to true."""
        self.req.patch("sample", {"data": "data"}, True)
        self._check_args(("patch", "/redfish/v1/sample", '{"data": "data"}'))

    def test_patch_complete_path_is_false(self):
        """Test for the patch method when complete_path is set to false."""
        self.req.patch("sample", {"data": "data"}, False)
        self._check_args(("patch", "sample", '{"data": "data"}'))

    def test_blkid2odata(self):
        """Test for the blkid2odata method."""
        expected = "/redfish/v1/CompositionService/ResourceBlocks/Block-1"
        self.assertEqual(expected, self.req.blkid2odata("Block-1"))
