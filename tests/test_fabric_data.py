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
Test program for _FabricData class
"""

import json
from unittest import TestCase, mock
from test_http_requests import _DEFAULT_SPECIFIC_DATA, _mock_response
from plugins.fm.reference.plugin import _ErrorCtrl, _ErrorType, _FabricData, _HttpRequests


class TestInit(TestCase):
    """Test class for constructor."""

    def setUp(self):
        err = _ErrorCtrl()
        self.req = _HttpRequests(_DEFAULT_SPECIFIC_DATA, err)

    def test___init___normal(self):
        """Test for the initialization of instance variables."""
        fabric = _FabricData(self.req)
        self.assertIsInstance(fabric.err, _ErrorCtrl)
        self.assertIsInstance(fabric.req, _HttpRequests)
        self.assertEqual([], fabric.uspids)
        self.assertEqual([], fabric.dspids)
        self.assertEqual([], fabric.swtids)


class TestGetPortIds(TestCase):
    """Test class for get_port_ids method."""

    def setUp(self):
        err = _ErrorCtrl()
        req = _HttpRequests(_DEFAULT_SPECIFIC_DATA, err)
        self.fabric = _FabricData(req)

    def _save_port_ids(self):
        with mock.patch("requests.get") as func:
            blocks = ["ComputeBlock-1", "ComputeBlock-2", "DeviceBlock-3", "DeviceBlock-4"]
            lists = [{"@odata.id": f"CompositionService/ResourceBlocks/{x}"} for x in blocks]
            func.return_value = _mock_response(200, json.dumps({"Members": lists}))
            self.fabric.save_and_get_port_ids()

    def test_get_port_ids_port_type_is_usp_no_data(self):
        """Test when there is no USP data available."""
        self.assertEqual([], self.fabric.get_port_ids("USP"))

    def test_get_port_ids_port_type_is_dsp_no_data(self):
        """Test when there is no DSP data available."""
        self.assertEqual([], self.fabric.get_port_ids("DSP"))

    def test_get_port_ids_port_type_is_not_specifies_no_data(self):
        """Test when neither data is available."""
        self.assertEqual([], self.fabric.get_port_ids())

    def test_get_port_ids_port_type_is_usp_set_data(self):
        """Test when USP data exists."""
        self._save_port_ids()
        self.assertEqual(["ComputeBlock-1", "ComputeBlock-2"], self.fabric.get_port_ids("USP"))

    def test_get_port_ids_port_type_is_dsp_set_data(self):
        """Test when DSP data exists."""
        self._save_port_ids()
        self.assertEqual(["DeviceBlock-3", "DeviceBlock-4"], self.fabric.get_port_ids("DSP"))

    def test_get_port_ids_port_type_is_not_specifies_set_data(self):
        """Test when both sets of data are available."""
        self._save_port_ids()
        expected = ["ComputeBlock-1", "ComputeBlock-2", "DeviceBlock-3", "DeviceBlock-4"]
        self.assertEqual(expected, self.fabric.get_port_ids())


class TestGetSwitchIds(TestCase):
    """Test class for get_switch_ids method."""

    def setUp(self):
        err = _ErrorCtrl()
        req = _HttpRequests(_DEFAULT_SPECIFIC_DATA, err)
        self.fabric = _FabricData(req)

    def test_get_switch_ids_no_data(self):
        """Test when there is no switch data available."""
        self.assertEqual([], self.fabric.get_switch_ids())

    def test_get_switch_ids_set_data(self):
        """Test when switch data is available."""
        with mock.patch("requests.get") as func:
            switches = ["SWITCH-4001", "SWITCH-4002"]
            lists = [{"@odata.id": f"Fabrics/CXL/Switches/{x}"} for x in switches]
            func.return_value = _mock_response(200, json.dumps({"Members": lists}))
            self.fabric.save_and_get_switch_ids()
        self.assertEqual(["SWITCH-4001", "SWITCH-4002"], self.fabric.get_switch_ids())


class TestSaveAndGetPortIds(TestCase):
    """Test class for save_and_get_port_ids method."""

    def setUp(self):
        err = _ErrorCtrl()
        req = _HttpRequests(_DEFAULT_SPECIFIC_DATA, err)
        self.fabric = _FabricData(req)

    def _mock_call(self, status_code, data, expected, logmsg=None):
        with mock.patch("plugins.fm.reference.plugin.log.warning") as log_func:
            with mock.patch("requests.get") as req_func:
                req_func.return_value = _mock_response(status_code, json.dumps(data))
                resp = self.fabric.save_and_get_port_ids()
                self.assertEqual(expected[0] + expected[1], resp)
                self.assertEqual(expected[0], self.fabric.uspids)
                self.assertEqual(expected[1], self.fabric.dspids)
                if logmsg:
                    log_func.assert_called_with(logmsg)
                    self.assertEqual([_ErrorType.ERROR_CONTROL], self.fabric.err.error)
                else:
                    log_func.assert_not_called()
                    self.assertEqual([], self.fabric.err.error)

    def test_save_and_get_port_ids_blocks_is_none(self):
        """Test when the resource block schema cannot be retrieved."""
        errmsg = "Server error case response status code is 500"
        self._mock_call(500, {"message": "Internal Server Error"}, ([], []), errmsg)

    def test_save_and_get_port_ids_odata_not_found(self):
        """Test when the format of the resource block schema is incorrect."""
        uspids = ["ComputeBlock-1", "ComputeBlock-2"]
        dspids = ["DeviceBlock-3", "DeviceBlock-4"]
        members = [{"@odata.id": f"CompositionService/ResourceBlocks/{x}"} for x in uspids + dspids]
        members.append({})
        errmsg = "Invalid format {}"
        self._mock_call(200, {"Members": members}, (uspids, dspids), errmsg)

    def test_save_and_get_port_ids_blocks_not_found(self):
        """Test when the resource block does not exist."""
        errmsg = "No resource block found from ResourceBlocks\n{'Members': []}"
        self._mock_call(200, {"Members": []}, ([], []), errmsg)

    def test_save_and_get_port_ids_normal(self):
        """Test when successfully returning the list of resource blocks."""
        uspids = ["ComputeBlock-1", "ComputeBlock-2"]
        dspids = ["DeviceBlock-3", "DeviceBlock-4"]
        members = [{"@odata.id": f"CompositionService/ResourceBlocks/{x}"} for x in uspids + dspids]
        self._mock_call(200, {"Members": members}, (uspids, dspids))


class TestSaveAndGetSwitchIds(TestCase):
    """Test class for save_and_get_switch_ids method."""

    def setUp(self):
        err = _ErrorCtrl()
        req = _HttpRequests(_DEFAULT_SPECIFIC_DATA, err)
        self.fabric = _FabricData(req)

    def _mock_call(self, status_code, data, expected, logmsg=None):
        with mock.patch("plugins.fm.reference.plugin.log.warning") as log_func:
            with mock.patch("requests.get") as req_func:
                req_func.return_value = _mock_response(status_code, json.dumps(data))
                resp = self.fabric.save_and_get_switch_ids()
                self.assertEqual(expected, resp)
                self.assertEqual(resp, self.fabric.swtids)
                if logmsg:
                    log_func.assert_called_with(logmsg)
                    self.assertEqual([_ErrorType.ERROR_CONTROL], self.fabric.err.error)
                else:
                    log_func.assert_not_called()
                    self.assertEqual([], self.fabric.err.error)

    def test_save_and_get_switch_ids_switches_is_none(self):
        """Test when the switch cannot be retrieved."""
        errmsg = "Server error case response status code is 500"
        self._mock_call(500, {"message": "Internal Server Error"}, [], errmsg)

    def test_save_and_get_switch_ids_odata_not_found(self):
        """Test when the format of the switch is incorrect."""
        switches = ["SWITCH-4001", "SWITCH-4002"]
        members = [{"@odata.id": f"Fabrics/CXL/Switches/{x}"} for x in switches]
        members.append({})
        self._mock_call(200, {"Members": members}, switches, "Invalid format {}")

    def test_save_and_get_switch_ids_switches_not_found(self):
        """Test when the switch does not exist."""
        errmsg = "No switch found from Switches\n{'Members': []}"
        self._mock_call(200, {"Members": []}, [], errmsg)

    def test_save_and_get_switch_ids_normal(self):
        """Test when successfully returning the list of switches."""
        switches = ["SWITCH-4001", "SWITCH-4002", "SWITCH-4003"]
        members = [{"@odata.id": f"Fabrics/CXL/Switches/{x}"} for x in switches]
        self._mock_call(200, {"Members": members}, switches)


class TestStaticMethods(TestCase):
    """Test class for port_id_usp, uspid2system, system2uspid, odata2id methods."""

    def test_port_is_usp_is_true(self):
        """Test for port_is_usp method (true)."""
        self.assertTrue(_FabricData.port_is_usp("ComputeBlock-1"))

    def test_port_is_usp_is_false(self):
        """Test for port_is_usp method (false)."""
        self.assertFalse(_FabricData.port_is_usp("DeviceBlock-1"))

    def test_uspid2system(self):
        """Test for uspid2system method."""
        self.assertEqual("Systems/System-1", _FabricData.uspid2system("ComputeBlock-1"))

    def test_system2uspid(self):
        """Test for system2uspid method."""
        self.assertEqual("ComputeBlock-1", _FabricData.system2uspid("System-1"))

    def test_odata2id_not_found(self):
        """Test for odata2id method (not found)."""
        err = _ErrorCtrl()
        with mock.patch("plugins.fm.reference.plugin.log.warning") as log_func:
            data = _FabricData.odata2id({"not@odata.id": "System/System-1"}, err)
            self.assertIsNone(data)
            log_func.assert_called_with("Invalid format {'not@odata.id': 'System/System-1'}")
        self.assertEqual([_ErrorType.ERROR_CONTROL], err.error)

    def test_odata2id_normal(self):
        """Test for odata2id method (found)."""
        err = _ErrorCtrl()
        with mock.patch("plugins.fm.reference.plugin.log.warning") as log_func:
            data = _FabricData.odata2id({"@odata.id": "System/System-1"}, err)
            self.assertEqual(data, "System-1")
            log_func.assert_not_called()
        self.assertEqual([], err.error)
