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
Mock object of app.common.utils.fm_plugin_base
"""

from typing import Dict, Optional, List, Literal, Self
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator


_HEXADECIMAL = r"^[0-9a-fA-F]*$"


class FMPortData(BaseModel):
    """Mock class of FMPortData"""

    model_config = ConfigDict(validate_assignment=True)
    id: StrictStr
    switch_id: Optional[StrictStr] = Field(None, alias="switchId")
    switch_port_number: Optional[StrictStr] = Field(None, alias="switchPortNumber")
    switch_port_type: Optional[Literal["USP", "DSP"]] = Field(None, alias="switchPortType")
    fabric_id: Optional[StrictStr] = Field(None, alias="fabricId")
    link: Optional[List[str]] = Field(None)
    device_type: Optional[
        Literal["CXL-Type1", "CXL-Type2", "CXL-Type3", "CXL-Type3-MLD", "PCIe", "Undetected", "Other", "Unknown"]
    ] = Field(None, alias="deviceType")
    pci_class_code: Optional[Dict[str, int]] = Field(None, min_length=3, max_length=3, alias="PCIClassCode")
    pcie_vendor_id: Optional[StrictStr] = Field(
        None, min_length=4, max_length=4, pattern=_HEXADECIMAL, alias="PCIeVendorId"
    )
    pcie_device_id: Optional[StrictStr] = Field(
        None, min_length=4, max_length=4, pattern=_HEXADECIMAL, alias="PCIeDeviceId"
    )
    pcie_device_serial_number: Optional[StrictStr] = Field(
        None, min_length=16, max_length=16, pattern=_HEXADECIMAL, alias="PCIeDeviceSerialNumber"
    )
    cpu_manufacturer: Optional[StrictStr] = Field(None, alias="CPUManufacturer")
    cpu_model: Optional[StrictStr] = Field(None, alias="CPUModel")
    cpu_serial_number: Optional[StrictStr] = Field(None, alias="CPUSerialNumber")
    ltssm_state: Optional[
        Literal["L0", "L0s", "L2", "Detect", "Polling", "Configuration", "Recovery", "HotReset", "Disable", "Loopback"]
    ] = Field(None, alias="LTSSMState")
    device_keys: dict = Field({}, alias="deviceKeys")
    port_keys: dict = Field({}, alias="portKeys")
    capacity: Optional[Dict[str, StrictInt]] = Field(None, min_length=1, max_length=3)

    @field_validator("pci_class_code")
    @classmethod
    def validate_pci_class_code(cls, value):
        """PCIClassCode must be {'base': 0-255, 'sub': 0-255, 'prog': 0-255}"""
        if value is None:
            return value
        if set(["base", "sub", "prog"]) != set(value.keys()) or len([x for x in value.values() if 0 <= x < 0x100]) != 3:
            raise ValueError(
                "The keys of the dictionary data are not 'base', 'sub', or 'prog', "
                "or the values are not within the range of 0 to 255."
            )
        return value

    @staticmethod
    def _fix_capacity(value: dict):
        """Fill in the missing information of capacity."""
        if len(value) == 1:
            if "volatile" in value:
                value["total"] = value["volatile"]
                value["persistent"] = 0
            elif "persistent" in value:
                value["total"] = value["persistent"]
                value["volatile"] = 0
        elif len(value) == 2:
            if "volatile" in value and "persistent" in value:
                value["total"] = value["volatile"] + value["persistent"]
            elif "volatile" in value and "total" in value:
                value["persistent"] = value["total"] - value["volatile"]
            elif "persistent" in value and "total" in value:
                value["volatile"] = value["total"] - value["persistent"]

    @field_validator("capacity")
    @classmethod
    def validate_capacity(cls, value):
        """capacity"""
        if value is None:
            return value

        cls._fix_capacity(value)
        if "volatile" not in value or "persistent" not in value or "total" not in value:
            raise ValueError("The keys of the dictionary data are not 'volatile', 'persistent', or 'total'.")
        if (
            value["total"] != value["persistent"] + value["volatile"]
            or value["total"] < 0
            or value["persistent"] < 0
            or value["volatile"] < 0
        ):
            raise ValueError("There are inconsistencies in the values for 'volatile', 'persistent', or 'total'.")
        return value

    @model_validator(mode="after")
    def validate_port_type_cpu_pcie(self) -> Self:
        """PCIe data must be None if switchPortType is USP,
        CPU data must be None if switchPortType is DSP
        """
        if self.switch_port_type == "USP" and (
            self.pcie_vendor_id is not None
            or self.pcie_device_id is not None
            or self.pcie_device_serial_number is not None
        ):
            raise ValueError("The switchPortType is USP, but PCI information is set.")
        if self.switch_port_type == "DSP" and (
            self.cpu_manufacturer is not None or self.cpu_model is not None or self.cpu_serial_number is not None
        ):
            raise ValueError("The switchPortType is DSP, but CPU information is set.")
        return self


class FMSwitchData(BaseModel):
    """Mock class of FMSwitchData"""

    model_config = ConfigDict(validate_assignment=True)
    switch_id: StrictStr = Field(..., alias="switchId")
    switch_manufacturer: Optional[StrictStr] = Field(None, alias="switchManufacturer")
    switch_model: Optional[StrictStr] = Field(None, alias="switchModel")
    switch_serial_number: Optional[StrictStr] = Field(None, alias="switchSerialNumber")
    link: Optional[List[str]] = Field(None)


class FMPluginBase:
    """Mock class of FMPluginBase."""

    # pylint: disable=too-few-public-methods
    def __init__(self, specific_data=None):
        self.specific_data = specific_data
