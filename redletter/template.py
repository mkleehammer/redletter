
class Template(object):
    """
    A compiled template.

    code
      The Python code object from a compiled template.
    """
    def __init__(self, code):
        self.code = code


    def execute(self, out, vars=None):
        """
        Executes the template and write the resulting text (e.g. HTML, XHTML, or XML) to `out`.

        out
          A file-like object that the template writes to.  It must support write(str) and flush().  After the template
          has been executed, out.flush() will be called.

        vars
          An optional dictionary of objects to put into the global namespace of the template, using the dictionary key as
          the name.  This can be used to add global variables and global functions.

        Unless overridden by variables in `vars`, two other global variables are added to the template namespace:
          _out
            The `out` parameter, allowing code in the template to write to the stream.
  
          _template
            This Template instance (self).
        """
        localvars = { '_template' : self,
                      '_out'      : out }

        if vars:
            localvars.update(vars)

        self._execute(out, localvars)


    def executev(self, out, **kwargs):
        """
        A "varargs" style version of 'execute' that accepts keyword parameters.

        This version makes all keyword parameters global variables in the template., in addition to '_out' and
        '_template'.
        """
        if '_template' not in kwargs:
            kwargs['_template'] = self
        if '_out' not in kwargs:
            kwargs['_out'] = out

        self._execute(out, kwargs)


    def _execute(self, out, vars):
        exec(self.code) in vars
        out.flush()
