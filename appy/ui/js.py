'''Module implementing Javascript-related functionality'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import re

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Quote:
    '''This class escapes strings to be integrated as Javascript string literals
       in Javascript code, and, once escaped, quotes them.'''
    # The "escaping" part of this class is inspired by class appy/xml/Escape
    rex = re.compile("[\n\t\r']")
    blanks = {'\n': '', '\t':'', '\r':''}
    # There are 2 ways to escape a single quote
    values = {True: {"'": '&apos;'}, False: {"'": "\\'"}}
    for d in values.values(): d.update(blanks)

    @staticmethod
    def js(s, withEntity=True):
        '''Escapes blanks and single quotes in string p_s. Single quotes are
           escaped with a HTML entity if p_withEntity is True or with a quote
           prefixed with a "backslash" char else. Returns p_s, escaped and
           quoted.'''
        s = s if isinstance(s, str) else str(s)
        fun = lambda match: Quote.values[withEntity][match.group(0)]
        return "'%s'" % Quote.rex.sub(fun, s)
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
