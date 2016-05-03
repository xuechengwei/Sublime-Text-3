
# Copyright (C) 2013 - Oscar Campos <oscar.campos@member.fsf.org>
# This program is Free Software see LICENSE file for details

import sys
import logging

try:
    import html
except ImportError:
    # python2 faillback
    import cgi
    from HTMLParser import HTMLParser

from .base import Command


class Doc(Command):
    """Get back a python definition where to go
    """

    def __init__(self, callback, uid, script, html):
        self.script = script
        self.html = html
        super(Doc, self).__init__(callback, uid)


    def run(self):
        """Run the command
        """

        processed = []
        try:
            definitions = self.script.goto_definitions()
        except Exception as error:
            logging.debug(error)
            definitions = []

        if not definitions:
            success = False
            docs = []
        else:
            docs = []
            success = True
            for definition in definitions:
                if definition not in processed:
                    docs.append(
                        self._plain(definition) if not self.html
                        else self._html(definition)
                    )
                    processed.append(definition)

        self.callback({
            'success': success,
            'doc': ('<br><br>' if self.html else '\n'+'-'*79+'\n').join(docs),
            'uid': self.uid
        })

    def _plain(sef, definition):
        """Generate a documentation string for use as plain text
        """

        return 'Docstring for {0}\n{1}\n{2}'.format(
            definition.full_name, '=' * 40, definition.doc
        )

    def _html(self, definition):
        """Generate documentation string in HTML format
        """

        if sys.version_info >= (3, 0):
            escaped_doc = html.escape(
                html.unescape(definition.doc), quote=False)
        else:
            escaped_doc = cgi.escape(
                HTMLParser.unescape.__func__(HTMLParser, definition.doc))

        escaped_doc = escaped_doc.replace('\n', '<br>')

        return '{0}\n{1}'.format(definition.full_name, escaped_doc)
