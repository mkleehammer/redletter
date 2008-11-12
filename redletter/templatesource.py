"""
Contains the TemplateSource abstract class which handles loading template files, compiling them to Python source, and
caches the resulting Template objects.

Example implementations are provided.  The DirectorySource and FastDirectorySource classes load templates from a
directory; the DirectorySource will reload them if they are modified.  The ZipFileSource class loads templates from a
zip file.  All 3 examples cache all templates indefinitely and are intended for small numbers of templates.
"""

from os.path import join, getmtime, abspath
from cStringIO import StringIO
from translator import Translator
from template import Template


class TemplateSource(object):
    def get_template(self, name):
        """
        Returns a Template object translated from template `name`.

        This is called each time a template is requested, so it may be prudent to cache the templates.
        """
        raise NotImplementedError()

    def get_content(self, name):
        """
        Returns the contents of file `name`.  This is only called when included a template, which only occurs when one
        is loaded.  It should not be necessary to cache here.
        """
        raise NotImplementedError()
    
    def translate(self, name, content):
        t = Translator(ts=self)
        return t.translate(name, content) # Turn PSP source to Python source

    def compile(self, name, source):
        """
        Compiles the contents of a template file (.psp) and returns a Template object.
        """
        code = compile(source, name, "exec") # Compile Python source to byte codes
        return Template(code)                    # Wrap the byte-codes in a Template object.
        

class DirectorySource(TemplateSource):
    """
    An implementation of TemplateSource that loads templates from a single directory.  All templates are cached and
    their modification times are checked on every access so templates can be reloaded when modified.
    """
    def __init__(self, path, savepath=None):
        """
        savepath
          An optional directory where generated source should be saved, useful for debugging templates.
        """  
        self.path     = path
        self.savepath = savepath
        # Contains (template, mtime, fully-qualified filename); we keep the fqn to speed up modification time checks.
        self.cache  = {}

    def get_content(self, name):
        return file(join(self.path, name), 'rb').read()

    def get_template(self, name):
        try:
            template, mtime, fqn = self.cache[name]

            newmtime = getmtime(fqn)
            if newmtime == mtime:
                return template

        except KeyError:
            fqn = join(self.path, name)
            newmtime = getmtime(fqn)

        content = file(fqn, 'rb').read()
        source  = self.translate(name, content)

        if self.savepath:
            fd = file(join(self.savepath, name + '.py'), 'wb')
            fd.write(source)
            fd.close()

        template = self.compile(name, source)

        # self.cache[name] = (template, newmtime, fqn)

        return template


class FastDirectorySource(TemplateSource):
    """
    An implementation of TemplateSource that loads templates from a single directory, but does not reload them.  This
    is faster than DirectorySource.
    """
    def __init__(self, path, savepath=None):
        """
        savepath
          An optional directory where generated source should be saved, useful for debugging templates
        """  
        self.path     = path
        self.savepath = path
        # Contains just the template.
        self.cache = {}

    def get_content(self, name):
        return file(join(self.path, name), 'rb').read()

    def get_template(self, name):
        try:
            return self.cache[name]

        except KeyError:
            pass

        fqn = join(self.path, name)
        content = file(fqn, 'rb').read()
        source  = self.translate(name, content)

        if self.savepath:
            fd = file(join(self.savepath, name + '.py'), 'wb')
            fd.write(source)
            fd.close()

        template = self.compile(name, source)

        self.cache[name] = template

        return template


class ZipFileSource(TemplateSource):
    """
    A TemplateSource implementation that loads files from a single directory in a zip file.
    """
    def __init__(self, filename, path):
        # Note: The import is intentionally put here so that it is not required unless this class is actually used,
        # useful when freezing scripts with programs like py2exe.
        TemplateSource.__init__(self)
        import zipfile             
        self.zip   = zipfile.ZipFile(filename, 'r')
        self.path  = path
        self.cache = {}

    def get_content(self, name):
        return self.zip.read('%s/%s' % (self.path, name))

    def get_template(self, name):
        try:
            return self.cache[name]
        except KeyError:
            pass

        try:
            content  = self.get_content(name)
            source   = self.translate(name, content)
            template = self.compile(name, source)
            self.cache[name] = template
            return template
        except KeyError:
            raise IOError('%s not found' % name, 2)
