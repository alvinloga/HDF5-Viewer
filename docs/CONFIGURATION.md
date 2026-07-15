# Data Viewer Configuration v1

## Purpose

Application configuration stores machine-local preferences and infrastructure limits. It is separate from `.dvw` workspaces and from scientific source files.

## Location

Target configuration uses platform-standard directories via `platformdirs`:

- config: `user_config_dir("Data Viewer", "Data Viewer")`
- cache: `user_cache_dir("Data Viewer", "Data Viewer")`
- logs: `user_log_dir("Data Viewer", "Data Viewer")`

Tests and packaged smoke checks may override locations with:

- `DATA_VIEWER_CONFIG_DIR`
- `DATA_VIEWER_CACHE_DIR`
- `DATA_VIEWER_LOG_DIR`

These overrides are intended for isolation and diagnostics; tests must use temporary paths and must not write the repository `config.json`.

## Schema

The current schema version is `1`. Writers emit UTF-8 JSON with a trailing newline.

```json
{
  "schema_version": 1,
  "ui": {
    "theme": "light",
    "sidebar_width": 280,
    "secondary_panel_width": 280,
    "secondary_panel_visible": false
  },
  "cache": {
    "max_bytes": 536870912,
    "max_entries": 128,
    "max_age_days": 7,
    "allow_disk_pressure_fallback": true
  },
  "logging": {
    "level": "INFO",
    "console_level": "INFO",
    "file_enabled": true,
    "file_max_bytes": 10485760,
    "file_backups": 3,
    "sensitive_paths": [],
    "sensitive_values": []
  }
}
```

Unsupported, corrupt, or invalid target config is backed up and replaced at runtime with safe defaults. Existing newer or current target config is never overwritten by legacy migration.

## Legacy repository config migration

The historical repository-local `config.json` remains a legacy input only. DV-1004 provides a safe migration service with these rules:

- read and validate the legacy file without modifying it;
- preview known UI keys before writing anything;
- ignore unknown keys with warnings;
- corrupt legacy config produces warnings and safe defaults;
- explicit `MIGRATE` writes the target platform config atomically;
- explicit `DECLINE` leaves both legacy and target files unchanged;
- existing target config blocks migration so stale repository config cannot downgrade user preferences.

Currently migrated legacy keys:

| Legacy key | Target key |
|---|---|
| `ui.theme` | `ui.theme` |
| `ui.sidebarWidth` | `ui.sidebar_width` |
| `ui.secondaryPanelWidth` | `ui.secondary_panel_width` |
| `ui.secondaryPanelVisible` | `ui.secondary_panel_visible` |

The target bootstrap prepares platform paths and a migration preview on startup but does not silently modify the legacy file.
