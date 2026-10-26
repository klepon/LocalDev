# LocalDev

A Windows desktop app (PySide6) for managing local Node/Cloudflare projects, similar to Local WP.

- Project list on the left, details on the right.
- Start/stop the dev server, open it in the browser, the project folder, or VS Code.
- Wrangler login status (check, login, logout).
- D1 migrations (local, staging, production) and Cloudflare deploys (preview, production), with typed confirmation for production.
- Other `package.json` scripts, with a log tab per command.

Actions are detected automatically from the project's `package.json` `scripts`.

## Running

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
LocalDev.bat
```

## Building an .exe

```
build.bat
```

The app is written to `dist\LocalDev\LocalDev.exe`; keep the whole `dist\LocalDev` folder together.

The project list is stored in `%APPDATA%\LocalDev\projects.json`; window size and position in the registry under `HKCU\Software\LocalDev`.
