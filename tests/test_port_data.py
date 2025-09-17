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
Test program for _PortData class
"""

from unittest import TestCase
from test_http_requests import _DEFAULT_SPECIFIC_DATA
from plugins.fm.reference.plugin import _ErrorCtrl, _ErrorType, _HTTPRequests, _PortData, _SwitchData


_DEFAULT_NONE_PORT_MEMBERS = [
    "switch_id",
    "switch_port_number",
    "fabric_id",
    "link",
    "device_type",
    "pci_class_code",
    "pcie_vendor_id",
    "pcie_device_id",
    "pcie_device_serial_number",
    "cpu_manufacturer",
    "cpu_model",
    "cpu_serial_number",
    "ltssm_state",
    "capacity",
]
_LOG_PREFIX = "WARNING:plugins.fm.reference.plugin:"


class TestsInit(TestCase):
    """Test class for constructor."""

    def setUp(self):
        err = _ErrorCtrl()
        self.req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, err)

    def test___init___normal(self):
        """Test for the initialization of instance variables."""
        prt = _PortData("test", self.req)
        self.assertEqual("test", prt.pid)
        self.assertEqual("test", prt.port.id)
        self.assertIsNone(prt.zone)
        for member in _DEFAULT_NONE_PORT_MEMBERS + ["switch_port_type"]:
            self.assertIsNone(getattr(prt.port, member))
        self.assertEqual({}, prt.port.device_keys)
        self.assertEqual({}, prt.port.port_keys)


class TestsSaveSwitchData(TestCase):
    """Test class for save_switch_data method."""

    def setUp(self):
        err = _ErrorCtrl()
        req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, err)
        self.prt = _PortData("test", req)
        self.prt.zone = "zone"
        self.swt = _SwitchData("switchid", req)
        self.swt.switch.switch_manufacturer = "sample manufacturer"
        self.swt.switch.switch_model = "sample model"
        self.swt.switch.switch_serial_number = "sample serial number"

    def test_save_switch_data_switch_is_not_string(self):
        """Test when the switch_id of the _SwitchData class is not a string."""
        self.swt.sid = 1  # type: ignore[reportGeneralTypeIssues]
        with self.assertLogs(level="WARNING") as _cm:
            self.prt.save_switch_data(self.swt)
            self.assertIn(f"{_LOG_PREFIX}Validation error 1", _cm.output[0])
        self.assertEqual([_ErrorType.ERROR_INTERNAL], self.prt.err.error)

    def test_save_switch_data_manufacturer_is_none(self):
        """Test when the switch_manufacturer of the _SwitchData class is not set."""
        self.swt.switch.switch_manufacturer = None
        self.prt.save_switch_data(self.swt)
        self.assertIsNone(self.prt.port.fabric_id)

    def test_save_switch_data_model_is_none(self):
        """Test when the switch_model of the _SwitchData class is not set."""
        self.swt.switch.switch_model = None
        self.prt.save_switch_data(self.swt)
        self.assertIsNone(self.prt.port.fabric_id)

    def test_save_switch_data_serial_number_is_none(self):
        """Test when the switch_serial_number of the _SwitchData class is not set."""
        self.swt.switch.switch_serial_number = None
        self.prt.save_switch_data(self.swt)
        self.assertIsNone(self.prt.port.fabric_id)

    def test_save_switch_data_zone_is_none(self):
        """Test when the zone of the _PortData class is not set."""
        self.prt.zone = None
        self.prt.save_switch_data(self.swt)
        self.assertIsNone(self.prt.port.fabric_id)

    def test_save_switch_data_normal(self):
        """Test when all information is successfully retrieved."""
        self.prt.save_switch_data(self.swt)
        fabric_expected = "sample manufacturer-sample model-sample serial number-zone"
        self.assertEqual(fabric_expected, self.prt.port.fabric_id)
        self.assertEqual("switchid", self.prt.port.switch_id)


class TestsSaveZone(TestCase):
    """Test class for save_zone method."""

    def setUp(self):
        err = _ErrorCtrl()
        req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, err)
        self.prt = _PortData("test", req)
        self.zone_path = "/redfish/v1/CompositionService/ResourceZones/"

    def test_save_zone_no_zone(self):
        """Test when no zones exist."""
        self.prt.save_zone({"Links": {"Zones": []}})
        self.assertIsNone(self.prt.zone)

    def test_save_zone_one_zone(self):
        """Test when only one zone exists."""
        self.prt.save_zone({"Links": {"Zones": [{"@odata.id": f"{self.zone_path}zone"}]}})
        self.assertEqual("zone", self.prt.zone)

    def test_save_zone_no_odataid(self):
        """Test when the format of the zone is invalid."""
        self.prt.save_zone({"Links": {"Zones": [{"notodataid": f"{self.zone_path}zone"}]}})
        self.assertIsNone(self.prt.zone)
        self.assertEqual([_ErrorType.ERROR_CONTROL], self.prt.err.error)

    def test_save_zone_two_zones(self):
        """Test when there are two zones."""
        zones = [{"@odata.id": f"{self.zone_path}{x}"} for x in ["zone1", "zone2"]]
        self.prt.save_zone({"Links": {"Zones": zones}})
        self.assertIsNone(self.prt.zone)


class TestsGetPortData(TestCase):
    """Test class for get_port_data method."""

    def setUp(self):
        err = _ErrorCtrl()
        req = _HTTPRequests(_DEFAULT_SPECIFIC_DATA, err)
        self.prt = _PortData("test", req)
        self.prt.zone = "zone"
        self.swt = _SwitchData("switchid", req)
        self.swt.switch.switch_manufacturer = "sample manufacturer"
        self.swt.switch.switch_model = "sample model"
        self.swt.switch.switch_serial_number = "sample serial number"

    def test_get_port_data_not_set(self):
        """Test when the information cannot be retrieved."""
        prt = self.prt.get_port_data()
        self.assertEqual("test", prt.id)
        for member in [
            "switch_id",
            "switch_port_number",
            "switch_port_type",
            "fabric_id",
            "link",
            "device_type",
            "pci_class_code",
            "pcie_vendor_id",
            "pcie_device_id",
            "pcie_device_serial_number",
            "cpu_manufacturer",
            "cpu_model",
            "cpu_serial_number",
            "ltssm_state",
            "capacity",
        ]:
            self.assertIsNone(getattr(prt, member))
        self.assertEqual({}, prt.device_keys)
        self.assertEqual({}, prt.port_keys)

    def test_get_port_data_all_set(self):
        """Test when all information is successfully retrieved."""
        # revisit
        self.prt.save_switch_data(self.swt)
        prt = self.prt.get_port_data()
        self.assertEqual("test", prt.id)
        fabric_expected = "sample manufacturer-sample model-sample serial number-zone"
        self.assertEqual(fabric_expected, prt.fabric_id)
        self.assertEqual("switchid", prt.switch_id)
