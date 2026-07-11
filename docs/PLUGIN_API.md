# Plugin API v1

## 1. Purpose and trust model

Plugins provide incremental analysis and visualization without importing GUI internals or format-library handles. Data Viewer v1 ships trusted built-in plugins only. Third-party discovery, installation, permissions, process isolation, signing, and marketplace distribution are future work and must not be implied by v1 UI.

The public contract has `api_version = 1`. Breaking changes require a new API version, migration guidance, compatibility tests, and an ADR.

## 2. Package boundary

```text
data_viewer/
  plugins/
    api.py              # public types only
    registry.py         # manifest discovery and validation
    runner.py           # task integration
    results.py          # result validation/materialization
    builtin/
      dataset_profile/
        plugin.json
        plugin.py
        tests/
```

A plugin may import `data_viewer.plugins.api` and documented domain value types. It must not import `data_viewer.gui`, adapters, controllers, private modules, or another plugin's internals.

## 3. Manifest

Every plugin directory contains `plugin.json`:

```json
{
  "schema_version": 1,
  "api_version": 1,
  "id": "org.dataviewer.dataset_profile",
  "name": "Dataset Profile",
  "version": "1.0.0",
  "description": "Summarizes shape, dtype, missingness, and finite-value ranges.",
  "entry_point": "data_viewer.plugins.builtin.dataset_profile.plugin:DatasetProfilePlugin",
  "kind": "analysis",
  "input": {
    "domains": ["array", "table"],
    "min_ndim": 1,
    "max_ndim": null,
    "dtype_families": ["boolean", "integer", "floating", "complex"],
    "requires_random_access": false,
    "supports_chunked_input": true,
    "supports_selection": true
  },
  "parameters_schema": {
    "type": "object",
    "properties": {
      "nan_policy": {"type": "string", "enum": ["omit", "propagate"], "default": "omit"}
    },
    "additionalProperties": false
  },
  "result_kinds": ["summary", "table"]
}
```

Rules:

- `id` is globally stable reverse-DNS text and never reused for another meaning.
- `version` uses semantic versioning.
- `entry_point` must resolve inside the installed Data Viewer package in v1.
- The manifest is JSON Schema validated before importing plugin code.
- UI names/descriptions are display text; logic keys use stable IDs.
- Unknown manifest keys are rejected in v1 to catch misspellings.

## 4. Runtime contract

```python
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Iterator, Mapping, Protocol, Sequence

import numpy as np
from numpy.typing import NDArray

class ResultKind(StrEnum):
    SUMMARY = "summary"
    TABLE = "table"
    ARRAY = "array"
    IMAGE = "image"
    PLOT = "plot"
    COLLECTION = "collection"

@dataclass(frozen=True)
class InputDescriptor:
    source_id: str
    source_fingerprint: Mapping[str, object]
    resource_path: str
    domain: str
    shape: tuple[int, ...] | None
    dtype: str | None
    selection: Mapping[str, object]
    estimated_elements: int | None
    estimated_bytes: int | None

@dataclass(frozen=True)
class DataChunk:
    values: NDArray[np.generic]
    origin: tuple[int, ...]
    selection: Mapping[str, object]
    is_last: bool

class InputAccess(Protocol):
    descriptor: InputDescriptor
    def read(self, selection: Mapping[str, object]) -> NDArray[np.generic]: ...
    def iter_chunks(self, target_bytes: int) -> Iterator[DataChunk]: ...

@dataclass(frozen=True)
class PluginContext:
    run_id: str
    inputs: tuple[InputAccess, ...]
    parameters: Mapping[str, object]
    memory_budget_bytes: int
    temp_budget_bytes: int
    is_cancelled: Callable[[], bool]
    report_progress: Callable[[float | None, str], None]
    emit_warning: Callable[[str, str], None]

@dataclass(frozen=True)
class ResultProvenance:
    plugin_id: str
    plugin_version: str
    api_version: int
    inputs: tuple[InputDescriptor, ...]
    parameters: Mapping[str, object]
    computation_scope: str
    sampled: bool

@dataclass(frozen=True)
class PluginResult:
    kind: ResultKind
    title: str
    payload: object
    provenance: ResultProvenance
    metadata: Mapping[str, object]
    warnings: tuple[str, ...] = ()

class DataViewerPlugin(Protocol):
    def run(self, context: PluginContext) -> PluginResult: ...
```

Actual code must use the canonical domain selection/value types rather than duplicate dictionary shapes. The abbreviated mappings above define serialization boundaries.

## 5. Compatibility decision

Compatibility is computed before enabling Run:

1. every selected input domain is allowed;
2. dimension bounds match;
3. dtype family is allowed;
4. selection requirements are satisfied;
5. random/chunked access requirements match adapter capabilities;
6. estimated size is within plugin and application budgets or the plugin supports chunking/sampling;
7. multi-input count and shape/alignment rules match;
8. required optional dependencies are available.

Disabled plugins show the exact reasons. They are not hidden, because discoverability and remediation matter.

## 6. Parameter schema

`parameters_schema` uses a documented JSON Schema subset:

- object, string, integer, number, boolean, array;
- enum, minimum/maximum, minItems/maxItems, default, title, description;
- `ui:widget` hints for axis selector, colormap, resource selector, and range;
- conditional schemas are excluded from v1 unless the form renderer gains tested support.

The UI builds a standard parameter panel, validates locally, and passes immutable JSON-safe values. Plugins do not create modal GUI dialogs.

## 7. Execution

- Every run is a `Task` with queued/running/succeeded/failed/cancelled states.
- Plugin code runs outside the GUI thread.
- Cancellation is cooperative; loops and chunk boundaries check `is_cancelled()`.
- Progress is `0.0..1.0` or indeterminate and includes a short phase label.
- Memory and temporary-disk budgets are declared and enforced by input access and result validation.
- Plugins request data through `InputAccess`; they never receive h5py, pandas, NiBabel, openpyxl, or session handles.
- Exceptions are converted to `PluginError`; full traceback goes to diagnostics, while the UI receives a safe summary and remediation.
- A cancelled or failed run publishes no partial final result. Optional preview events are ephemeral and clearly marked.

V1 trusted built-ins may use the shared process. The API deliberately avoids GUI/session handles so a later process-isolated runner can preserve the same plugin contract.

## 8. Results

### Summary

JSON-safe labeled metrics with units, descriptions, and warning status.

### Table

A typed column schema plus bounded records or a Data Viewer-owned tabular result store. pandas objects do not cross the public boundary.

### Array/image

An ndarray plus axes, coordinates, units, value semantics, and source-selection mapping. Large results use a Data Viewer-owned temporary result store.

### Plot

A declarative `PlotSpec`, not a Matplotlib `Figure`. Required v1 marks: line, scatter, histogram, box, heatmap, image. The renderer owns theme, accessibility, export, and lifecycle.

### Collection

An ordered group of the above with a shared provenance record.

All results display plugin/version, exact inputs, selection/scope, parameters, sampled/full status, warnings, and creation time. Copy and export include the same provenance.

## 9. Built-in v1 catalog

### Statistics and analysis

- Dataset Profile: shape, dtype, storage, finite/missing counts, ranges.
- Descriptive Statistics: count, mean, standard deviation, quantiles, extrema, configurable axes.
- Distribution Summary: histogram, robust spread, skewness/kurtosis when valid, sampled labeling.
- Correlation/Covariance: selected numeric columns/axes with missing policy.
- Dataset Compare: compatibility, shape/dtype differences, absolute/relative errors, equality counts.

### Visualization

- Line Plot
- Scatter Plot
- Histogram
- Box Plot
- Image Viewer
- 3D+ Slice Navigator
- Correlation Heatmap
- Missing Data Map
- NIfTI Orthogonal Viewer and header/coordinate inspector

Each catalog entry is its own manifest/package and may ship incrementally without changing the runner.

## 10. Numerical and sampling rules

- Default computation scope is explicit: full resource, current slice, selection, filtered rows, or sample.
- Sampling never occurs silently. Results state method, seed, requested size, actual size, and population estimate.
- Stable algorithms are required for large sums/variance; expected tolerance is dtype-aware.
- `NaN`, infinity, complex numbers, masked/missing values, strings, booleans, and empty inputs have documented behavior.
- Dataset Compare refuses ambiguous broadcasting or alignment.
- Random operations use a recorded seed.

## 11. Registry behavior

At startup the registry:

1. enumerates only packaged built-in manifest locations;
2. validates manifests without importing code;
3. checks duplicate IDs and supported API versions;
4. imports eligible entry points lazily on first run;
5. records unavailable plugins and diagnostics without failing application startup.

Plugin ordering is deterministic by category, configured order, then localized name.

## 12. Conformance suite

Every plugin must pass reusable tests for:

- manifest/schema and unique ID;
- compatibility: enabled and every disabled reason;
- parameter defaults/validation/round trip;
- cancellation and progress monotonicity;
- memory budget and chunked access behavior;
- safe error conversion;
- deterministic known-input numerical result;
- empty, scalar, missing, infinite, nonnumeric, and oversized input behavior as applicable;
- result/provenance schema;
- no imports from forbidden GUI/adapter modules;
- Windows and Linux execution.

## 13. Example minimal plugin

```python
import numpy as np

from data_viewer.plugins.api import PluginResult, ResultKind, ResultProvenance

class RangePlugin:
    def run(self, context):
        minimum = None
        maximum = None
        for chunk in context.inputs[0].iter_chunks(target_bytes=8 * 1024 * 1024):
            if context.is_cancelled():
                raise PluginCancelled()
            values = np.asarray(chunk.values)
            finite = values[np.isfinite(values)]
            if finite.size:
                part_min = finite.min().item()
                part_max = finite.max().item()
                minimum = part_min if minimum is None else min(minimum, part_min)
                maximum = part_max if maximum is None else max(maximum, part_max)
        return PluginResult(
            kind=ResultKind.SUMMARY,
            title="Finite range",
            payload={"minimum": minimum, "maximum": maximum},
            provenance=ResultProvenance.from_context(context, sampled=False),
            metadata={},
        )
```

Canonical implementation types may differ slightly, but chunking, cancellation, safe results, provenance, and absence of GUI access are mandatory.
