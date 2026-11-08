import os
import sys

# Make the backend modules importable as top level modules, the same way
# main.py imports its neighbours.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
