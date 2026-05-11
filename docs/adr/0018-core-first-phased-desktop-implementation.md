# Core-first phased desktop implementation

The desktop application will be implemented in phases, starting with reusable core modules, configurable paths, App Data/KB Data separation, and the SQLite Job Queue before building the PySide6 UI. This avoids painting a desktop shell over fixed-path scripts and makes hooks, CLI subcommands, background jobs, tests, and packaging share one reliable execution model.
