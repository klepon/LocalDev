# LocalDev

Aplikasi desktop Windows (PySide6) untuk mengelola project Node/Cloudflare lokal, mirip Local WP.

- Daftar project di kiri, detail di kanan.
- Start/stop dev server, buka di browser, folder, atau VS Code.
- Status login Wrangler (cek, login, logout).
- Migrasi D1 (local, staging, production) dan deploy Cloudflare (preview, production) dengan konfirmasi untuk production.
- Script lain dari `package.json` dan log per perintah.

Aksi dibaca otomatis dari `scripts` di `package.json` project.

## Menjalankan

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
LocalDev.bat
```

Daftar project disimpan di `%APPDATA%\LocalDev\projects.json`; ukuran jendela di registry `HKCU\Software\LocalDev`.
