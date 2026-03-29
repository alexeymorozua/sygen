# Fileshare Server

Built-in HTTP file exchange server. Agents write files to `downloads/` and users upload files via the browser UI into `uploads/`.

## Enabling

Add to your `config.json`:

```json
{
    "fileshare": {
        "enabled": true,
        "host": "127.0.0.1",
        "port": 8090
    }
}
```

Restart the bot after changing the config.

## Configuration

| Field     | Default       | Description                    |
|-----------|---------------|--------------------------------|
| `enabled`            | `false`       | Enable the fileshare server                        |
| `host`               | `"127.0.0.1"` | Bind address                                       |
| `port`               | `8090`        | Listen port                                        |
| `auto_cleanup_days`  | `7`           | Delete files older than N days (0 = disable)       |

For access over Tailscale or LAN, set `host` to your machine's network address (e.g. `100.x.x.x` for Tailscale).

## Directory Layout

```
~/.sygen/fileshare/
    uploads/      # Files uploaded by users via browser
    downloads/    # Files placed by agents for download
```

Directories are created automatically on startup.

## Routes

| Method | Path                    | Description                          |
|--------|-------------------------|--------------------------------------|
| GET    | `/`                     | Browser UI with drag-and-drop upload |
| GET    | `/uploads/{filename}`   | Download a user-uploaded file        |
| GET    | `/downloads/{filename}` | Download an agent-provided file      |
| GET    | `/download/{filename}`  | Alias for `/downloads/{filename}`    |
| POST   | `/upload`               | Multipart file upload endpoint       |

## Integration with send_large_file.py

When the fileshare server is running, the environment variables `FILESHARE_URL` and `FILESHARE_DOWNLOADS` are set automatically. The `send_large_file.py` tool detects these and copies large files (>45 MB) into the downloads directory instead of uploading to external services.

The tool constructs URLs like `{FILESHARE_URL}/download/{filename}` which the server handles via the `/download/` alias route.

## Web UI

Open `http://{host}:{port}/` in a browser to:

- Drag and drop files to upload them
- Browse and download files from both uploads and downloads directories

## Auto-Cleanup

Files in `uploads/` and `downloads/` are automatically cleaned up in two ways:

1. **On bot startup** — files older than `auto_cleanup_days` are removed.
2. **Weekly cleanup cron** — the built-in `weekly-cleanup` task also respects this setting.

Set `auto_cleanup_days` to `0` to disable automatic cleanup entirely.

## Security Notes

- The server has **no authentication**. Only bind to private/trusted networks.
- For Tailscale users: bind to your Tailscale IP to restrict access to your tailnet.
- Do not expose to the public internet without adding an auth layer in front.
- Path traversal is blocked (`..` in filenames is rejected).
