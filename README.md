# fm-plugin-reference

fm-plugin-reference - Reference Fabric Manager Plugin for hw-control

## Requirements

- Python 3.11 and later
- [pdm](https://pdm-project.org/en/latest/)
- [hw-control](https://github.com/project-cdim/hw-control)
- [hw-emulator-reference](https://github.com/project-cdim/hw-emulator-reference)

## How to use

1. Start the [hw-emulator-reference](https://github.com/project-cdim/hw-emulator-reference)
   for the control target.  
1. Install the plugin in the
   [hw-control](https://github.com/project-cdim/hw-control).  
   Please refer to [Installation](#installation) for details.  
1. Update the following items in the Plugin Configuration File to match the environment
   of the hw-emulator-reference:  

   service_host  
     - No changes are necessary if you are running the hw-emulator-reference
       and the hw-control on the same machine.  
     - If you are operating on a different machine, please change.

   service_port  
     - If you have changed the port of the hw-emulator-reference, please change.

   Please refer to [Plugin Configuration File](#plugin-configuration-file) for details
   on the settings.  

## Installation

Clone the fm-plugin-reference repository to any location.  

```bash
git clone <the URL of the fm-plugin-reference repository>
```

Copy the FM Plugin core to the operating environment of the hw-control.

```bash
cp -r fm-plugin-reference/src/plugins/fm/reference \
 <path to the hw-control>/hw-control/src/plugins/fm/
```

Copy the Plugin Configuration File to the operating environment of the hw-control.

```bash
cp fm-plugin-reference/src/plugins/fm/refer-001_manager.yaml \
 <path to the hw-control>/hw-control/src/plugins/fm/
```

## Plugin Configuration File

The descriptions of the items listed listed in the Plugin Configuration File are
as follows.

- module
  - Specify the location of the plugin module from `plugins.fm.`.
- class
  - Specify the class name of the plugin.
- specific_data
  - This is the unique data used by this plugin. It contains the following items.
    - service_type
      - Specify the protocol for communicating with the hw-emulator-reference
        as a string.
      - Only `http` is available for use.
    - service_host
      - Specify the host running the hw-emulator-reference as a string.
    - service_port
      - Specify the port running the hw-emulator-reference as a number.
    - service_root:
      - Specify the service root of the hw-emulator-reference as a string.
    - timeout
      - Specify the common timeout value in seconds for both Read and Connection
        when communicating with the hw-emulator-reference as a number.

## How to run lint

```bash
pdm run lint
```

## How to run unittest

```bash
pdm run test
```

## Included Files

- src/plugins/fm/refer-001_manager.yaml
  - Plugin Configuration File.
- src/plugins/fm/reference/plugin.py
  - The python module that is the FM Plugin core.
- tests/test_fm_plugin.py
  - Unit test module for `FmPlugin` class.
- tests/test_error_ctrl.py
  - Unit test module for `_ErrorCtrl` class.
- tests/test_http_requests.py
  - Unit test module for `_HttpRequests` class.
- tests/test_fabric_data.py
  - Unit test module for `_FabricData` class.
- tests/test_switch_data.py
  - Unit test module for `_SwitchData` class.
- tests/test_port_data.py
  - Unit test module for `_PortData` class.
- tests/test_port_data_usp.py
  - Unit test module for `_PortDataUSP` class.
- tests/test_port_data_dsp.py
  - Unit test module for `_PortDataDSP` class.
- tests/app/common/messages/message.py
  - Mock for the log message model class within hw-control.
- tests/app/common/basic_exceptions.py
  - Mock for the HW Control Exceptions within hw-control.
- tests/app/common/utils/fm_plugin_base.py
  - Mock for the Plugin Manager within hw-control.
- tests/app/common/utils/log.py
  - Mock for the logger object within hw-control.

## License

[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)
