"""MarkLogic IPython extension"""
__version__ = "0.0.1"

from .magics import MarkLogicMagics

def load_ipython_extension(ipython):
    magics = MarkLogicMagics(ipython)
    ipython.register_magics(magics)