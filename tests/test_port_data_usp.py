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
Test program for _PortDataUSP class
"""

import copy
import json
from unittest import TestCase, mock
from test_http_requests import _DEFAULT_SPECIFIC_DATA, _mock_response
from test_port_data import _DEFAULT_NONE_PORT_MEMBERS
from plugins.fm.reference.plugin import _ErrorCtrl, _ErrorType, _HttpRequests, _PortDataUSP


_DEFAULT_PROCESSOR_DATA = {
    "ProcessorType": "CPU",
    "Manufacturer": "manufacturer",
    "Model": "model",
    "SerialNumber": "serial number"
}


class TestsInit(TestCase):
    """Test class for constructor."""

    def setUp(self):
        err = _ErrorCtrl()
        self.req = _HttpRequests(_DEFAULT_SPECIFIC_DATA, err)

    def test___init__normal(self):
        """Test for the initialization of instance variables."""
        prt = _PortDataUSP("ComputeBlock-1", self.req)
        self.assertEqual("ComputeBlock-1", prt.pid)
        self.assertEqual("ComputeBlock-1", prt.port.id)
        self.assertEqual("Systems/System-1", prt.syspath)
        for member in _DEFAULT_NONE_PORT_MEMBERS:
            self.assertIsNone(getattr(prt.port, member))
        self.assertEqual("USP", prt.port.switch_port_type)
        self.assertEqual({}, prt.port.device_keys)
        self.assertEqual({}, prt.port.port_keys)


class TestsSaveLinkUSP(TestCase):
    """Test class for save_link method."""

    def setUp(self):
        err = _ErrorCtrl()
        req = _HttpRequests(_DEFAULT_SPECIFIC_DATA, err)
        self.usp = _PortDataUSP("ComputeBlock-1", req)
        self.port_ids = ["ComputeBlock-1", "ComputeBlock-2", "DeviceBlock-3", "DeviceBlock-4"]

    def _mock_call(self, status_code, data, logmsg=None):
        with mock.patch("plugins.fm.reference.plugin.log.warning") as log_func:
            with mock.patch("requests.get") as req_func:
                req_func.return_value = _mock_response(status_code, json.dumps(data))
                self.usp.save_link(self.port_ids)
                if logmsg:
                    log_func.assert_called_with(logmsg)
                    self.assertEqual([_ErrorType.ERROR_CONTROL], self.usp.err.error)
                    self.assertIsNone(self.usp.port.link)
                else:
                    log_func.assert_not_called()
                    self.assertEqual([], self.usp.err.error)

    def test_save_link_sysdata_is_none(self):
        """Test when the compute system schema cannot be retrieved."""
        errmsg = "Server error case response status code is 500"
        self._mock_call(500, {"message": "Internal Server Error"}, errmsg)

    def test_save_link_odataid_not_found(self):
        """Test when the format of the compute system schema is incorrect."""
        pids = ["ComputeBlock-1", "DeviceBlock-3"]
        members = [{"@odata.id": f"CompositionService/ResourceBlocks/{x}"} for x in pids]
        members.append({})
        self._mock_call(200, {"Links": {"ResourceBlocks": members}}, "Invalid format {}")

    def test_save_link_inconsistent_ids(self):
        """Test for inconsistencies in links of the retrieved compute system schema."""
        errmsg = f"Invalid resource block DeviceBlock-2 not in {self.port_ids}"
        pids = ["ComputeBlock-1", "DeviceBlock-2"]
        members = [{"@odata.id": f"CompositionService/ResourceBlocks/{x}"} for x in pids]
        self._mock_call(200, {"Links": {"ResourceBlocks": members}}, errmsg)

    def test_save_link_no_data(self):
        """Test when the compute system does not exist."""
        self._mock_call(200, {"Links": {"ResourceBlocks": []}})
        self.assertEqual([], self.usp.port.link)

    def test_save_link_one_data(self):
        """Test when one link is found."""
        pids = ["ComputeBlock-1", "DeviceBlock-3"]
        members = [{"@odata.id": f"CompositionService/ResourceBlocks/{x}"} for x in pids]
        self._mock_call(200, {"Links": {"ResourceBlocks": members}})
        self.assertEqual(["DeviceBlock-3"], self.usp.port.link)

    def test_save_link_two_data(self):
        """Test when multiple links are found."""
        pids = ["ComputeBlock-1", "DeviceBlock-3", "DeviceBlock-4"]
        members = [{"@odata.id": f"CompositionService/ResourceBlocks/{x}"} for x in pids]
        self._mock_call(200, {"Links": {"ResourceBlocks": members}})
        self.assertEqual(["DeviceBlock-3", "DeviceBlock-4"], self.usp.port.link)


class TestsSavePortData(TestCase):
    """Test class for save_port_data method."""

    def setUp(self):
        err = _ErrorCtrl()
        req = _HttpRequests(_DEFAULT_SPECIFIC_DATA, err)
        self.usp = _PortDataUSP("ComputeBlock-1", req)

    def _mock_call(self, data, logmsgs=None, errors=None):
        with mock.patch("plugins.fm.reference.plugin.log.warning") as log_func:
            with mock.patch("requests.get") as req_func:
                req_func.side_effect = [_mock_response(x, json.dumps(y)) for x, y in data]
                self.usp.save_port_data()
                if errors:
                    self.assertEqual(errors, self.usp.err.error)
                if logmsgs:
                    log_func.assert_has_calls([mock.call(x) for x in logmsgs])

    def test_save_port_data_resource_block_is_none(self):
        """Test when the resource block schema cannot be retrieved."""
        errors = [_ErrorType.ERROR_CONTROL]
        errmsg = "Server error case response status code is 500"
        self._mock_call([(500, {"message": "Internal Server Error"})], [errmsg], errors)
        self.assertIsNone(self.usp.port.cpu_manufacturer)
        self.assertIsNone(self.usp.port.cpu_model)
        self.assertIsNone(self.usp.port.cpu_serial_number)
        self.assertIsNone(self.usp.zone)

    def test_save_port_data_processor_not_found(self):
        """Test when a processor is not found."""
        errors = [_ErrorType.ERROR_CONTROL]
        zone = {"Zones": [{"@odata.id": "CompositionService/ResourceZones/zone"}]}
        data = {"Links": zone, "Processors": []}
        errmsg = f"ComputeBlock-1 usp processor not found\n{data}"
        self._mock_call([(200, data)], [errmsg], errors)
        self.assertIsNone(self.usp.port.cpu_manufacturer)
        self.assertIsNone(self.usp.port.cpu_model)
        self.assertIsNone(self.usp.port.cpu_serial_number)
        self.assertEqual(self.usp.zone, "zone")

    def test_save_port_data_processor_exist(self):
        """Test when various errors occurred but the processor was found."""
        data1 = (200, {"Processors": [{}] + [{"@odata.id": x} for x in ["p1", "p2", "p3", "p4"]]})
        data2 = (500, {"message": "Internal Server Error"})
        data3 = (200, {"NotProcessorType": "CPU"})
        data4 = (200, {"ProcessorType": "GPU"})
        data5 = (200, _DEFAULT_PROCESSOR_DATA)
        self._mock_call([data1, data2, data3, data4, data5])
        self.assertEqual("manufacturer", self.usp.port.cpu_manufacturer)
        self.assertEqual("model", self.usp.port.cpu_model)
        self.assertEqual("serial number", self.usp.port.cpu_serial_number)

    def test_save_port_data_manufacturer_is_none(self):
        """Test when there is no manufacturer information in the processor schema."""
        cpu_data = {k: v for k, v in _DEFAULT_PROCESSOR_DATA.items() if k != "Manufacturer"}
        self._mock_call([(200, {"Processors": [{"@odata.id": "path1"}]}), (200, cpu_data)])
        self.assertIsNone(self.usp.port.cpu_manufacturer)
        self.assertEqual("model", self.usp.port.cpu_model)
        self.assertEqual("serial number", self.usp.port.cpu_serial_number)

    def test_save_port_data_manufacturer_is_not_string(self):
        """Test when the manufacturer in the processor schema is not a string."""
        cpu_data = copy.deepcopy(_DEFAULT_PROCESSOR_DATA)
        cpu_data["Manufacturer"] = 0  # type: ignore
        data = [(200, {"Processors": [{"@odata.id": "path1"}]}), (200, cpu_data)]
        errmsg = f"Validation error {cpu_data}"
        self._mock_call(data, [errmsg], [_ErrorType.ERROR_INTERNAL])
        self.assertIsNone(self.usp.port.cpu_manufacturer)

    def test_save_port_data_model_is_none(self):
        """Test when there is no model information in the processor schema."""
        cpu_data = {k: v for k, v in _DEFAULT_PROCESSOR_DATA.items() if k != "Model"}
        self._mock_call([(200, {"Processors": [{"@odata.id": "path1"}]}), (200, cpu_data)])
        self.assertIsNone(self.usp.port.cpu_model)
        self.assertEqual("manufacturer", self.usp.port.cpu_manufacturer)
        self.assertEqual("serial number", self.usp.port.cpu_serial_number)

    def test_save_port_data_model_is_not_string(self):
        """Test when the model in the processor schema is not a string."""
        cpu_data = copy.deepcopy(_DEFAULT_PROCESSOR_DATA)
        cpu_data["Model"] = {}  # type: ignore
        data = [(200, {"Processors": [{"@odata.id": "path1"}]}), (200, cpu_data)]
        errmsg = f"Validation error {cpu_data}"
        self._mock_call(data, [errmsg], [_ErrorType.ERROR_INTERNAL])
        self.assertIsNone(self.usp.port.cpu_model)

    def test_save_port_data_serial_number_is_none(self):
        """Test when there is no serial number information in the processor schema."""
        cpu_data = {k: v for k, v in _DEFAULT_PROCESSOR_DATA.items() if k != "SerialNumber"}
        self._mock_call([(200, {"Processors": [{"@odata.id": "path1"}]}), (200, cpu_data)])
        self.assertIsNone(self.usp.port.cpu_serial_number)
        self.assertEqual("manufacturer", self.usp.port.cpu_manufacturer)
        self.assertEqual("model", self.usp.port.cpu_model)

    def test_save_port_data_serial_number_is_not_string(self):
        """Test when the serial number in the processor schema is not a string."""
        cpu_data = copy.deepcopy(_DEFAULT_PROCESSOR_DATA)
        cpu_data["SerialNumber"] = []  # type: ignore
        data = [(200, {"Processors": [{"@odata.id": "path1"}]}), (200, cpu_data)]
        errmsg = f"Validation error {cpu_data}"
        self._mock_call(data, [errmsg], [_ErrorType.ERROR_INTERNAL])
        self.assertIsNone(self.usp.port.cpu_serial_number)

    def test_save_port_data_normal(self):
        """Test when all information is successfully retrieved."""
        rbdata = {"Processors": [{"@odata.id": "path1"}]}
        self._mock_call([(200, rbdata), (200, _DEFAULT_PROCESSOR_DATA)])
        self.assertEqual("manufacturer", self.usp.port.cpu_manufacturer)
        self.assertEqual("model", self.usp.port.cpu_model)
        self.assertEqual("serial number", self.usp.port.cpu_serial_number)


class TestsChangeLink(TestCase):
    """Test class for change_link method."""

    def setUp(self):
        err = _ErrorCtrl()
        req = _HttpRequests(_DEFAULT_SPECIFIC_DATA, err)
        self.usp = _PortDataUSP("ComputeBlock-1", req)

    def test_change_link_failed(self):
        """Test when updating the link fails."""
        self.usp.req.patch = mock.Mock()
        self.usp.req.patch.return_value = None
        self.assertFalse(self.usp.change_link(["DeviceBlock-3", "DeviceBlock-4"]))

    def test_change_link_success(self):
        """Test when updating the link succeeds."""
        self.usp.req.patch = mock.Mock()
        self.usp.req.patch.return_value = {}
        self.assertTrue(self.usp.change_link(["DeviceBlock-3", "DeviceBlock-4"]))
