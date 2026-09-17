import os, sys
# Ensure the project root (which may contain spaces) is in sys.path for imports like `backend`.
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
