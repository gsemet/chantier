"""`chantier serve`: the web board's server (starlette and uvicorn, pinned in the root
pyproject.toml and imported lazily). It is the surface server: it reads the record the CLI keeps,
writes only its entries of `server.json` in the git folder, runs the forge hub, and knows no
role."""
