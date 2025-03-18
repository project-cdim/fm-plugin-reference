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
Test program for FmPlugin class
"""

import typing
from unittest import TestCase, mock
import app.common.basic_exceptions as exc
from app.common.utils.fm_plugin_base import FmPortData, FmSwitchData
from test_http_requests import _DEFAULT_SPECIFIC_DATA
from plugins.fm.reference.plugin import _ErrorCtrl, _FabricData, _HttpRequests, FmPlugin


class TestInit(TestCase):
    """Test class for constructor."""

    def setUp(self):
        self.err = _ErrorCtrl()
        self.req = _HttpRequests(None, self.err)

    def test___init___normal(self):
        """Test for the initialization of instance variables."""
        fmp = FmPlugin()
        self.assertIsInstance(fmp.err, _ErrorCtrl)
        self.assertIsInstance(fmp.req, _HttpRequests)
        self.assertIsInstance(fmp.fabric, _FabricData)


class TestGetPortInfo(TestCase):
    """Test class for get_port_info method."""

    def setUp(self):
        self.fmp = FmPlugin(_DEFAULT_SPECIFIC_DATA)
        self.fmp.fabric = mock.Mock()
        self.fmp.fabric.save_and_get_port_ids.return_value = ["ComputeBlock-1", "DeviceBlock-2"]
        self.fmp.fabric.save_and_get_switch_ids.return_value = ["SWITCH-4001"]
        self.fmp.fabric.port_is_usp.side_effect = _FabricData.port_is_usp

    def test_get_port_info_port_ids_not_found(self):
        """Test when no port ids are found."""
        assert isinstance(self.fmp.fabric.save_and_get_port_ids, mock.Mock)
        self.fmp.fabric.save_and_get_port_ids.return_value = []
        with self.assertRaises(exc.InternalHwControlError):
            self.fmp.get_port_info()

    def test_get_port_info_switch_ids_not_found(self):
        """Test when no switch ids are found."""
        assert isinstance(self.fmp.fabric.save_and_get_switch_ids, mock.Mock)
        self.fmp.fabric.save_and_get_switch_ids.return_value = []
        with self.assertRaises(exc.InternalHwControlError):
            self.fmp.get_port_info()

    def test_get_port_info_target_id_not_found(self):
        """Test when the specified target_id does not exist."""
        with self.assertRaises(exc.ResourceNotFoundHwControlError):
            self.fmp.get_port_info("Block-3")

    def test_get_port_info_target_id_is_usp(self):
        """Test when the specified target_id exists in USP."""
        data = self.fmp.get_port_info("ComputeBlock-1")
        self.assertEqual(1, len(data))
        self.assertIsInstance(data["data"], list)
        self.assertEqual(1, len(data["data"]))
        self.assertIsInstance(data["data"][0], FmPortData)
        self.assertEqual("ComputeBlock-1", data["data"][0].id)
        self.assertEqual("USP", data["data"][0].switch_port_type)

    def test_get_port_info_target_id_is_dsp(self):
        """Test when the specified target_id exists in DSP."""
        data = self.fmp.get_port_info("DeviceBlock-2")
        self.assertEqual(1, len(data))
        self.assertIsInstance(data["data"], list)
        self.assertEqual(1, len(data["data"]))
        self.assertIsInstance(data["data"][0], FmPortData)
        self.assertEqual("DeviceBlock-2", data["data"][0].id)
        self.assertEqual("DSP", data["data"][0].switch_port_type)

    def test_get_port_info_target_id_not_specifies(self):
        """Test when the target_id is not specified."""
        data = self.fmp.get_port_info()
        self.assertEqual(1, len(data))
        self.assertIsInstance(data["data"], list)
        self.assertEqual(2, len(data["data"]))
        self.assertIsInstance(data["data"][0], FmPortData)
        self.assertIsInstance(data["data"][1], FmPortData)
        self.assertEqual("ComputeBlock-1", data["data"][0].id)
        self.assertEqual("DeviceBlock-2", data["data"][1].id)


class TestGetSwitchInfo(TestCase):
    """Test class for get_switch_info method."""

    def setUp(self):
        self.fmp = FmPlugin(_DEFAULT_SPECIFIC_DATA)
        self.fmp.fabric.save_and_get_switch_ids = mock.Mock()
        self.fmp.fabric.save_and_get_switch_ids.return_value = ["SWITCH-4001", "SWITCH-4002"]

    def test_get_switch_info_switch_ids_not_found(self):
        """Test when no switch ids are found."""
        assert isinstance(self.fmp.fabric.save_and_get_switch_ids, mock.Mock)
        self.fmp.fabric.save_and_get_switch_ids.return_value = []
        with self.assertRaises(exc.InternalHwControlError):
            self.fmp.get_switch_info()

    def test_get_switch_info_switch_id_not_found(self):
        """Test when the specified switch_id does not exist."""
        with self.assertRaises(exc.SwitchNotFoundHwControlError):
            self.fmp.get_switch_info("SWITCH-4003")

    def test_get_switch_info_switch_id_found(self):
        """Test when the specified switch_id exist."""
        data = self.fmp.get_switch_info("SWITCH-4001")
        self.assertEqual(1, len(data))
        self.assertEqual(1, len(data["data"]))
        self.assertIsInstance(data["data"], list)
        self.assertEqual("SWITCH-4001", data["data"][0].switch_id)

    def test_get_switch_info_switch_id_not_specifies(self):
        """Test when the switch_id is not specified."""
        data = self.fmp.get_switch_info()
        self.assertEqual(1, len(data))
        self.assertIsInstance(data["data"], list)
        self.assertEqual(2, len(data["data"]))
        self.assertIsInstance(data["data"][0], FmSwitchData)
        self.assertIsInstance(data["data"][1], FmSwitchData)
        self.assertEqual("SWITCH-4001", data["data"][0].switch_id)
        self.assertEqual("SWITCH-4002", data["data"][1].switch_id)


class TestConnect(TestCase):
    """Test class for connect method."""

    def setUp(self):
        self.fmp = FmPlugin(_DEFAULT_SPECIFIC_DATA)
        self.dsplink_result = []
        self.usplink_result = []
        self.fmp.fabric = mock.Mock()
        self.fmp.fabric.save_and_get_port_ids.return_value = self._get_port_ids()
        self.fmp.fabric.save_and_get_switch_ids.return_value = ["SWITCH-4001"]
        self.fmp.fabric.get_port_ids.side_effect = self._get_port_ids
        self.fmp.req.get = mock.Mock()
        self.fmp.req.get.side_effect = self._http_requests_get

    def _get_port_ids(self, port_type: typing.Literal["USP", "DSP"] | None = None) -> list:
        if port_type == "USP":
            return ["ComputeBlock-1", "ComputeBlock-2"]
        if port_type == "DSP":
            return ["DeviceBlock-3", "DeviceBlock-4"]
        return ["ComputeBlock-1", "ComputeBlock-2", "DeviceBlock-3", "DeviceBlock-4"]

    def _http_requests_get(self, path: str, data: dict, complete_path: bool = False) -> dict | None:
        if path.startswith("CompositionService/ResourceBlocks"):
            if self.dsplink_result is None:
                return None
            links = [{"@odata.id": f"Systems/System-{x.rsplit('-', maxsplit=1)[-1]}"}
                     for x in self.dsplink_result]
            return {"Links": {"ComputerSystems": links}}
        if path.startswith("Systems/System"):
            if self.usplink_result is None:
                return None
            links = [{"@odata.id": f"ResourceBlocks/{x}"} for x in self.usplink_result]
            return {"Links": {"ResourceBlocks": links}}
        self.fail(f"TP Error unknown {path} called (data={data}, complete_path={complete_path})")
        return None

    def test_connect_port_ids_not_found(self):
        """Test when no port ids are found."""
        assert isinstance(self.fmp.fabric.save_and_get_port_ids, mock.Mock)
        self.fmp.fabric.save_and_get_port_ids.return_value = []
        with self.assertRaises(exc.InternalHwControlError):
            self.fmp.connect("ComputeBlock-1", "DeviceBlock-3")

    def test_connect_both_not_found(self):
        """Test when both the specified cpu_id and device_id do not exist."""
        with self.assertRaises(exc.HostCpuAndDeviceNotFoundHwControlError):
            self.fmp.connect("ComputeBlock-3", "DeviceBlock-5")

    def test_connect_usp_not_found(self):
        """Test when the specified cpu_id does not exist."""
        with self.assertRaises(exc.HostCpuNotFoundHwControlError):
            self.fmp.connect("ComputeBlock-3", "DeviceBlock-3")

    def test_connect_dsp_not_found(self):
        """Test when the specified device_id does not exist."""
        with self.assertRaises(exc.DeviceNotFoundHwControlError):
            self.fmp.connect("ComputeBlock-1", "DeviceBlock-5")

    def test_connect_usp_link_is_none(self):
        """Test when failing to retrieve link information from USP."""
        self.usplink_result = None
        with self.assertRaises(exc.InternalHwControlError):
            self.fmp.connect("ComputeBlock-1", "DeviceBlock-3")

    def test_connect_dsp_link_is_none(self):
        """Test when failing to retrieve link information from DSP."""
        self.dsplink_result = None
        with self.assertRaises(exc.InternalHwControlError):
            self.fmp.connect("ComputeBlock-1", "DeviceBlock-3")

    def test_connect_already_connected(self):
        """Test when a connected cpu_id and device_id are specified."""
        self.fmp.req.patch = mock.Mock()
        self.usplink_result = ["DeviceBlock-3"]
        self.fmp.connect("ComputeBlock-1", "DeviceBlock-3")
        self.fmp.req.patch.assert_not_called()

    def test_connect_dsp_linked_to_anther_usp(self):
        """Test when the specified device_id is connected to a different cpu_id."""
        self.dsplink_result = ["ComputeBlock-2"]
        with self.assertRaises(exc.RequestConflictHwControlError):
            self.fmp.connect("ComputeBlock-1", "DeviceBlock-3")

    def test_connect_update_link_failed(self):
        """Test when the update process fails."""
        self.fmp.req.patch = mock.Mock()
        self.fmp.req.patch.return_value = None
        with self.assertRaises(exc.FmConnectFailureHwControlError):
            self.fmp.connect("ComputeBlock-1", "DeviceBlock-3")

    def test_connect_success(self):
        """Test when the update process succeeds."""
        self.fmp.req.patch = mock.Mock()
        self.fmp.req.patch.return_value = {}
        self.fmp.connect("ComputeBlock-1", "DeviceBlock-3")
        self.fmp.req.patch.assert_called_once()


class TestDisconnect(TestCase):
    """Test class for disconnect method."""

    def setUp(self):
        self.fmp = FmPlugin(_DEFAULT_SPECIFIC_DATA)
        self.fmp.fabric = mock.Mock()
        self.fmp.fabric.save_and_get_port_ids.return_value = self._get_port_ids()
        self.fmp.fabric.save_and_get_switch_ids.return_value = ["SWITCH-4001"]
        self.fmp.fabric.get_port_ids.side_effect = self._get_port_ids
        self.fmp.req.get = mock.Mock()
        self.fmp.req.get.side_effect = self._http_requests_get
        self.dsplink_result = ["ComputeBlock-1"]
        self.usplink_result = ["DeviceBlock-3"]

    def _get_port_ids(self, port_type: typing.Literal["USP", "DSP"] | None = None) -> list:
        if port_type == "USP":
            return ["ComputeBlock-1", "ComputeBlock-2"]
        if port_type == "DSP":
            return ["DeviceBlock-3", "DeviceBlock-4"]
        return ["ComputeBlock-1", "ComputeBlock-2", "DeviceBlock-3", "DeviceBlock-4"]

    def _http_requests_get(self, path: str, data: dict, complete_path: bool = False) -> dict | None:
        if path.startswith("CompositionService/ResourceBlocks"):
            if self.dsplink_result is None:
                return None
            links = [{"@odata.id": f"Systems/System-{x.rsplit('-', maxsplit=1)[-1]}"}
                     for x in self.dsplink_result]
            return {"Links": {"ComputerSystems": links}}
        if path.startswith("Systems/System"):
            if self.usplink_result is None:
                return None
            links = [{"@odata.id": f"ResourceBlocks/{x}"} for x in self.usplink_result]
            return {"Links": {"ResourceBlocks": links}}
        self.fail(f"TP Error unknown {path} called (data={data}, complete_path={complete_path})")
        return None

    def test_disconnect_port_ids_not_found(self):
        """Test when no port ids are found."""
        assert isinstance(self.fmp.fabric.save_and_get_port_ids, mock.Mock)
        self.fmp.fabric.save_and_get_port_ids.return_value = []
        with self.assertRaises(exc.InternalHwControlError):
            self.fmp.disconnect("ComputeBlock-1", "DeviceBlock-3")

    def test_disconnect_both_not_found(self):
        """Test when both the specified cpu_id and device_id do not exist."""
        with self.assertRaises(exc.HostCpuAndDeviceNotFoundHwControlError):
            self.fmp.disconnect("ComputeBlock-3", "DeviceBlock-5")

    def test_disconnect_usp_not_found(self):
        """Test when the specified cpu_id does not exist."""
        with self.assertRaises(exc.HostCpuNotFoundHwControlError):
            self.fmp.disconnect("ComputeBlock-3", "DeviceBlock-3")

    def test_disconnect_dsp_not_found(self):
        """Test when the specified device_id does not exist."""
        with self.assertRaises(exc.DeviceNotFoundHwControlError):
            self.fmp.disconnect("ComputeBlock-1", "DeviceBlock-5")

    def test_disconnect_usp_link_is_none(self):
        """Test when failing to retrieve link information from USP."""
        self.usplink_result = None
        with self.assertRaises(exc.InternalHwControlError):
            self.fmp.disconnect("ComputeBlock-1", "DeviceBlock-3")

    def test_disconnect_dsp_link_is_none(self):
        """Test when failing to retrieve link information from DSP."""
        self.dsplink_result = None
        with self.assertRaises(exc.InternalHwControlError):
            self.fmp.disconnect("ComputeBlock-1", "DeviceBlock-3")

    def test_disconnect_already_disconnected(self):
        """When a device_id in a disconnected state is specified."""
        self.fmp.req.patch = mock.Mock()
        self.dsplink_result = []
        self.fmp.disconnect("ComputeBlock-1", "DeviceBlock-3")
        self.fmp.req.patch.assert_not_called()

    def test_disconnect_dsp_linked_to_anther_usp(self):
        """Test when the specified device_id is connected to a different cpu_id."""
        self.usplink_result = ["DeviceBlock-4"]
        with self.assertRaises(exc.RequestConflictHwControlError):
            self.fmp.disconnect("ComputeBlock-1", "DeviceBlock-3")

    def test_disconnect_update_link_failed(self):
        """Test when the update process fails."""
        self.fmp.req.patch = mock.Mock()
        self.fmp.req.patch.return_value = None
        with self.assertRaises(exc.FmDisconnectFailureHwControlError):
            self.fmp.disconnect("ComputeBlock-1", "DeviceBlock-3")

    def test_disconnect_success(self):
        """Test when the update process succeeds."""
        self.fmp.req.patch = mock.Mock()
        self.fmp.disconnect("ComputeBlock-1", "DeviceBlock-3")
        self.fmp.req.patch.assert_called_once()
