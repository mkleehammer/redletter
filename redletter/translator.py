
import os, re, sys, codecs
from datetime import datetime
from cStringIO import StringIO
from os.path import abspath, isabs, join, dirname

if sys.version_info[:2] < (2, 4):
    from sets import Set as set

try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO

re_directive   = re.compile(r'^\s*<%@\s+(.+)%>\s*$')
re_block_open  = re.compile(r'^\s*<(?P<keyword>for|if|while)\s+(?P<exp>[^>]+)>\s*$')
re_block_close = re.compile(r'^\s*</(?P<keyword>for|if|while)\s*>\s*$')

re_expression = re.compile(r'\$\{ (?P<exp>.*?) \}', re.VERBOSE)
re_filters = re.compile(r'(?<![|])\|(?![|])')

re_else        = re.compile(r'^\s*<else>\s*$')
re_elif        = re.compile(r'^\s*<elif\s+(?P<exp>[^>]+)>\s*$')
re_code_open   = re.compile(r'^\s*{%\s*$')
re_code_close  = re.compile(r'^\s*%}\s*$')
re_code_inline = re.compile(r'^\s* %\{ (.+) \} \s* $', re.VERBOSE)

re_comment_inline = re.compile(r'{--.*?--}')
re_comment_start  = re.compile(r'\s*{--.*')
re_comment_end    = re.compile(r'.*--}\s*')

re_leading_ws = re.compile(r'^\s*')

esc_func = """
def tostr(s):
    return (s is not None) and str(s) or ''

import urllib, cgi
import xml.sax.saxutils

filter_esc   = cgi.escape
filter_quote = xml.sax.saxutils.quoteattr
filter_url   = urllib.quote
def filter_attr(s):
    return cgi.escape(s, True)

filter_e = filter_esc
filter_a = filter_attr
filter_q = filter_quote
filter_u = filter_url
"""

class TranslateError(Exception):

    def __init__(self, filename, lineno, msg):
        Exception.__init__(self, msg) # '"%s", line %d: %s' % (filename, lineno, msg))
        self.filename = filename
        self.lineno   = lineno

    def __str__(self):
        # Format in an Unix/emacs/vi-friendly way
        return '"%s", line %d: %s' % (abspath(self.filename), self.lineno, self.args[0])


class Translator(object):
    """
    Translates Redletter templates to Python source.
    """
    def __init__(self, ts=None, in_codec=None, out_codec=None):
        """
        The following apply to all templates translated with this instance:

        ts
          An optional TemplateSource, used to load included templates.  If not supplied, an exception is raised if a
          template attempts to include another.
        """
        self.ts = ts

        #
        # The following are valid during a translation, then reset.
        #

        # self.expr_flags = EXPFLAG_NONE_CHECK | EXPFLAG_TYPE_UNICODE

        # The template input is read from this StreamReader.  The default is UTF-8, but this can be overridden if a
        # custom StreamReader is supplied.
        self.reader = None
        self.readercls = codecs.getreader('utf_8')

        # Generated code is written to this StreamWriter to UTF-8 encode it before writing it to a StringIO object.
        self.writer = None
        self.writercls = codecs.getwriter('utf_8')

        # If True, we have already begun an 'out.write(...' call in the buffer.  When we encounter dynamic content, we
        # close the write call if this is true.

        # Static content is copied from the templates into triple quoted strings, referred to as a fragment.  Once we
        # start writing a fragment, we don't put the closing quotes on until we hit dynamic content or the end of the
        # template.  This Boolean tells us whether we've opened the quotes or not.
        self.in_fragment = False

        # A string printed before each line to maintain the current indentation level.
        self.indentation = None

        # The name of the current template, used in error messages.
        self.name = None

        # Tracks the line number during translation so it can be reported in errors.
        self.lineno = None

        # The EXPFLAG_ESC_xxx flags used, so we know which functions to write to the file.
        # self.expr_flags_used = 0


    def translate(self, name, input):
        """
        Returns the Python code generated from a Redletter template.

        input
          The template to translate, either as a file-like object, a codecs.StreamReader object, a string object, or a
          Unicode object.  If a StreamReader is not supplied, input will be assumed to be in UTF-8.
        """
        out = StringIO()
        self.writer = self.writercls(out)

        self.indentation = ''
        self.parent      = None

        self._translate(name, input)

        self.writer.reset()
        source = out.getvalue()

        return source


    def _translate(self, name, input, parent=None):
        """
        The internal translation function that performs the actual translation.

        parent
          Optional parent translator, used when including templates.  When a child template is being included, escape
          functions are handled by the top-level parent to ensure they are included only once and at the top of the
          generated source.  Most settings are copied from the parent.
        """
        self.name = name

        if isinstance(input, codecs.StreamReader):
            self.reader = input
        else:
            if isinstance(input, basestring):
                input = StringIO(input)
            self.reader = self.readercls(input)

        self.parent = parent

        self.lineno      = 0
        self.in_fragment = False

        if self.parent:
            self.writer      = parent.writer
            self.indentation = parent.indentation

        else:
            self._write_dynamic('# Generated %s' % str(datetime.now())[:19])
            self.writer.write(esc_func)
            self.writer.write('\n')

        while 1:
            line = self.reader.readline()
            if not line:
                break

            self.lineno += 1

            # Remove inline comments <%-- xxx --%>

            cleaned = self._remove_inline_comments(line)
            if line != cleaned and not cleaned.strip():
                # There was nothing on the line except a comment.  Remove the line completely.
                continue
            line = cleaned

            # If we are starting a comment block, eat all lines until the end of the block.

            if re_comment_start.match(line):
                self._skip_past_comment()
                continue

            m = re_block_open.match(line)
            if m:
                self._open_block(m.group('keyword'), m.group('exp'))
                continue

            if re_block_close.match(line):
                self._close_block()
                continue

            m = re_directive.match(line)
            if m:
                self._directive(m.group(1))
                continue

            m = re_else.match(line)
            if m:
                self._else_block()
                continue

            m = re_elif.match(line)
            if m:
                self._elif_block(m.group('exp'))
                continue

            m = re_code_inline.match(line)
            if m:
                self._write_dynamic(m.group(1).strip())
                continue

            m = re_code_open.match(line)
            if m:
                self._code_block()
                continue

            m = re_expression.search(line)
            if m:
                while m:

                    start,stop = m.span()
                    if start:
                        self._write_static(line[:start])

                    self._expression(m.group('exp'))

                    line = line[stop:]
                    m = re_expression.search(line)

                if line:
                    self._write_static(line)
            else:
                self._write_static(line)

        # Close the last out.write.
        self._write_dynamic('\n')

    def _expression(self, expr):

        filters = re_filters.split(expr)
        expr = filters[0].strip()

        filters = [ 'filter_%s' % f.strip() for f in filters[1:] ]

        # Filters must be applied in the order they appear in the template, so we have to reverse them here.  The
        # innermost function will be called first.
        filters.reverse()

        filters.append('tostr')
        filters.append(expr)

        parts = [ '_out.write(',
                  '('.join(filters),
                  ')' * len(filters),
                  '' ]
        self._write_dynamic(''.join(parts))

    def _code_block(self):
        """
        Process a code block (<% %>).

        Reads each line until '%>' is found and copy the code verbatim into the output file.  Because Python is
        indentation sensitive, the indentation of the entire block is adjusted to match the current indentation level
        of the output code.
        """

        # Since we don't consider translating to be performance critical, we use a simple approach of removing all
        # indentation and adding the necessary amount back.

        code = []
        while 1:
            line = self.reader.readline()
            if not line:
                break
            self.lineno += 1
            if re_code_close.match(line):
                break
            code.append(line)

        cch = 9999
        for line in code:
            cch = min(cch, len(re_leading_ws.search(line).group(0)))

        self._write_dynamic(self.indentation.join([ line[cch:] for line in code ]))


    def _remove_inline_comments(self, line):
        """
        Removes inline comments from the line and returns the rest.
        """
        m = re_comment_inline.search(line)
        while m:
            start,stop = m.span()
            line = line[:start] + line[stop:]
            m = re_comment_inline.search(line)
        return line


    def _skip_past_comment(self):
        """
        Called when we have started a comment block (a '<%--' by itself on a line).  All lines are skipped until we
        find the close of the comment ('--%>').
        """
        while 1:
            line = self.reader.readline()
            if not line:
                break
            self.lineno += 1
            if re_comment_end.match(line):
                break


    def _write_static(self, text):
        """
        Write static Unicode text (part of an out.write) to the output, starting the write call if necessary.

        If an output codec has been defined, `text` will be encoded with it.  Otherwise it will be encoded as UTF 8.
        """
        if "'''" in text or text.endswith("'"):
            # We're going to use triple quotes, so we don't want any inside the text turning them off.  We also don't
            # want the text to end with a single quote which would be added to our ending quotes.  We'll have to escape
            # them.  Since technically there could be 20 quotes in a row, we're not going to be clever at this point
            # and try to only escape the triples; we'll escape them all right now.
            text = text.replace("'", "\\'")

        if not self.in_fragment:
            self.in_fragment = True
            self.writer.write("%s_out.write('''" % self.indentation)
        self.writer.write(text)


    def _close_fragment(self):
        if self.in_fragment:
            self.in_fragment = False
            self.writer.write('\n')

    def _write_dynamic(self, text):
        """
        Write dynamic text, closing the current out.write if necessary.
        """
        if not text:
            return

        if self.in_fragment:
            self.in_fragment = False
            self.writer.write("''')\n")
        self.writer.write(self.indentation)
        self.writer.write(text)

        if text[-1] != '\n':
            self.writer.write('\n')


    def _open_block(self, keyword, exp):
        self._write_dynamic('%s %s:\n' % (keyword, exp))
        self.indentation += '    '


    def _close_block(self):
        """
        Called when a block close tag (e.g. </if>) is found.  Reduces the current indentation.
        """
        if self.in_fragment:
            # We're in a template fragment which we must end.
            self.in_fragment = False
            self.writer.write("''')\n\n")
        self.indentation = self.indentation[:-4]


    def _else_block(self):
        self.indentation = self.indentation[:-4]
        self._write_dynamic('else:\n')
        self.indentation += '    '


    def _elif_block(self, expr):
        self.indentation = self.indentation[:-4]
        self._write_dynamic('elif %s:\n' % expr)
        self.indentation += '    '


    def _directive(self, expr):

        parts = expr.strip().split(None, 1)
        if len(parts) == 1:
            keyword, args = parts[0], None
        else:
            keyword, args = parts

        if keyword == 'include':
            self._include_template(args)
        else:
            raise TranslateError(self.name, self.lineno, 'Unknown directive: %s' % keyword)


    def _include_template(self, childname):

        # REVIEW: Recursion is not handled (e.g. A includes B; B includes C; C includes A).

        if self.ts is None:
            raise Exception('The template %s attempted to include %s, but no TemplateSource was supplied to the translator.' % (self.name, childname))

        self._write_dynamic('# begin include %s\n' % childname)

        # At this point, we are allowing another object ('c' below) to write to self.out, so we must not be in an
        # out.write call.  The _write_dynamic above closes this, but this assertion is to make sure future changes
        # don't break this.
        assert not self.in_fragment, "Close current fragment before include."

        t = Translator(self.ts)
        t._translate(childname, self.ts.get_content(childname), parent=self)

        self._write_dynamic('# end include %s\n\n' % childname)
