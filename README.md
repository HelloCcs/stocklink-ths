# StockLink THS

StockLink THS is a Windows desktop helper for sending a six digit stock code from a spreadsheet to a running Tonghuashun (THS) quote window and switching that quote to the daily K chart.

The supported lightweight workflow is:

1. Start the StockLink application.
2. Copy one six digit stock code in WPS or another spreadsheet.
3. Press **Ctrl+Alt+Z**.
4. StockLink discovers the visible THS window, activates the selected target, enters the code, and sends THS's `05` daily-chart command.

The project also contains the earlier date-marker and chart-tracking modules. Those modules are retained for development and research; the simplified hotkey workflow does not claim live verification of date overlays.

## Requirements

- Windows 10 or later
- Python 3.10+
- A locally installed Tonghuashun client (`hexin.exe`)
- Python dependencies in `requirements.txt` (and `requirements-vision.txt` for OCR modules)

Install dependencies in a virtual environment:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run from the project directory:

```powershell
.\.venv\Scripts\python.exe main.py
```

The source workflow is Windows-specific and uses guarded Win32 input. It will fail closed when no unique visible THS target can be identified.

## Testing

```powershell
.\.venv\Scripts\python.exe -m unittest discover -q
```

The repository's latest local run completed 101 tests with zero failures, errors, or skips. Tests cover workbook parsing, hotkey dispatch, target-window selection, command ordering, and failure propagation. Real THS GUI behavior still depends on the customer's Windows desktop and THS version.

## Scope and safety

StockLink does not include Tonghuashun, WPS, customer spreadsheets, screenshots, runtime evidence, or packaged binaries. Install those separately and follow their licenses and terms. Do not use the tool to send orders or alter account data.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Changes that affect window activation or keyboard modifiers need focused tests and a clear Windows reproduction case.

## Security

Please see [SECURITY.md](SECURITY.md). Never include credentials, customer files, screenshots, or live desktop evidence in an issue or pull request.

## License

Project code is released under the MIT License. Third-party dependencies remain under their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
