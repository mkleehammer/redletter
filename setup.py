#!/usr/bin/python

major    = 2
minor    = 1
revision = 8

import os, sys, re
from os.path import join
from distutils.core import setup, Command

class BaseCommand(Command):
    user_options = [ ]

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass


class TestCommand(BaseCommand):

    description = "Compiles the PSPs in the examples directory."

    def run(self):
        from redletter import translator, templatesource

        source = templatesource.FastDirectorySource('example', 'example')
        t      = translator.Translator(source)
        
        r = re.compile(r'^test.*\.psp$')

        for name in os.listdir('example'):
            if r.match(name):
                outname = '%s-result.html' % name[:-4]
                print '  %s --> %s' % (name, outname)
                template = source.get_template(name)
                out = file(join('example', outname), 'wb')
                template.executev(out, var='testing', var2='a & b')
                out.close()

    

setup(name="redletter",
      version="%s.%s.%s" % (major, minor, revision),
      author="Michael Kleehammer",
      author_email="mkleehammer@sourceforge.net",
      maintainer="Michael Kleehammer",
      maintainer_email="mkleehammer@sourceforge.net",
      packages=['redletter'],

      description='A line-oriented template system for Python.',

      classifiers=[ 'Development Status :: 5 - Production/Stable',
                    'Environment :: Console',
                    'Intended Audience :: Developers',
                    'License :: OSI Approved :: MIT License',
                    'Operating System :: OS Independent',
                    'Programming Language :: Python',
                    'Topic :: Software Development :: Build Tools',
                    ],
      options={'sdist' : {'force_manifest' : True}},
      cmdclass = dict(test=TestCommand),
      )
