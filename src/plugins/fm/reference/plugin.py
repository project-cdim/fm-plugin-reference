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

"""A module defining an FM plugin to work with the reference simulator.
"""

import enum
import json
import threading
import typing
import typing_extensions
import pydantic
import requests

import app.common.basic_exceptions as exc
from app.common.utils.fm_plugin_base import FMPluginBase, FmPortData, FmSwitchData
from app.common.utils.log import LOGGER as log
from app.common.messages import message as msg


class _ErrorType(enum.IntEnum):
    """Defines constants representing types of errors.

    Attributes:
        ERROR_INTERNAL: Internal error within this FM plugin.
           Raise a InternalHwControlError.
        ERROR_INCORRECT: The content of the plugin configuration (file)
           is invalid. Raise a ConfigurationHwControlError.
        ERROR_CONTROL: The state of the reference Redfish simulator is
           different from what is expected.
           Raise a ConfigurationHwControlError.
    """
    ERROR_INTERNAL = enum.auto()
    ERROR_INCORRECT = enum.auto()
    ERROR_CONTROL = enum.auto()


def _debug(out: str):
    """Output log messages at the debug level.

    This is an internal function for debug logging.

    Args:
        out (str): The string you want to output in the log.

    Returns:
        None

    Raises:
        None

    """

    log.debug(str(msg.BaseLogMessage(detail=out).to_json_encodable()), False)


def _get_value_from_data(data: dict, key: str, types: tuple, default=None) -> typing.Any:
    """Retrieve the value of key from data.

    This is an internal function that returns the element of the
    dictionary data if the value for the key matches the type
    specified by types.

    Args:
        data (dict): The dictionary data to be checked.
        key (str): The name of the key you want to check and retrieve
            from the dictionary data.
        types (tuple[type]): The types you want to check.
        default (Any): The data to return if no match is found.
            If omitted, None.

        Returns:
            The value for key in the dictionary data, or the value
            specified by default.

        Raises:
            None
    """

    if key not in data:
        return default
    if not isinstance(data[key], types):
        return default
    return data[key]


def _convert_hexadecimal_to_number(data: str | None, byte: int) -> int | None:
    """Convert the string into a number.

    This is an internal function that checks if the specified data
    string is a hexadecimal number of the specified number of bytes
    and converts it to a number.

    Args:
        data (str | None): A string that you want to verify can be
            converted to a hexadecimal number.
        byte (int): Specify how many bytes of data are expected.

    Returns:
        Return the number if successful, or None if it failed.

    Raises:
        None

    """

    if data is None:
        return None
    try:
        num = int(data, 16)
    except (ValueError, TypeError):
        return None
    if num < 0 or (1 << (byte * 8)) <= num:
        return None
    return num


def _norm_byte(data: str | None, byte: int) -> str | None:
    """Format to the specified number of bytes.

    This is an internal function that checks if the specified data
    string is hexadecimal and returns it as a string of the specified
    number of bytes.

    Args:
        data (str | None): A string that you want to verify can be
            converted to a hexadecimal number.
        byte (int): Specify how many bytes of data are expected.

    Returns:
        Return the specified data as a zero-padded hexadecimal string
        of the specified byte size if successful, or None if it failed.

    Raises:
        None
    """
    num = _convert_hexadecimal_to_number(data, byte)
    if num is None:
        return None
    return format(num, f"0{byte*2}x")


def _classcode(data: str | None) -> dict[str, int] | None:
    """Convert the string into a pci_class_code of FmPortData.

    This is an internal function that converts a string into the
    pci_class_code format for returning in the FM plugin's
    get_port_info method.

    Args:
        data (str | None): 6-byte hexadecimal string.

    Returns:
        pci_class_code of FmPortData class

    Raises:
        None
    """

    num = _convert_hexadecimal_to_number(data, 3)
    if num is None:
        return None
    return {"base": num >> 16, "sub": (num >> 8) & 0xFF, "prog": num & 0xFF}


class _ErrorCtrl:
    """Control errors.

    This is an internal class that holds exceptions in a list without
    immediately raising them.

    Attributes:
        _exceptions (dict[_ErrorType, BaseHwControlError]): A class
            variable that defines a dictionary-type data mapping
            _ErrorType to exceptions defined by HW control.
        error (list[_ErrorType]): A list-type instance variable that
            stores error information.
    """

    _exceptions = {
        _ErrorType.ERROR_INCORRECT: exc.ConfigurationHwControlError,
        _ErrorType.ERROR_CONTROL: exc.ControlObjectHwControlError,
        _ErrorType.ERROR_INTERNAL: exc.InternalHwControlError,
    }

    def __init__(self):
        self.error = []

    def put(self, errno: _ErrorType = _ErrorType.ERROR_CONTROL) -> None:
        """Retain error information.

        Args:
            errno (_ErrorType): The error code you want to add.
                Optional. If omitted, ERROR_CONTROL will be added.

        Returns:
            None

        Raises:
            None
        """
        self.error.append(errno)

    def get(self):
        """Extract errors stored in the error list.

        When multiple errors have been added, return them in the
        following order.
          - ConfigurationHwControlError
          - ControlObjectHwControlError
          - InternalHwControlError
        If no errors are set, return InternalHwControlError.

        Args:
            None

        Returns:
            An exception class that inherits from BaseHwControlError.

        Raises:
            None
        """
        for err, cls in self._exceptions.items():
            if err in self.error:
                return cls
        return self._exceptions[_ErrorType.ERROR_INTERNAL]


class _HttpRequests:
    """Communicating using the HTTP protocol.

    An internal class that requests get/patch operations to the target
    Redfish simulator and parses the response content.
    It has the following instance variables.

    Attributes:
        timeout (float): Common timeout seconds for Connection and
            Read. It is obtained from timeout in specific_data.
            If omitted, it defaults to 1.0.
        url (str | None): A URL that does not include the service root
            path of the Redfish simulator.
            It is constructed from the specific_data:
            service_type, service_host, and service_port.
            The format is:
             - {service_type}://{service_host}:str({service_port})
            If any of this value is missing, the variable should be set
            to None.
        root (str | None): The path of the service root of the Redfish
            simulator. It is constructed from the service_root in
            specific_data.
        err (_ErrorCtrl): A reference pointer to an instance of
            _ErrorCtrl.
    """

    timeout: float = 1.0
    url = None
    root = None

    def __init__(self, specific_data: dict | None, err: _ErrorCtrl):
        """Constructor of the _HttpRequests class.

        Parse specific_data and set the instance variables.

        Args:
            specific_data (dict | None): Arguments passed to the
                constructor of the FMPlugin class.
            err (_ErrorCtrl): A reference pointer to an instance of
                _ErrorCtrl.
        """
        self.err = err
        if specific_data is None:
            return
        schema = _get_value_from_data(specific_data, "service_type", (str,))
        host = _get_value_from_data(specific_data, "service_host", (str,))
        port = _get_value_from_data(specific_data, "service_port", (int,))
        self.root = _get_value_from_data(specific_data, "service_root", (str,))
        self.timeout = _get_value_from_data(specific_data, "timeout", (int, float), self.timeout)
        if schema and host and port:
            self.url = f"{schema}://{host}:{str(port)}"
        if self.url is None or self.root is None:
            log.warning(f"Invalid specific_data. {schema}, {host}, {port}, {self.root}")
            err.put(_ErrorType.ERROR_INCORRECT)

    def _check_response(self, response: requests.Response) -> dict | None:
        """Parse response data.

        An internal method that parses the response from the Redfish
        simulator and returns it as dictionary data.

        Args:
            response (requests.Response): Return data of the requests
                method.

        Returns:
            If the status_code of the argument response is 200 and the
            data is in JSON format, the data converted to a dictionary.
            Otherwise, None.

        Raises:
            None
        """
        if response.status_code >= 500:
            log.warning(f"Server error case response status code is {response.status_code}")
            self.err.put(_ErrorType.ERROR_CONTROL)
            return None
        if response.status_code != 200:
            log.warning(f"Internal error case response status code is {response.status_code}")
            self.err.put(_ErrorType.ERROR_INTERNAL)
            return None
        try:
            return json.loads(response.text)
        except (json.JSONDecodeError, KeyError):
            log.warning(f"Invalid response text '{response.text}'")
            self.err.put(_ErrorType.ERROR_CONTROL)
        return None

    def _request(self, method: str, path: str, data: str | None = None) -> dict | None:
        """Send requests.

        An internal method to send HTTP requests to the Redfish
        simulator.

        Args:
            method (str): The request method name: "patch" or "get"
            path (str): The endpoint name of the Redfish simulator,
                including the service root
            data (str | None): Request data specified when using
                "patch". Optional. If omitted, None.

        Returns:
            If successful, the response data of the request in
            dictionary form. If it failed, None.

        Raises:
            None

        """
        _debug(f"entry: _request({method}, {path}, {data})")
        if self.url is None:
            return None
        url = f"{self.url}/{path}"
        header = {"Content-Type": "application/json; charset=utf-8"}
        try:
            func = getattr(requests, method)
            response = func(url, headers=header, data=data, timeout=self.timeout)
        except AttributeError:
            log.warning(f"Invalid method '{method}' specified.")
            self.err.put(_ErrorType.ERROR_INTERNAL)
            return None
        except (
            requests.exceptions.InvalidURL,
            requests.exceptions.InvalidSchema,
        ) as err:
            log.warning(f"Invalid specific data error {url}: {err}")
            self.err.put(_ErrorType.ERROR_INCORRECT)
            return None
        except requests.exceptions.RequestException as err:
            log.warning(f"Server error case {err.__class__.__name__}: {err}")
            self.err.put(_ErrorType.ERROR_CONTROL)
            return None

        return self._check_response(response)

    def get(self, path: str, complete_path: bool = False) -> dict | None:
        """Execute the get method and return the resulting data.

        Args:
           path (str): The path to send the request to.
           complete_path (bool): True if the path is a relative path
               from the service root, False if it is a full path.

        Returns:
           The value converted to a dictionary from the JSON-formatted
           text data returned upon success. If it failed, it returns
           None.

        Raises:
            None
        """

        if complete_path:
            path = f"{self.root}/{path}"
        return self._request("get", path)

    def patch(self, path: str, data: dict, complete_path: bool = False) -> dict | None:
        """Execute the patch method and return the resulting data.

        Args:
           path (str): The path to send the request to.
           complete_path (bool): True if the path is a relative path
               from the service root, False if it is a full path.

        Returns:
           The value converted to a dictionary from the JSON-formatted
           text data returned upon success. If it failed, it returns
           None.

        Raises:
            None
        """
        if complete_path:
            path = f"{self.root}/{path}"
        return self._request("patch", path, json.dumps(data))

    def blkid2odata(self, blkid: str) -> str:
        """Obtain the full path to the resource block information.

        Specify the resource block ID to obtain the full path to the
        resource block information.

        Args:
            blkid (str): Resource block ID.

        Returns:
            Full path to the resource block information.

        Raises:
            None
        """
        return f"{self.root}/CompositionService/ResourceBlocks/{blkid}"


class _SwitchData:
    """Manage switch information.

    An internal class to obtain information from the Redfish simulator
    and store it in FmSwitchData.
    It has the following instance variables.

    Attributes:
        req (_HttpRequests): A reference pointer to an instance of
            _HttpRequests.
        err (_ErrorCtrl): A reference pointer to an instance of
            _ErrorCtrl.
        sid (str): switch ID.
        switch (FmSwitchData): A instance of FmSwitchData.
    """

    def __init__(self, sid: str, req: _HttpRequests):
        """Constructor of the _SwitchData class.

        Create an instance of the FmSwitchData class by specifying the
        switch ID.

        Args:
            sid (str): Switch ID of the switch to retrieve information
                from.
            req (_HttpRequests): A reference pointer to an instance of
                _HttpRequests
        """
        self.req = req
        self.err = req.err
        self.sid = sid
        self.switch = FmSwitchData(
            switchId=sid,
            switchManufacturer=None,
            switchModel=None,
            switchSerialNumber=None,
            link=None,
        )

    def save_switch_data(self) -> None:
        """Retrieve the switch information and store it in FmSwitchData.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """
        switch = self.req.get(f"Fabrics/CXL/Switches/{self.sid}", True)
        if switch is None:
            return
        try:
            self.switch.switch_manufacturer = switch.get("Manufacturer")
            self.switch.switch_model = switch.get("Model")
            self.switch.switch_serial_number = switch.get("SerialNumber")
        except pydantic.ValidationError:
            self.err.put(_ErrorType.ERROR_INTERNAL)
            log.warning(f"Validation error {switch}")

    def save_switch_link(self, link: list) -> None:
        """Store the link information in FmSwitchData.

        Args:
            link (list): List of all switch IDs.

        Returns:
            None

        Raises:
            None
        """
        self.switch.link = [x for x in link if x != self.sid]

    def get_switch_data(self) -> FmSwitchData:
        """Return the stored FmSwitchData.

        Args:
            None

        Returns:
            Stored FmSwitchData.

        Raises:
            None
        """
        return self.switch


class _PortData:
    """Manage port information.

    An internal class to obtain information from the Redfish simulator
    and store it in FmPortData.
    It has the following instance variables.

    Attributes:
        req (_HttpRequests): A reference pointer to an instance of
            _HttpRequests.
        err (_ErrorCtrl): A reference pointer to an instance of
            _ErrorCtrl.
        pid (str): FM port ID.
        port_type (Literal["USP", "DSP"] | None): Value to be set in
            switch_port_type of FmPortData.
        port (FmPortData): An instance of FmPortData.
        zone (str | None): The ID of the resource zone to which the
            resource block corresponding to the port belongs.
    """
    zone: str | None = None
    port_type: typing.Literal["USP", "DSP"] | None = None

    def __init__(self, pid: str, req: _HttpRequests):
        """Constructor of the _PortData class.

        Create an instance of the FmPortData class by specifying the
        FM port ID.

        Args:
            pid (str): FM port ID of the port to retrieve information
                from.
            req (_HttpRequests): A reference pointer to an instance of
                _HttpRequests
        """
        self.req = req
        self.err = req.err
        self.pid = pid
        self.port = FmPortData(
            id=self.pid,
            switchPortType=self.port_type,
            switchId=None,
            switchPortNumber=None,
            fabricId=None,
            link=None,
            deviceType=None,
            PCIClassCode=None,
            PCIeDeviceId=None,
            PCIeVendorId=None,
            PCIeDeviceSerialNumber=None,
            CPUManufacturer=None,
            CPUModel=None,
            CPUSerialNumber=None,
            LTSSMState=None,
            deviceKeys={},
            portKeys={},
            capacity=None,
        )

    def save_switch_data(self, swt: _SwitchData) -> None:
        """Store the switch_id and fabric_id in FmPortData.

        Args:
            swt (_SwitchData): A reference pointer to an instance of
                _SwitchData

        Returns:
            None

        Raises:
            None
        """
        manufact = swt.switch.switch_manufacturer
        model = swt.switch.switch_model
        serial = swt.switch.switch_serial_number
        try:
            self.port.switch_id = swt.sid
            if manufact and model and serial and self.zone:
                self.port.fabric_id = f"{manufact}-{model}-{serial}-{self.zone}"
        except pydantic.ValidationError:
            self.err.put(_ErrorType.ERROR_INTERNAL)
            log.warning(f"Validation error {swt.sid}")

    def save_zone(self, rbdata: dict) -> None:
        """Store the zone instance variable.

        Args:
            rbdata (dict): Dictionary-type data for the resource block.

        Returns:
            None

        Raises:
            None
        """
        zones = rbdata.get("Links", {}).get("Zones", [])
        if len(zones) == 1:
            self.zone = _FabricData.odata2id(zones[0], self.err)

    def save_link(self, ids: list) -> None:
        """Store the link information in FmPortData.

        Args:
            ids (list): List of all FM port IDs.

        Returns:
            None

        Raises:
            None
        """

    def save_port_data(self) -> None:
        """Retrieve the port information and store it in FmPortData.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

    def get_port_data(self) -> FmPortData:
        """Return the stored FmPortData.

        Args:
            None

        Returns:
            Stored FmPortData.

        Raises:
            None
        """
        return self.port


class _PortDataUSP(_PortData):
    """Manage port information on the USP side.

    In addition to the attributes inherited from the _PortData class,
    it has the following instance variables.

    Attributes:
        syspath (str | None): Full path of the system schema.
    """

    port_type: typing.Literal["USP", "DSP"] | None = "USP"

    def __init__(self, pid: str, req: _HttpRequests):
        """Constructor of the _PortDataUSP class.

        Execute the constructor of the parent class and retrieve the
        syspath.

        Args:
            pid (str): FM port ID of the port to retrieve information
                from.
            req (_HttpRequests): A reference pointer to an instance of
                _HttpRequests
        """
        super().__init__(pid, req)
        self.syspath = _FabricData.uspid2system(pid)

    def _get_device_data(self) -> None | dict:
        """Retrieve the Processor schema.

        An internal method that obtains the device path of the CPU
        located in the resource block and returns the CPU information.

        Args:
            None

        Returns:
            On success, a dictionary-type data of the Processor schema
            obtained from the simulator. On failure, None.

        Raises:
            None
        """
        rbdata = self.req.get(f"CompositionService/ResourceBlocks/{self.pid}", True)
        if rbdata is None:
            return None
        self.save_zone(rbdata)
        for dev in rbdata.get("Processors", []):
            devpath = dev.get("@odata.id")
            if not devpath:
                continue
            devdata = self.req.get(devpath)
            if devdata and devdata.get("ProcessorType") == "CPU":
                return devdata
        log.warning(f"{self.pid} usp processor not found\n{rbdata}")
        self.err.put(_ErrorType.ERROR_CONTROL)
        return None

    @typing_extensions.override
    def save_link(self, ids: list) -> None:
        """See base class."""
        sysdata = self.req.get(self.syspath, True)
        if sysdata is None:
            return

        links = []
        for block in sysdata.get("Links", {}).get("ResourceBlocks", []):
            blkid = _FabricData.odata2id(block, self.err)
            if blkid is None:
                return
            if blkid not in ids:
                log.warning(f"Invalid resource block {blkid} not in {ids}")
                self.err.put(_ErrorType.ERROR_CONTROL)
                return

            if not _FabricData.port_is_usp(blkid):
                links.append(blkid)

        self.port.link = links

    @typing_extensions.override
    def save_port_data(self) -> None:
        """See base class."""
        cpu_data = self._get_device_data()
        if cpu_data is None:
            return
        try:
            self.port.cpu_model = cpu_data.get("Model")
            self.port.cpu_manufacturer = cpu_data.get("Manufacturer")
            self.port.cpu_serial_number = cpu_data.get("SerialNumber")
        except pydantic.ValidationError:
            self.err.put(_ErrorType.ERROR_INTERNAL)
            log.warning(f"Validation error {cpu_data}")

    def change_link(self, blkids: list) -> bool:
        """Request a configuration change to the simulator.

        Args:
            blkids (list): A list of resource block IDs connected after
                the configuration change.

        Returns:
            Return True if the request completes successfully, and
            False if it failed.

        Raises:
            None

        Note:
            The method does not modify the link information held in the
            port instance variable.
            If you wish to refer to the updated link information of the
            port after executing this method, you should execute the
            save_link method on the instance of the port whose link
            information you want to refer to.
        """
        links = [{"@odata.id": self.req.blkid2odata(_b)} for _b in blkids + [self.pid]]
        data = {"Links": {"ResourceBlocks": links}}
        return self.req.patch(self.syspath, data, True) is not None


class _PortDataDSP(_PortData):
    """Manage port information on the DSP side.

    Inherit from the _PortData class and have the same attributes.
    """

    port_type: typing.Literal["USP", "DSP"] | None = "DSP"

    def _get_device_path(self) -> None | str:
        """Retrieve the path of the device schema.

        An internal method that retrieves and returns the path of the
        device located in the resource block.

        Args:
            None

        Returns:
            The path of the device schema if successful. None if failed.

        Raises:
            None
        """
        rbdata = self.req.get(f"CompositionService/ResourceBlocks/{self.pid}", True)
        if rbdata is None:
            return None
        self.save_zone(rbdata)
        found = []
        for devtype in ["Processors", "Memory", "EthernetInterfaces", "Drives"]:
            for dev in rbdata.get(devtype, []):
                found.append(dev.get("@odata.id"))
        if len(found) != 1:
            log.warning(f"{self.pid} dsp target device count is {(len(found))}\n{rbdata}")
            self.err.put(_ErrorType.ERROR_CONTROL)
            return None
        return found[0]

    @typing_extensions.override
    def save_link(self, ids: list) -> None:
        """See base class."""
        rbdata = self.req.get(f"CompositionService/ResourceBlocks/{self.pid}", True)
        if rbdata is None:
            return

        links = []
        for system in rbdata.get("Links", {}).get("ComputerSystems", []):
            sysid = _FabricData.odata2id(system, self.err)
            if sysid is None:
                return
            blkid = _FabricData.system2uspid(sysid)
            if blkid not in ids:
                log.warning(f"Invalid resource block {blkid} not in {ids}")
                self.err.put(_ErrorType.ERROR_CONTROL)
                return
            links.append(blkid)

        if len(links) > 1:
            log.warning(f"{self.pid} dsp link failed\n{rbdata}")
            self.err.put(_ErrorType.ERROR_CONTROL)
            return
        self.port.link = links

    @typing_extensions.override
    def save_port_data(self) -> None:
        """See base class."""
        devpath = self._get_device_path()
        if devpath is None:
            return

        devid = devpath.split("-")[-1]
        pciedev = self.req.get(f"Chassis/Chassis-1/PCIeDevices/PCIe-{devid}", True)
        if pciedev is None:
            return
        pdsn = _norm_byte(pciedev.get("SerialNumber"), 8)
        if pdsn is None:
            self._save_port_data_memory(devpath)
            return
        self.port.pcie_device_serial_number = pdsn
        self.port.device_type = "PCIe"

        funcpath = pciedev.get("PCIeFunctions", {}).get("@odata.id")
        pciefunc = self.req.get(f"{funcpath}/PCIeF-{devid}")
        if pciefunc is None:
            return
        self.port.pcie_device_id = _norm_byte(pciefunc.get("DeviceId"), 2)
        self.port.pcie_vendor_id = _norm_byte(pciefunc.get("VendorId"), 2)
        self.port.pci_class_code = _classcode(pciefunc.get("ClassCode"))

    def _save_port_data_memory(self, devpath: str) -> None:
        """Retrieve the memory information and store it in FmPortData.

        An internal method that retrieves the memory schema of the
        specified path and stores it in the capacity and device_keys of
        FmPortData.

        Args:
            The full path of the memory schema.

        Returns:
            None

        Raises:
            None
        """
        memdata = self.req.get(devpath)
        if memdata is None:
            return
        self.port.device_keys = {"SimulatedDeviceID": memdata.get("SerialNumber")}
        cxl = memdata.get("CXL")
        if cxl is None:
            return
        volatile = _get_value_from_data(cxl, "StagedVolatileSizeMiB", (int,), 0)
        persistent = _get_value_from_data(cxl, "StagedNonVolatileSizeMiB", (int,), 0)
        if volatile < 0 or persistent < 0 or (volatile == 0 and persistent == 0):
            return
        self.port.capacity = {
            "volatile": volatile << 20,
            "persistent": persistent << 20,
        }
        self.port.device_type = "CXL-Type3"


class _FabricData:
    """Manage fabric information.

    An internal class that retrieves, stores, and returns a list of FM
    port IDs and switch IDs.

    Attributes:
        req (_HttpRequests): A reference pointer to an instance of
            _HttpRequests.
        err (_ErrorCtrl): A reference pointer to an instance of
            _ErrorCtrl.
        uspids (list): The list of FM port IDs on the USP side.
        dspids (list): The list of FM port IDs on the DSP side.
        swtids (list): The list of switch IDs.
    """
    def __init__(self, req: _HttpRequests):
        """Constructor of the _FabricData class.

        Store instance variables and initialize the list.

        Args:
            req (_HttpRequests): A reference pointer to an instance of
                _HttpRequests
        """
        self.err = req.err
        self.req = req
        self.uspids: list[str] = []
        self.dspids: list[str] = []
        self.swtids: list[str] = []

    @staticmethod
    def port_is_usp(blkid: str) -> bool:
        """Return whether the FM Port ID is USP or DSP.

        A static method that returns whether the argument blkid is on
        the USP side or the DSP side.

        Args:
            blkid (str): Resource block ID(Same as FM port ID).

        Returns: Return True if the argument blkid is on the USP side,
            and False if it is on the DSP side.

        Raises:
            None
        """
        return blkid.startswith("ComputeBlock")

    @staticmethod
    def uspid2system(blkid: str) -> str:
        """Return the full path of the system schema.

        A static method that converts the argument blkid to a relative
        path from the System's service root.

        Args:
            blkid (str): USP side Resource Block ID.

        Returns:
            The path of the system schema.

        Raises:
            None
        """
        return blkid.replace("ComputeBlock", "Systems/System")

    @staticmethod
    def system2uspid(system: str) -> str:
        """Return the resource block ID on the USP side.

        A static method that converts the argument system schema path
        to a resource block ID.

        Args:
            system (str): The path of the system schema.

        Returns:
            USP side Resource Block ID.

        Raises:
            None
        """
        return f"ComputeBlock-{system.split('-')[-1]}"

    @staticmethod
    def odata2id(member: dict, err: _ErrorCtrl) -> str | None:
        """Return the resource path from the dictionary data.

        A static method that returns the resource path of the odata.id
        element within the member dictionary data provided as an
        argument.

        Args:
            member (dict): Elements such as link information obtained
                from the simulator.
            err (_ErrorCtrl): An instance of _ErrorCtrl that stores
                errors.

        Returns:
            The resource path of the value corresponding to the
            "@odata.id" key. If it does not exist, return None.

        Raises:
            None
        """
        odata = member.get("@odata.id")
        if odata is None:
            log.warning(f"Invalid format {member}")
            err.put(_ErrorType.ERROR_CONTROL)
            return None
        return odata.split("/")[-1]

    def get_port_ids(self, port_type: typing.Literal["USP", "DSP"] | None = None) -> list:
        """Return a list of FM port IDs.

        Args:
            port_type (Literal["USP", "DSP"] | None): "USP" or "DSP"
                can be omitted.

        Returns:
            If port_type is specified, return a list of FM port IDs for
            the specified side. If not specified, return a list of all
            FM port IDs.
            If the save_and_get_port_ids method has not been executed,
            return an empty list.

        Raises:
            None
        """
        if port_type == "USP":
            return self.uspids
        if port_type == "DSP":
            return self.dspids
        return self.uspids + self.dspids

    def get_switch_ids(self) -> list:
        """Return a list of switch IDs.

        Args:
            None

        Returns:
            A list of switch IDs.
            If the save_and_get_switch_ids method has not been
            executed, return an empty list.

        Raises:
            None
        """
        return self.swtids

    def save_and_get_port_ids(self) -> list:
        """Retrieve, save, and return a list of FM port IDs.

        Args:
            None

        Returns:
            A list of all detected FM port IDs.
            If retrieval failed, return an empty list.

        Raises:
            None
        """
        _debug("entry: save_port_ids")
        uspids = []
        dspids = []
        blocks = self.req.get("CompositionService/ResourceBlocks", True)
        if blocks is None:
            return []

        for _b in blocks.get("Members", []):
            blkid = _FabricData.odata2id(_b, self.err)
            if blkid:
                if self.port_is_usp(blkid):
                    uspids.append(blkid)
                else:
                    dspids.append(blkid)
        if len(uspids + dspids) == 0:
            log.warning(f"No resource block found from ResourceBlocks\n{blocks}")
            self.err.put(_ErrorType.ERROR_CONTROL)
            return []
        self.uspids = uspids
        self.dspids = dspids
        return uspids + dspids

    def save_and_get_switch_ids(self) -> list:
        """Retrieve, save, and return a list of switch IDs.

        Args:
            None

        Returns:
            A list of all detected switch IDs.
            If retrieval failed, return an empty list.

        Raises:
            None
        """
        _debug("entry: save_switch_ids")
        swtids = []
        switches = self.req.get("Fabrics/CXL/Switches", True)
        if switches is None:
            return []

        for _s in switches.get("Members", []):
            swtid = _FabricData.odata2id(_s, self.err)
            if swtid:
                swtids.append(swtid)
        if len(swtids) == 0:
            log.warning(f"No switch found from Switches\n{switches}")
            self.err.put(_ErrorType.ERROR_CONTROL)
            return []
        self.swtids = swtids
        return swtids


class FmPlugin(FMPluginBase):
    """Fabric Manager plugin class for use reference redfish simulator.

    Class Name:
        FmPlugin

    Attributes:
        _link_lock (_thread.lock): A class variable for a lock to
            protect the port's link state. It should be held during the
            following processes:
              - During the retrieval of all link information when
                obtaining all port information (when get_port_info is
                called without arguments).
              - During link retrieval and updates caused by connecting
                or disconnecting.
        err (_ErrorCtrl): An instance variable to store the _ErrorCtrl
            instance.
        req (_HttpRequests): An instance variable to store the
            _HttpRequests instance.
        fabric (_FabricData): An instance variable to store the
            _FabricData instance.
    """

    _link_lock = threading.Lock()

    def __init__(self, specific_data: dict | None = None):
        """Constructor of the FmPlugin class.

        Create instances of the _ErrorCtrl class, _HttpRequests class,
        and _FabricData class.

        Args:
            specific_data (dict | None): An instance variable that holds
                the specific_data from the plugin configuration file.
                It is dictionary data containing the following keys.
                  - timeout(float)
                  - service_root(str)
                  - service_host(str)
                  - service_type(str)
                  - service_port(int)
        """
        super().__init__(specific_data)
        self.err = _ErrorCtrl()
        self.req = _HttpRequests(specific_data, self.err)
        self.fabric = _FabricData(self.req)

    def _get_port_data(self, pid: str, swt: _SwitchData) -> _PortData:
        """Retrieval of FmPortData other than links.

        An internal method to create an instance of _PortData and store
        port information other than the link.

        Args:
            pid (str): The FM port ID of the port from which information
                is to be retrieved.
            swt (_SwitchData): An instance of _SwitchData where the port
                exists.

        Returns:
            An instance of the _PortData class.

        Raises:
            None
        """
        _debug("entry: _get_port_data")
        port: _PortData
        if self.fabric.port_is_usp(pid):
            port = _PortDataUSP(pid, self.req)
        else:
            port = _PortDataDSP(pid, self.req)
        port.save_port_data()
        port.save_switch_data(swt)
        return port

    def _get_switch_data(self, sid: str, swtids: list) -> _SwitchData:
        """Retrieval of FmSwitchData.

        An internal method to create an instance of SwitchData and
        store switch information.

        Args:
            sid (str): The switch ID of the port from which information
                is to be retrieved.
            swtids (list): A list of all switches.

        Returns:
            An instance of the _SwitchData class.

        Raises:
            None
        """
        _debug("entry: _get_switch_data")
        swt = _SwitchData(sid, self.req)
        swt.save_switch_data()
        swt.save_switch_link(swtids)
        return swt

    def _setup_control(self, uid: str, did: str) -> typing.Tuple[_PortDataUSP, _PortDataDSP]:
        """Check whether the FM port ID given in the argument exists.

        An internal method to verify whether the FM port ID specified
        in the connect/disconnect arguments exists.

        Args:
            uid (str): FM port ID on the USP side.
            did (str): FM port ID on the DSP side.

        Returns:
            A tuple containing an instance of the _PortDataUSP class
            and an instance of the _PortDataDSP class.

        Raises:
            Following exception defined in the
            app.common.basic_exceptions module:
            HostCpuNotFoundHwControlError:
                The specified cpu_id is not found in data.
            DeviceNotFoundHwControlError:
                The specified device_id is not found in data.
            HostCpuAndDeviceNotFoundHwControlError:
                Both cpu_id and device_id is not found in data.
            ConfigurationHwControlError:
                The 'specific_data' instance variable is incorrect.
            ControlObjectHwControlError:
                The simulator response is unexpected, and so on.
            InternalHwControlError:
                Detected an inconsistency in the internal processing.
        """
        if len(self.fabric.save_and_get_port_ids()) == 0:
            raise self.err.get()
        if (uid not in self.fabric.get_port_ids("USP") and
                did not in self.fabric.get_port_ids("DSP")):
            raise exc.HostCpuAndDeviceNotFoundHwControlError
        if uid not in self.fabric.get_port_ids("USP"):
            raise exc.HostCpuNotFoundHwControlError
        if did not in self.fabric.get_port_ids("DSP"):
            raise exc.DeviceNotFoundHwControlError

        usp = _PortDataUSP(uid, self.req)
        dsp = _PortDataDSP(did, self.req)
        return usp, dsp

    def get_port_info(self, target_id: typing.Optional[str] = None) -> dict:
        """Get port information.

        Method Name:
            get_port_info

        Args:
            target_id (str): Optional.
                Specify the id of the data you want to acquire.
                If omitted, all data of up and down stream ports.

        Returns:
            A dictionary-type data with the "data" key.
            The value of the "data" key is a list of FmPortData class
            instances.
            If an argument is specified, the list contains only one
            specified port.
            If no argument is specified, the list contains all the ports
            retrieved.

        Raises:
            Following exception defined in the
            app.common.basic_exceptions module:
            ResourceNotFoundHwControlError:
                The specified target_id is not found in data.
            ConfigurationHwControlError:
                The 'specific_data' instance variable is incorrect.
            ControlObjectHwControlError:
                The simulator response is unexpected, and so on.
            InternalHwControlError:
                Detected an inconsistency in the internal processing.
        """
        prtids = self.fabric.save_and_get_port_ids()
        if len(prtids) == 0:
            raise self.err.get()

        swtids = self.fabric.save_and_get_switch_ids()
        if len(swtids) == 0:
            raise self.err.get()
        swt = self._get_switch_data(swtids[0], swtids)
        if target_id:
            if target_id not in prtids:
                raise exc.ResourceNotFoundHwControlError

            port = self._get_port_data(target_id, swt)

            # The link status of a single port is determined by one type of information.
            # This information is updated atomically when the link status is updated.
            # When returning the link status of only one port, mutual exclusion is not
            # necessary, and the _link_lock is not acquired.
            port.save_link(prtids)
            return {"data": [port.get_port_data()]}

        ports = [self._get_port_data(p, swt) for p in prtids]
        with FmPlugin._link_lock:
            for port in ports:
                port.save_link(prtids)

        return {"data": [p.get_port_data() for p in ports]}

    def get_switch_info(self, switch_id: typing.Optional[str] = None) -> dict:
        """Get switch information.

        Method Name:
            get_switch_info

        Args:
            switch_id (str): Optional.
                Specify the id of the data you want to acquire.
                If omitted, all data of switches managed by FM.

        Returns:
            A dictionary-type data with the "data" key.
            The value of the "data" key is a list of FmPortData class
            instances.
            If an argument is specified, the list contains only one
            specified switch.
            If no argument is specified, the list contains all the
            switches retrieved.

        Raises:
            Following exception defined in the
            app.common.basic_exceptions module:
            SwitchNotFoundHwControlError:
                The specified switch_id is not found in data.
            ConfigurationHwControlError:
                The 'specific_data' instance variable is incorrect.
            ControlObjectHwControlError:
                The simulator response is unexpected, and so on.
            InternalHwControlError:
                Detected an inconsistency in the internal processing.
        """
        swtids = self.fabric.save_and_get_switch_ids()
        if len(swtids) == 0:
            raise self.err.get()

        if switch_id:
            if switch_id not in swtids:
                raise exc.SwitchNotFoundHwControlError

            swt = self._get_switch_data(switch_id, swtids)
            return {"data": [swt.get_switch_data()]}

        switches = [self._get_switch_data(s, swtids) for s in swtids]
        return {"data": [s.get_switch_data() for s in switches]}

    def connect(self, cpu_id: str, device_id: str) -> None:
        """Connect up stream port and down stream port.

        Method Name:
            connect

        Args:
            cpu_id (str): Unique id associated with the up stream port.
            device_id (str): Unique id associated with the down stream
                port.

        Returns:
            None

        Raises:
            Following exception defined in the
            app.common.basic_exceptions module:
            HostCpuNotFoundHwControlError:
                The specified cpu_id is not found in data.
            DeviceNotFoundHwControlError:
                The specified device_id is not found in data.
            HostCpuAndDeviceNotFoundHwControlError:
                Both cpu_id and device_id is not found in data.
            RequestConflictHwControlError:
                The specified device_id is connected to another cpu_id.
            ConfigurationHwControlError:
                The 'specific_data' instance variable is incorrect.
            ControlObjectHwControlError:
                The simulator response is unexpected, and so on.
            FmConnectFailureHwControlError:
                The request to connect to the simulator failed.
            InternalHwControlError:
                Detected an inconsistency in the internal processing.
        """
        usp, dsp = self._setup_control(cpu_id, device_id)

        with FmPlugin._link_lock:
            usp.save_link(self.fabric.get_port_ids())
            dsp.save_link(self.fabric.get_port_ids())
            usplink = usp.get_port_data().link
            dsplink = dsp.get_port_data().link
            if usplink is None or dsplink is None:
                raise self.err.get()

            if dsp.pid in usplink:
                return
            if dsplink:
                _msg = f"connect: device_id {device_id} linked {dsplink}"
                raise exc.RequestConflictHwControlError(additional_message=_msg)

            resp = usp.change_link([dsp.pid] + usplink)
            if not resp:
                raise exc.FmConnectFailureHwControlError
        return

    def disconnect(self, cpu_id: str, device_id: str) -> None:
        """Disconnect up stream port and down stream port.

        Method Name:
            disconnect

        Args:
            cpu_id (str): Unique id associated with the up stream port.
            device_id (str): Unique id associated with the down stream
                port.

        Returns:
            None

        Raises:
            Following exception defined in the
            app.common.basic_exceptions module:
            HostCpuNotFoundHwControlError:
                The specified cpu_id is not found in data.
            DeviceNotFoundHwControlError:
                The specified device_id is not found in data.
            HostCpuAndDeviceNotFoundHwControlError
                Both cpu_id and device_id is not found in data.
            RequestConflictHwControlError:
                The specified device_id is connected to another cpu_id.
            ConfigurationHwControlError:
                The 'specific_data' instance variable is incorrect.
            ControlObjectHwControlError:
                The simulator response is unexpected, and so on.
            FmDisconnectFailureHwControlError:
                The request to disconnect to the simulator failed.
            InternalHwControlError:
                Detected an inconsistency in the internal processing.
        """
        usp, dsp = self._setup_control(cpu_id, device_id)

        with FmPlugin._link_lock:
            usp.save_link(self.fabric.get_port_ids())
            dsp.save_link(self.fabric.get_port_ids())
            usplink = usp.get_port_data().link
            dsplink = dsp.get_port_data().link
            if usplink is None or dsplink is None:
                raise self.err.get()

            if not dsplink:
                return

            if dsp.pid not in usplink:
                _msg = f"disconnect: device_id {device_id} linked {dsplink}"
                raise exc.RequestConflictHwControlError(additional_message=_msg)

            links = [pid for pid in usplink if dsp.pid != pid]
            resp = usp.change_link(links)
            if not resp:
                raise exc.FmDisconnectFailureHwControlError
        return
