## Useful on this box
- Python projects use `uv` (`uv venv`, `uv pip install`); there's no conda. Each project has its own `.venv`; run tests with it on PATH (`PATH=$PWD/.venv/bin:$PATH python -m pytest ...`), because some tests spawn `python3` subprocesses. Node 22 and Bun are installed.
{{OPS_NOTE}}
