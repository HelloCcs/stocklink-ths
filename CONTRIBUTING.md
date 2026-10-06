# Contributing

1. Create a focused branch and explain the Windows behavior you are changing.
2. Do not add customer files, screenshots, credentials, runtime evidence, or third-party installers.
3. Add or update focused tests for behavior changes.
4. Run `python -m unittest discover -q` before opening a pull request.
5. Keep Win32 input bounded, fail-closed, and explicit about foreground and window identity checks.
