# Repository instructions

For a user asking to install this project, read `INSTALL.md` and execute its host-specific path. Do not interpret installation as permission to create stories, upload videos or start paid tasks.

For development:
- The distributable skill is `skills/drama-studio/`; keep it self-contained.
- Local tools require only Python 3.10+ standard library. Do not introduce provider credentials or a new model runtime.
- mali-story owns remote tasks, billing and adopted story state. Discover live capabilities before use; source code is not deployment evidence.
- Preserve local edits during installation and upgrades. Never overwrite an unowned skill directory or user-modified installation.
- Keep user projects, private references, credentials and videos outside the distribution.
- Run `python3 -B -m unittest discover -s tests -v` and `python3 -B scripts/validate.py` after relevant changes.
- Report installation, host discovery, MCP authorization, business reads and end-to-end creative acceptance separately.
- Document new commands in README.md. No publication or new license is implied by a local change.
