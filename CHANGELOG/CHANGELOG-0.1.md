# Changelog 0.1

## [0.1.1](https://github.com/project-cdim/fm-plugin-reference/compare/v0.1.0...v0.1.1) - 2025-09-12

The changes from v0.1.0 are as follows:

### Breaking Changes

- Switched from the logger provided by the hw-control to using Python's built-in
  logger.
- Addressed changes to the names of HW Control Exceptions classes and port/switch
  information classes.

### Others

- Updated the required Python version from 3.11 or higher to 3.12 or higher.
- Added mypy type checking and Black format checking to lint.
- Migrated internal class names to follow the PEP8 CapitalizedWords (CamelCase) convention.
- Refined `.gitignore`
