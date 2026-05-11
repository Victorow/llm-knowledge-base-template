# Packaged app does not depend on uv runtime

The installed desktop application will not require users to have `uv` or a separate Python environment available at runtime. PyInstaller will package the Python application and dependencies, and the UI/Background Agent will call reusable core modules directly; existing CLI scripts remain as development and automation wrappers around the same core behavior.
