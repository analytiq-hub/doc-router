import os
import sys

# Ensure `packages/python` is on sys.path so `import analytiq_data` works
cwd = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.normpath(os.path.join(cwd, "..")))

