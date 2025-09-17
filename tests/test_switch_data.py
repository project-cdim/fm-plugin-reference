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
Test program for _SwitchData class
"""

import copy
import json
from unittest import TestCase, mock
from test_http_requests import _DEFAULT_SPECIFIC_DATA, _mock_response
from plugins.fm.reference.plugin import _ErrorCtrl, _ErrorType, _HTTPRequests, _SwitchData


_DEFAULT_SWITCH_DATA = {
    "Manufacturer": "sample manufacturer",
    "Model": "sample model",
    "SerialNumber": "sample serial number",
}


class TestsInit(TestCase):
    """Test class for constructor."""

    def setUp(self):
        self.err = _ErrorCtrl()
        self.req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, self.err)

    def test___init___normal(self):
        """Test for the initialization of instance variables."""
        swt = _SwitchData("test", self.req)
        self.assertEqual("test", swt.sid)
        self.assertEqual("test", swt.switch.switch_id)
        self.assertIsNone(swt.switch.switch_manufacturer)
        self.assertIsNone(swt.switch.switch_model)
        self.assertIsNone(swt.switch.switch_serial_number)
        self.assertIsNone(swt.switch.link)


class TestsSaveSwitchData(TestCase):
    """Test class for save_switch_data method."""

    def setUp(self):
        self.err = _ErrorCtrl()
        self.req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, self.err)
        self.swt = _SwitchData("test", self.req)

    def _mock_call(self, status_code: int, text: str, error: bool = False):
        with mock.patch("requests.get") as req_func:
            req_func.return_value = _mock_response(status_code, text)
            if error:
                with self.assertLogs(level="WARNING") as _cm:
                    self.swt.save_switch_data()
                self.assertIn("Validation error", _cm.output[0])
                self.assertEqual([_ErrorType.ERROR_INTERNAL], self.err.error)
            else:
                self.swt.save_switch_data()

    def test_save_switch_data_switch_is_none(self):
        """Test when failing to retrieve the switch schema."""
        self._mock_call(404, json.dumps({"message": "Not Found"}))
        self.assertIsNone(self.swt.switch.switch_manufacturer)
        self.assertIsNone(self.swt.switch.switch_model)
        self.assertIsNone(self.swt.switch.switch_serial_number)

    def test_save_switch_data_manufacturer_is_none(self):
        """Test when there is no manufacturer information in the switch schema."""
        switch_data = {k: v for k, v in _DEFAULT_SWITCH_DATA.items() if k != "Manufacturer"}
        self._mock_call(200, json.dumps(switch_data))
        self.assertIsNone(self.swt.switch.switch_manufacturer)

    def test_save_switch_data_manufacturer_is_not_string(self):
        """Test when the manufacturer in the switch schema is not a string."""
        switch_data = copy.deepcopy(_DEFAULT_SWITCH_DATA)
        switch_data["Manufacturer"] = {}  # type: ignore[reportGeneralTypeIssues]
        self._mock_call(200, json.dumps(switch_data), True)
        self.assertIsNone(self.swt.switch.switch_manufacturer)

    def test_save_switch_data_model_is_none(self):
        """Test when there is no model information in the switch schema."""
        switch_data = {k: v for k, v in _DEFAULT_SWITCH_DATA.items() if k != "Model"}
        self._mock_call(200, json.dumps(switch_data))
        self.assertIsNone(self.swt.switch.switch_model)

    def test_save_switch_data_model_is_not_string(self):
        """Test when the model in the switch schema is not a string."""
        switch_data = copy.deepcopy(_DEFAULT_SWITCH_DATA)
        switch_data["Model"] = ["str1", "str2"]  # type: ignore[reportGeneralTypeIssues]
        self._mock_call(200, json.dumps(switch_data), True)
        self.assertIsNone(self.swt.switch.switch_model)

    def test_save_switch_data_serial_number_is_none(self):
        """Test when there is no serial number information in the switch schema."""
        switch_data = {k: v for k, v in _DEFAULT_SWITCH_DATA.items() if k != "SerialNumber"}
        self._mock_call(200, json.dumps(switch_data))
        self.assertIsNone(self.swt.switch.switch_serial_number)

    def test_save_switch_data_serial_number_is_not_string(self):
        """Test when the serial number in the switch schema is not a string."""
        switch_data = copy.deepcopy(_DEFAULT_SWITCH_DATA)
        switch_data["SerialNumber"] = 5  # type: ignore[reportGeneralTypeIssues]
        self._mock_call(200, json.dumps(switch_data), True)
        self.assertIsNone(self.swt.switch.switch_serial_number)

    def test_save_switch_data_normal(self):
        """Test when all information is successfully retrieved."""
        self._mock_call(200, json.dumps(_DEFAULT_SWITCH_DATA))
        self.assertEqual("sample manufacturer", self.swt.switch.switch_manufacturer)
        self.assertEqual("sample model", self.swt.switch.switch_model)
        self.assertEqual("sample serial number", self.swt.switch.switch_serial_number)


class TestsSaveSwitchLink(TestCase):
    """Test class for save_switch_link method."""

    def setUp(self):
        self.err = _ErrorCtrl()
        self.req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, self.err)
        self.swt = _SwitchData("test", self.req)

    def test_save_switch_link_only_myself(self):
        """Test when there is only one switch."""
        self.swt.save_switch_link(["test"])
        self.assertEqual([], self.swt.switch.link)

    def test_save_switch_link_switches_post(self):
        """Test when there are two switches (after)."""
        self.swt.save_switch_link(["test", "post"])
        self.assertEqual(["post"], self.swt.switch.link)

    def test_save_switch_link_switches_prev(self):
        """Test when there are two switches (before)."""
        self.swt.save_switch_link(["prev", "test"])
        self.assertEqual(["prev"], self.swt.switch.link)

    def test_save_switch_link_3_switches(self):
        """Test when there are three switches."""
        self.swt.save_switch_link(["prev", "test", "post"])
        self.assertEqual(["prev", "post"], self.swt.switch.link)

    def test_save_switch_link_one_other(self):
        """Test when a switch other than the current one is specified."""
        self.swt.save_switch_link(["sample"])
        self.assertEqual(["sample"], self.swt.switch.link)


class TestsGetSwitchData(TestCase):
    """Test class for get_switch_data method."""

    def setUp(self):
        self.err = _ErrorCtrl()
        self.req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, self.err)
        self.swt = _SwitchData("test", self.req)

    def test_get_switch_data_all_set(self):
        """Test when all information is successfully retrieved."""
        with mock.patch("requests.get") as req_func:
            req_func.return_value = _mock_response(200, json.dumps(_DEFAULT_SWITCH_DATA))
            self.swt.save_switch_data()
        self.swt.save_switch_link(["prev", "test", "post"])
        swt = self.swt.get_switch_data()
        self.assertEqual("test", swt.switch_id)
        self.assertEqual(["prev", "post"], swt.link)
        self.assertEqual("sample manufacturer", swt.switch_manufacturer)
        self.assertEqual("sample model", swt.switch_model)
        self.assertEqual("sample serial number", swt.switch_serial_number)

    def test_get_switch_data_not_set(self):
        """Test when the information cannot be retrieved."""
        swt = self.swt.get_switch_data()
        self.assertEqual("test", swt.switch_id)
        self.assertIsNone(swt.switch_manufacturer)
        self.assertIsNone(swt.switch_model)
        self.assertIsNone(swt.switch_serial_number)
        self.assertIsNone(swt.link)
