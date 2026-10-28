# Local runtime for offline games

Unmodified minimal runtime from the application's existing Pyodide **0.26.1** distribution:
https://cdn.jsdelivr.net/pyodide/v0.26.1/full/

Included: pyodide.js, pyodide.asm.js, pyodide.asm.wasm, python_stdlib.zip,
pyodide-lock.json and PyYAML 6.0.1 (the only separately loaded package; no dependencies).
The wheel hash is checked against the official lock file by build_pwa.py.
All downloaded runtime/model sizes and SHA-256 hashes are recorded in js/offline-assets.js.
The standard-library ZIP and wheel retain their internal license notices.
Pyodide's MPL-2.0 notice is in 0.26.1/LICENSE; PyYAML's notice is alongside it.

This keeps the existing Python/WASM version and AI behavior. It does not ship
PyTorch, training checkpoints, optimizer states, or unused Pyodide packages.
Use `make build` to regenerate the app and offline inventory.
