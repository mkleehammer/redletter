"""
Utilities for integrating with mod_python.
"""

class ModPythonAdapter:
    """
    Adapts Redletter PSP templates to mod_python.

    The mod_python `request.write` method accepts 2 parameters, but the Redletter generated code calls write with 1.
    The additional parameter is a Boolean indicating whether to flush the stream which we always set to False.
    """
    def __init__(self, request):
        self.request = request

    def write(self, value):
        self.request.write(value, False)

    def flush(self):
        self.request.flush()

