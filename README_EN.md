# HDF5 Viewer

**[中文](README.md)** | **[English](README_EN.md)**

A lightweight HDF5 file viewer with VSCode-style layout, supporting lazy loading for large files, multi-tab split views, Matplotlib visualization, and data editing.

## ✨ Features

- 🎨 **VSCode-style Interface** — Activity Bar + Sidebar + Editor Area + Bottom Panel
- 📑 **Multi-tab + Split** — View multiple files/datasets simultaneously with left/right and top/bottom splits
- 🖱️ **Tab Drag & Drop** — Drag tabs to reorder (detach to separate window not yet enabled)
- 🚀 **Async Loading for Large Files** — Background loading + pagination keeps UI responsive
- 📊 **Matplotlib Visualization** — Line charts, histograms, heatmaps for 1D/2D/3D datasets
- 🔌 **Plugin Panel** — Activity Bar plugin entry with visualizer selection and parameter config
- 🎯 **Command Palette** — `Ctrl+Shift+P` for quick command execution
- 🌗 **Dark/Light Theme** — One-click toggle with auto-persisting config
- 📊 **Dedicated Attributes Tab** — Bottom panel shows attributes; double-click to open value in new tab
- 🔍 **Global Search** — Search HDF5 node paths
- 💾 **Multi-format Export** — CSV + NumPy (.npy) export
- ✏️ **Data Editing Mode** — Toggle edit mode to modify dataset values and save back to file
- 🌐 **Multiple Data Sources** — HDF5 + NetCDF + Zarr (optional dependencies, silently skipped if missing)
- 🌐 **Right Panel Bar** — Search + Plugins in independent right panel, visible alongside Explorer
- 🧪 **121 Test Coverage** — Theme switching, data editing, tab operations, search, plugins, edge cases

## 🚀 Quick Start

### Run from Source

```bash
# Clone the repository
git clone https://github.com/realalvinlog/HDF5-Viewer.git
cd HDF5-Viewer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run
python main.py [file.h5]
```

### Optional Dependencies

NetCDF and Zarr support are optional — install the corresponding packages to enable:

```bash
pip install netCDF4>=1.6.0   # NetCDF support
pip install zarr>=2.14.0     # Zarr support
```

The program runs normally without them; unsupported formats won't appear in the file filter.

### Use Pre-built Version

#### Linux

```bash
python build.py --all
cd dist/HDF5Viewer/
./run.sh [file.h5]
```

#### Windows

```bat
build_windows.bat
dist\HDF5Viewer\HDF5Viewer.exe [file.h5]
```

## 📖 User Guide

### Basic Operations

| Action | Description |
|--------|-------------|
| Open File | `Ctrl+O` or drag & drop file to window |
| Close Tab | `Ctrl+W` |
| Command Palette | `Ctrl+Shift+P` |
| Toggle Sidebar | Click Activity Bar icons |
| Split View | Right-click tab → Split Right / Split Down |
| Drag Tabs | Drag tabs to reorder (detach to window not yet enabled) |
| Right Panel | Click right Activity Bar 🔍/🔌 buttons |
| Toggle Bottom Panel | `Ctrl+J` |
| Search Nodes | `Ctrl+Shift+F` |
| Toggle Theme | Command Palette → Toggle Theme |
| Data Editing | Command Palette → Toggle Edit Mode |

### Command Palette Commands

Press `Ctrl+Shift+P` to open, with fuzzy search support:

| Command | Description |
|---------|-------------|
| Open File | Open file dialog |
| Close Tab | Close current tab |
| Close All Tabs | Close all tabs |
| Toggle Sidebar | Toggle sidebar |
| Toggle Bottom Panel | Toggle bottom panel |
| Toggle Theme | Toggle Dark/Light theme |
| Toggle Edit Mode | Toggle data editing mode |
| Export CSV | Export current dataset as CSV |
| Export NumPy | Export current dataset as .npy |
| Focus Explorer | Focus file tree |
| Focus Search | Focus search |
| Focus Plugin Panel | Focus plugin panel |

### Slice Controls

- **Manual input**: Type `[0:100, :]` in the Slice input box
- **Quick buttons**: First 100 / Last 100 / All
- **Dimension selection**: Choose dimensions for high-dimensional data

### Visualization Plugins

1. Click the 🔌 icon in the Activity Bar to open the plugin panel
2. Select a visualization plugin (Line Chart / Histogram / Heatmap)
3. Plugins auto-filter to match the current data dimensions
4. Click **Run** to visualize; results appear in a new editor tab

| Plugin | Dimensions | Description |
|--------|------------|-------------|
| Line Chart | 1D, 2D | Line plot; 2D data plots one line per row |
| Histogram | 1D | Histogram with automatic binning |
| Heatmap | 2D, 3D | Heatmap; 3D data takes first slice |

### Attributes Viewer

- Switch to the **Attributes** tab in the bottom panel to view attribute list
- **Double-click** an attribute row to open its value in a table view in a new editor tab

### Data Editing

1. Click the **✏️ Edit** button in the tab's Slice toolbar to enter edit mode (each tab has independent control)
2. Double-click a cell to edit its value
3. After editing, click the **💾 Save** button to save

### Tab Operations

| Action | Description |
|--------|-------------|
| Right-click → Split Right | Move tab to a new right-side group |
| Right-click → Split Down | Move tab to a new bottom group |
| Right-click → Close | Close current tab |
| Right-click → Close Others | Close other tabs |
| Right-click → Close All | Close all tabs |
| Drag tab outside tab bar | Detach to separate window |

## 🏗️ Project Structure

```
hdf5-viewer/
├── main.py                    # Entry point
├── config.json                # Configuration
├── core/                      # Core modules
│   ├── datasource.py          # Data source interface + DataMeta/NodeType
│   ├── h5_source.py           # HDF5 implementation
│   ├── event_bus.py           # Event bus
│   ├── slicer.py              # Slice parser
│   ├── cache.py               # LRU cache
│   ├── async_loader.py        # Async loader
│   └── registry.py            # Plugin registry + conditional registration
├── gui/                       # GUI modules
│   ├── main_window.py         # Main window
│   ├── activity_bar.py        # Activity bar
│   ├── command_palette.py     # Command Palette
│   ├── secondary_bar.py       # Right Activity Bar
│   ├── secondary_panel.py     # Right panel (Search + Plugins)
│   ├── sidebar/               # Sidebar
│   │   ├── explorer.py        # HDF5 file tree
│   │   ├── folder_explorer.py # Local folder browser
│   │   └── plugin_panel.py    # Visualization plugin panel
│   ├── editor/                # Editor
│   │   ├── tab_manager.py     # Tab management (Split/drag/context menu)
│   │   ├── file_panel.py      # Dataset panel
│   │   ├── data_table.py      # Data table (edit mode support)
│   │   ├── data_editor.py     # Edit mode toolbar
│   │   └── attr_panel.py      # Attribute value panel
│   ├── status_bar.py          # Status bar
│   └── bottom_panel.py        # Bottom panel (Properties/Attributes/Output)
├── plugins/                   # Plugin system
│   ├── base.py                # Plugin interfaces
│   ├── builtin/               # Built-in plugins
│   │   ├── statistics.py      # Basic statistics
│   │   ├── line_chart.py      # Matplotlib line chart
│   │   ├── histogram.py       # Matplotlib histogram
│   │   └── heatmap.py         # Matplotlib heatmap
│   └── external/              # External data source plugins
│       ├── netcdf_source.py   # NetCDF data source
│       └── zarr_source.py     # Zarr data source
├── services/                  # Services
│   ├── search.py              # Search
│   └── exporter.py            # Export (CSV + NumPy)
└── tests/                     # Tests
```

## 🔧 Configuration

Edit `config.json`:

```json
{
  "ui": {
    "theme": "dark",
    "sidebarWidth": 280
  },
  "folder": {
    "fileFilters": [".h5", ".hdf5", ".hdf", ".h5py", ".nc", ".nc4", ".netcdf", ".zarr"]
  }
}
```

| Field | Description | Default |
|-------|-------------|---------|
| `ui.theme` | Theme: `dark` / `light` | `dark` |
| `ui.sidebarWidth` | Left sidebar width (px) | `280` |
| `ui.secondaryPanelWidth` | Right panel width (px) | `280` |
| `ui.secondaryPanelVisible` | Whether right panel is visible | `false` |
| `folder.fileFilters` | File filter supported extensions | See above |

Theme changes are automatically persisted to `config.json`.

Right panel (Search + Plugins) visibility state is also persisted.

## 🧪 Testing

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

## 📦 Packaging

### Linux

```bash
python build.py --all
```

### Windows

```bat
build_windows.bat
```

Build output is in `dist/HDF5Viewer/`. On Linux, ensure `libxcb-cursor0` is installed:
```bash
sudo apt install libxcb-cursor0
```

## 📋 Version History

### v0.2.1

- ✅ Edit mode buttons embedded in each tab's Slice toolbar (✏️ Edit + 💾 Save, independent per tab)
- ✅ Plugins track most recently active dataset (double-click/search/tab-switch all update plugin panel data source)
- ✅ Right Activity Bar always visible (closing panel only hides content area, not the button bar)
- ✅ Tab detach to separate window temporarily disabled

### v0.2.0

- ✅ Plugin panel UI (Activity Bar 🔌 entry + visualizer selection + parameter config)
- ✅ Matplotlib visualization (line chart/histogram/heatmap, replacing ASCII rendering)
- ✅ Command Palette (Ctrl+Shift+P, 14 commands) + theme-aware switching
- ✅ Tab drag-to-reorder (detach to separate window not yet enabled)
- ✅ Dark/Light theme toggle + config persistence (CommandPalette/SecondaryBar/SecondaryPanel all follow)
- ✅ NetCDF/Zarr conditional registration (optional dependencies, silently skipped if missing)
- ✅ NumPy (.npy) export
- ✅ Data editing mode (Toggle Edit Mode + cell editing + Save back to file)
- ✅ Right panel bar (Search + Plugins in independent panel, visible alongside Explorer)
- ✅ Context menu fixes (Split Right/Down vertical nesting, Close/Others/All all working)
- ✅ Split Down with true vertical nesting (QSplitter nesting)
- ✅ 121 test coverage

### v0.1.0

- Initial release
- VSCode-style interface
- HDF5 file browsing + async loading
- Multi-tab + Split
- CSV export
- Global search
- Attributes viewer

## 📄 License

MIT License
