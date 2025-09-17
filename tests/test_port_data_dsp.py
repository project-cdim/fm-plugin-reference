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
Test program for _PortDataDSP class
"""

import json
from unittest import TestCase, mock
from test_http_requests import _DEFAULT_SPECIFIC_DATA, _mock_response
from test_port_data import _DEFAULT_NONE_PORT_MEMBERS
from plugins.fm.reference.plugin import _ErrorCtrl, _ErrorType, _HTTPRequests, _PortDataDSP


_LOG_PREFIX = "WARNING:plugins.fm.reference.plugin:"


class TestsInit(TestCase):
    """Test class for constructor."""

    def setUp(self):
        err = _ErrorCtrl()
        self.req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, err)

    def test___init___normal(self):
        """Test for the initialization of instance variables."""
        prt = _PortDataDSP("DeviceBlock-1", self.req)
        self.assertEqual("DeviceBlock-1", prt.pid)
        self.assertEqual("DeviceBlock-1", prt.port.id)
        for member in _DEFAULT_NONE_PORT_MEMBERS:
            self.assertIsNone(getattr(prt.port, member))
        self.assertEqual("DSP", prt.port.switch_port_type)
        self.assertEqual({}, prt.port.device_keys)
        self.assertEqual({}, prt.port.port_keys)


class TestsSaveLinkDSP(TestCase):
    """Test class for save_link method."""

    def setUp(self):
        err = _ErrorCtrl()
        req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, err)
        self.dsp = _PortDataDSP("DeviceBlock-3", req)
        self.port_ids = ["ComputeBlock-1", "ComputeBlock-2", "DeviceBlock-3", "DeviceBlock-4"]

    def _mock_call(self, status_code, data, logmsg=None):
        with mock.patch("requests.get") as req_func:
            req_func.return_value = _mock_response(status_code, json.dumps(data))
            if logmsg:
                with self.assertLogs(level="WARNING") as _cm:
                    self.dsp.save_link(self.port_ids)
                self.assertEqual(_cm.output, [f"{_LOG_PREFIX}{logmsg}"])
                self.assertEqual([_ErrorType.ERROR_CONTROL], self.dsp.err.error)
                self.assertIsNone(self.dsp.port.link)
            else:
                with self.assertNoLogs(level="WARNING"):
                    self.dsp.save_link(self.port_ids)
                self.assertEqual([], self.dsp.err.error)

    def test_save_link_rbdata_is_none(self):
        """Test when the resource block schema cannot be retrieved."""
        errmsg = "Server error case response status code is 500"
        self._mock_call(500, {"message": "Internal Server Error"}, errmsg)

    def test_save_link_odataid_not_found(self):
        """Test when the format of the resource block schema is incorrect."""
        members = [{"@odata.id": "Systems/System-1"}, {}]
        self._mock_call(200, {"Links": {"ComputerSystems": members}}, "Invalid format {}")

    def test_save_link_inconsistent_ids(self):
        """Test for inconsistencies in links of the retrieved resource block schema."""
        errmsg = f"Invalid resource block ComputeBlock-3 not in {self.port_ids}"
        members = [{"@odata.id": "Systems/System-3"}]
        self._mock_call(200, {"Links": {"ComputerSystems": members}}, errmsg)

    def test_save_link_no_data(self):
        """Test when the resource block does not exist."""
        self._mock_call(200, {"Links": {"ComputerSystems": []}})
        self.assertEqual([], self.dsp.port.link)

    def test_save_link_one_data(self):
        """Test when one link is found."""
        members = [{"@odata.id": "Systems/System-1"}]
        self._mock_call(200, {"Links": {"ComputerSystems": members}})
        self.assertEqual(["ComputeBlock-1"], self.dsp.port.link)

    def test_save_link_two_data(self):
        """Test when multiple links are found."""
        members = [{"@odata.id": "Systems/System-1"}, {"@odata.id": "Systems/System-2"}]
        rbdata = {"Links": {"ComputerSystems": members}}
        self._mock_call(200, rbdata, f"DeviceBlock-3 dsp link failed\n{rbdata}")


class TestsSavePortData1(TestCase):
    """Test class for save_port_data method."""

    def setUp(self):
        err = _ErrorCtrl()
        req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, err)
        self.dsp = _PortDataDSP("DeviceBlock-3", req)

    def _mock_call(self, data, logmsgs=None, errors=None):
        with mock.patch("requests.get") as req_func:
            req_func.side_effect = [_mock_response(x, json.dumps(y)) for x, y in data]
            if logmsgs:
                with self.assertLogs(level="WARNING") as _cm:
                    self.dsp.save_port_data()
                self.assertEqual(_cm.output, [f"{_LOG_PREFIX}{x}" for x in logmsgs])
            else:
                self.dsp.save_port_data()
            if errors:
                self.assertEqual(errors, self.dsp.err.error)

    def _check_none(self, members: list):
        for member in members:
            self.assertIsNone(getattr(self.dsp.port, member))

    def _check_all_data_not_set(self):
        members = [
            "device_type",
            "pcie_device_serial_number",
            "pcie_device_id",
            "pcie_vendor_id",
            "pci_class_code",
            "capacity",
        ]
        self._check_none(members)
        self.assertEqual({}, self.dsp.port.device_keys)

    def test_save_port_data_resource_block_is_none(self):
        """Test when the resource block schema cannot be retrieved."""
        errors = [_ErrorType.ERROR_CONTROL]
        errmsg = "Server error case response status code is 500"
        self._mock_call([(500, {"message": "Internal Server Error"})], [errmsg], errors)
        self._check_all_data_not_set()
        self.assertIsNone(self.dsp.zone)

    def test_save_port_data_no_device_found(self):
        """Test for when no devices are found."""
        errors = [_ErrorType.ERROR_CONTROL]
        rbdata = {"Links": {"Zones": [{"@odata.id": "CompositionService/ResourceZones/zone"}]}}
        errmsg = f"DeviceBlock-3 dsp target device count is 0\n{rbdata}"
        self._mock_call([(200, rbdata)], [errmsg], errors)
        self._check_all_data_not_set()
        self.assertEqual("zone", self.dsp.zone)

    def test_save_port_data_two_devices_found(self):
        """Test for when multiple devices are found."""
        errors = [_ErrorType.ERROR_CONTROL]
        rbdata = {"Memory": [{"@odata.id": "path1"}, {"@odata.id": "path2"}]}
        errmsg = f"DeviceBlock-3 dsp target device count is 2\n{rbdata}"
        self._mock_call([(200, rbdata)], [errmsg], errors)
        self._check_all_data_not_set()

    def test_save_port_data_pciedev_is_none(self):
        """Test for when retrieving the PCIe device schema fails."""
        errors = [_ErrorType.ERROR_CONTROL]
        errmsg = "Server error case response status code is 500"
        data1 = (200, {"Processors": [{"@odata.id": "Processors/PROC-0001"}]})
        data2 = (500, {"message": "Internal Server Error"})
        self._mock_call([data1, data2], [errmsg], errors)
        self._check_all_data_not_set()

    def test_save_port_data_pciefunc_is_none(self):
        """Test for when retrieving the PCIe function schema fails."""
        errors = [_ErrorType.ERROR_CONTROL]
        errmsg = "Server error case response status code is 500"
        data1 = (200, {"Drives": [{"@odata.id": "Drives/DRI-2001"}]})
        data2 = (200, {"SerialNumber": "123456789abcdef0"})
        data3 = (500, {"message": "Internal Server Error"})
        self._mock_call([data1, data2, data3], [errmsg], errors)
        members = ["pcie_device_id", "pcie_vendor_id", "pci_class_code", "capacity"]
        self._check_none(members)
        self.assertDictEqual({}, self.dsp.port.device_keys)
        self.assertEqual("123456789abcdef0", self.dsp.port.pcie_device_serial_number)
        self.assertEqual("PCIe", self.dsp.port.device_type)

    def _check_pcie_function(self, pcief_data: dict):
        data1 = (200, {"Drives": [{"@odata.id": "Drives/DRI-2001"}]})
        data2 = (200, {"SerialNumber": "123456789abcdef0"})
        data3 = (200, pcief_data)
        self._mock_call([data1, data2, data3], [], [])
        self.assertDictEqual({}, self.dsp.port.device_keys)
        self.assertEqual("123456789abcdef0", self.dsp.port.pcie_device_serial_number)
        self.assertEqual("PCIe", self.dsp.port.device_type)
        self.assertIsNone(self.dsp.port.capacity)

    def test_save_port_data_device_id_is_none(self):
        """Test for when the PCIe function schema does not contain a DeviceId."""
        pciefunc = {"VendorId": "5678", "ClassCode": "0x9abcde"}
        self._check_pcie_function(pciefunc)
        self.assertIsNone(self.dsp.port.pcie_device_id)

    def test_device_id_is_not_string(self):
        """Test for when the DeviceId in the PCIe function schema is not a string."""
        pciefunc = {"DeviceId": 0x1234, "VendorId": "5678", "ClassCode": "0x9abcde"}
        self._check_pcie_function(pciefunc)
        self.assertIsNone(self.dsp.port.pcie_device_id)

    def test_save_port_data_device_id_is_not_hexadecimal(self):
        """Test for when the VendorId in the PCIe function schema is not a hexadecimal."""
        pciefunc = {"DeviceId": "xxxx", "VendorId": "5678", "ClassCode": "0x9abcde"}
        self._check_pcie_function(pciefunc)
        self.assertIsNone(self.dsp.port.pcie_device_id)

    def test_save_port_data_device_id_length_is_over(self):
        """Test for when the DeviceId string in the PCIe function schema is too long."""
        pciefunc = {"DeviceId": "12345", "VendorId": "5678", "ClassCode": "0x9abcde"}
        self._check_pcie_function(pciefunc)
        self.assertIsNone(self.dsp.port.pcie_device_id)

    def test_save_port_data_vendor_id_is_none(self):
        """Test for when the PCIe function schema does not contain a VendorId."""
        pciefunc = {"DeviceId": "1234", "ClassCode": "0x9abcde"}
        self._check_pcie_function(pciefunc)
        self.assertIsNone(self.dsp.port.pcie_vendor_id)

    def test_save_port_data_vendor_id_is_not_string(self):
        """Test for when the VendorId in the PCIe function schema is not a string."""
        pciefunc = {"DeviceId": "1234", "VendorId": 0x5678, "ClassCode": "0x9abcde"}
        self._check_pcie_function(pciefunc)
        self.assertIsNone(self.dsp.port.pcie_vendor_id)

    def test_save_port_data_vendor_id_is_not_hexadecimal(self):
        """Test for when the DeviceId in the PCIe function schema is not a hexadecimal."""
        pciefunc = {"DeviceId": "1234", "VendorId": "yyyy", "ClassCode": "0x9abcde"}
        self._check_pcie_function(pciefunc)
        self.assertIsNone(self.dsp.port.pcie_vendor_id)

    def test_save_port_data_vendor_id_length_is_over(self):
        """Test for when the VendorId string in the PCIe function schema is too long."""
        pciefunc = {"DeviceId": "1234", "VendorId": "56789", "ClassCode": "0x9abcde"}
        self._check_pcie_function(pciefunc)
        self.assertIsNone(self.dsp.port.pcie_vendor_id)

    def test_save_port_data_class_code_is_none(self):
        """Test for when the PCIe function schema does not contain a ClassCode."""
        pciefunc = {"DeviceId": "1234", "VendorId": "5678"}
        self._check_pcie_function(pciefunc)
        self.assertIsNone(self.dsp.port.pci_class_code)

    def test_save_port_data_class_code_is_not_string(self):
        """Test for when the ClassCode in the PCIe function schema is not a string."""
        pciefunc = {"DeviceId": "1234", "VendorId": "5678", "ClassCode": 0x9ABCDE}
        self._check_pcie_function(pciefunc)
        self.assertIsNone(self.dsp.port.pci_class_code)

    def test_save_port_data_class_code_is_hexadecimal(self):
        """Test for when the ClassCode in the PCIe function schema is not a hexadecimal."""
        pciefunc = {"DeviceId": "1234", "VendorId": "5678", "ClassCode": "0x9abcdg"}
        self._check_pcie_function(pciefunc)
        self.assertIsNone(self.dsp.port.pci_class_code)

    def test_save_port_data_class_code_length_is_over(self):
        """Test for when the ClassCode string in the PCIe function schema is too long."""
        pciefunc = {"DeviceId": "1234", "VendorId": "5678", "ClassCode": "0x9abcdef"}
        self._check_pcie_function(pciefunc)
        self.assertIsNone(self.dsp.port.pci_class_code)


class TestsSavePortData2(TestCase):
    """Test class for save_port_data method."""

    def setUp(self):
        err = _ErrorCtrl()
        req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, err)
        self.dsp = _PortDataDSP("DeviceBlock-3", req)

    def _mock_call(self, data, logmsgs=None, errors=None):
        with mock.patch("requests.get") as req_func:
            req_func.side_effect = [_mock_response(x, json.dumps(y)) for x, y in data]
            if logmsgs:
                with self.assertLogs(level="WARNING") as _cm:
                    self.dsp.save_port_data()
                self.assertEqual(_cm.output, [f"{_LOG_PREFIX}{x}" for x in logmsgs])
            else:
                self.dsp.save_port_data()
            if errors:
                self.assertEqual(errors, self.dsp.err.error)

    def _check_none(self, members: list):
        for member in members:
            self.assertIsNone(getattr(self.dsp.port, member))

    def _check_all_data_not_set(self):
        members = [
            "device_type",
            "pcie_device_serial_number",
            "pcie_device_id",
            "pcie_vendor_id",
            "pci_class_code",
            "capacity",
        ]
        self._check_none(members)
        self.assertEqual({}, self.dsp.port.device_keys)

    def _check_resource_type(self, resource):
        data1 = (200, resource)
        data2 = (200, {"SerialNumber": "123456789abcdef0"})
        data3 = (200, {"DeviceId": "1234", "VendorId": "5678", "ClassCode": "9abcde"})
        self._mock_call([data1, data2, data3], [], [])
        self.assertDictEqual({}, self.dsp.port.device_keys)
        self.assertEqual("123456789abcdef0", self.dsp.port.pcie_device_serial_number)
        self.assertEqual("PCIe", self.dsp.port.device_type)
        self.assertEqual("1234", self.dsp.port.pcie_device_id)
        self.assertEqual("5678", self.dsp.port.pcie_vendor_id)
        self.assertEqual({"base": 0x9A, "sub": 0xBC, "prog": 0xDE}, self.dsp.port.pci_class_code)
        self.assertIsNone(self.dsp.port.capacity)

    def test_save_port_data_processor_device_normal(self):
        """Test for when a processor is found."""
        self._check_resource_type({"Processors": [{"@odata.id": "Processors/PROC-5001"}]})

    def test_save_port_data_ethernet_interface_device_found(self):
        """Test for when a ethernet interface is found."""
        data = {"EthernetInterfaces": [{"@odata.id": "EthernetInterfaces/EI-3001"}]}
        self._check_resource_type(data)

    def test_save_port_data_drive_device_found(self):
        """Test for when a drive is found."""
        self._check_resource_type({"Drives": [{"@odata.id": "Drives/DRI-2001"}]})

    def test_save_port_data_memory_device_is_none(self):
        """Test for when retrieving memory schema fails."""
        errors = [_ErrorType.ERROR_CONTROL]
        errmsg = "Server error case response status code is 500"
        data1 = (200, {"Memory": [{"@odata.id": "Memory/MEM-1001"}]})
        data2 = (200, {"SerialNumber": None})
        data3 = (500, {"message": "Internal Server Error"})
        self._mock_call([data1, data2, data3], [errmsg], errors)
        self._check_all_data_not_set()

    def _check_capacity(self, cxl, capacity=None):
        data1 = (200, {"Memory": [{"@odata.id": "Memory/MEM-1001"}]})
        data2 = (200, {"SerialNumber": None})
        data3 = (200, {"SerialNumber": "1234", "CXL": cxl})
        self._mock_call([data1, data2, data3])
        pcies = ["pcie_device_serial_number", "pcie_device_id", "pcie_vendor_id", "pci_class_code"]
        self._check_none(pcies)
        self.assertEqual({"SimulatedDeviceID": "1234"}, self.dsp.port.device_keys)
        if capacity:
            self.assertEqual(capacity, self.dsp.port.capacity)
            self.assertEqual("CXL-Type3", self.dsp.port.device_type)
        else:
            self._check_none(["capacity", "device_type"])

    def test_save_port_data_memory_device_has_not_cxl(self):
        """Test for when CXL is not present in the memory schema."""
        self._check_capacity(None)

    def test_save_port_data_memory_device_volatile_is_none(self):
        """Test for when the memory schema does not have CXL/StagedNonVolatileSizeMiB."""
        capacity = {"volatile": 0, "persistent": 1048576, "total": 1048576}
        self._check_capacity({"StagedNonVolatileSizeMiB": 1}, capacity)

    def test_save_port_data_memory_device_volatile_is_not_int(self):
        """Test for when the CXL/StagedNonVolatileSizeMiB in the memory schema is not a number."""
        cxl = {"StagedNonVolatileSizeMiB": 1, "StagedVolatileSizeMiB": "2"}
        capacity = {"volatile": 0, "persistent": 1048576, "total": 1048576}
        self._check_capacity(cxl, capacity)

    def test_save_port_data_memory_device_volatile_is_negative(self):
        """Test for when the StagedNonVolatileSizeMiB in the memory schema is negative."""
        self._check_capacity({"StagedNonVolatileSizeMiB": 1, "StagedVolatileSizeMiB": -2})

    def test_save_port_data_memory_device_persistent_is_none(self):
        """Test for when the memory schema does not have CXL/StagedVolatileSizeMiB."""
        capacity = {"volatile": 2097152, "persistent": 0, "total": 2097152}
        self._check_capacity({"StagedVolatileSizeMiB": 2}, capacity)

    def test_save_port_data_memory_device_persistent_is_not_int(self):
        """Test for when the CXL/StagedVolatileSizeMiB in the memory schema is not a number."""
        cxl = {"StagedNonVolatileSizeMiB": "1", "StagedVolatileSizeMiB": 2}
        capacity = {"volatile": 2097152, "persistent": 0, "total": 2097152}
        self._check_capacity(cxl, capacity)

    def test_save_port_data_memory_device_persistent_is_negative(self):
        """Test for when the StagedVolatileSizeMiB in the memory schema is negative."""
        self._check_capacity({"StagedNonVolatileSizeMiB": -1, "StagedVolatileSizeMiB": 2})

    def test_save_port_data_memory_device_total_is_zero(self):
        """Test for when size information is missing in the CXL of the memory schema."""
        self._check_capacity({})

    def test_save_port_data_memory_device_normal(self):
        """Test for when a memory is found."""
        cxl = {"StagedNonVolatileSizeMiB": 1, "StagedVolatileSizeMiB": 2}
        capacity = {"volatile": 2097152, "persistent": 1048576, "total": 3145728}
        self._check_capacity(cxl, capacity)
