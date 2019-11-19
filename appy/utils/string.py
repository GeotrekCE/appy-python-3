'''Utility module related to string manipulation'''

# ------------------------------------------------------------------------------
import re, cgi, unicodedata

# ------------------------------------------------------------------------------
charsIgnore = '.,:;*+=~?%^\'’"<>{}[]|\t\\°-'
fileNameIgnore = charsIgnore + ' $£€/\r\n'
extractIgnore = charsIgnore + '/()'
extractIgnoreNoDash = extractIgnore.replace('-', '')
alphaRex = re.compile(b'[a-zA-Z]')
alphanumRex = re.compile(b'[a-zA-Z0-9]')
alphanum_Rex = re.compile(b'[a-zA-Z0-9_]')

def normalizeString(s, usage='fileName'):
    '''Returns a version of string p_s whose special chars (like accents) have
       been replaced with normal chars. Moreover, if p_usage is:
       * fileName: it removes any char that can't be part of a file name;
       * alphanum: it removes any non-alphanumeric char;
       * alpha: it removes any non-letter char.
    '''
    if not s: return s
    # For extracted text, replace any unwanted char with a blank
    if usage.startswith('extract'):
        ignore = usage.endswith('-') and extractIgnoreNoDash or extractIgnore
        res = ''
        for char in s:
            if char not in ignore: res += char
            else: res += ' '
        s = res
    # Standardize special chars like accents
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore')
    # Remove any other char, depending on p_usage
    if usage == 'fileName':
        # Remove any char that can't be found within a file name under Windows
        # or that could lead to problems with LibreOffice.
        res = ''
        for char in s:
            if char not in fileNameIgnore: res += char
    elif usage.startswith('alpha'):
        exec('rex = %sRex' % usage)
        res = ''
        for char in s:
            if rex.match(char): res += char
    elif usage == 'noAccents':
        res = s
    else:
        res = s
    # Re-code the result as a str
    return res.decode()

def normalizeText(s, lower=True, dash=False, space=True):
    '''Remove from p_s special chars and lowerize it (if p_lower is True) for
       indexing or other purposes.'''
    usage = dash and 'extract-' or 'extract'
    r = normalizeString(s, usage=usage).strip()
    if lower: r = r.lower()
    if not space: r = r.replace(' ', '')
    return r

def formatText(text, format='html'):
    '''Produces a representation of p_text into the desired p_format, which
       is "html" by default.'''
    if 'html' in format:
        if format == 'html_from_text': text = cgi.escape(text)
        r = text.replace('\r\n', '<br/>').replace('\n', '<br/>')
    elif format == 'text':
        r = text.replace('<br/>', '\n')
    else:
        r = text
    return r

def keepDigits(s):
    '''Returns string p_s whose non-number chars have been removed'''
    if s is None: return s
    res = ''
    for c in s:
        if c.isdigit(): res += c
    return res

def keepAlphanum(s):
    '''Returns string p_s whose non-alphanum chars have been removed'''
    if s is None: return s
    res = ''
    for c in s:
        if c.isalnum(): res += c
    return res

def getStringFrom(o, stringify=True):
    '''Returns a string representation for p_o that can be transported over
       HTTP and manipulated in Javascript.

       If p_stringify is True, non-string literals (None, integers, floats...)
       are surrounded by quotes.
    '''
    if isinstance(o, dict):
        res = []
        for k, v in o.items():
            res.append("%s:%s" % (getStringFrom(k, stringify),
                                  getStringFrom(v, stringify)))
        return '{%s}' % ','.join(res)
    elif isinstance(o, list) or isinstance(o, tuple):
        return '[%s]' % ','.join([getStringFrom(v, stringify) for v in o])
    else:
        # Convert the value to a string
        isString = isinstance(o, str)
        isDate = not isString and (o.__class__.__name__ == 'DateTime')
        if not isString: o = str(o)
        # Manage the special case of dates
        if isDate and not stringify: o = "DateTime('%s')" % o
        # Surround the value by quotes when appropriate
        if isString or stringify:
            o = "'%s'" % (o.replace("'", "\\'"))
        return o

def getDictFrom(s):
    '''Returns a dict from string representation p_s of the form
       "key1:value1,key2:value2".'''
    res = {}
    if s:
        for part in s.split(','):
            key, value = part.split(':')
            res[key] = value
    return res

def sadd(s, sub, sep=' '):
    '''Adds sub-string p_sub into p_s, which is a list of sub-strings separated
       by p_sep, and returns the updated string.'''
    if not sub: return s
    if not s: return sub
    elems = set(s.split(sep)).union(set(sub.split(sep)))
    return sep.join(elems)

def sremove(s, sub, sep=' '):
    '''Removes sub-string p_sub from p_s, which is a list of sub-strings
       separated by p_sep, and returns the updated string.'''
    if not sub: return s
    if not s: return s
    elems = set(s.split(sep))
    for elem in sub.split(sep):
        if elem in elems:
            elems.remove(elem)
    return sep.join(elems)

def stringIsAmong(s, l):
    '''Is p_s among list of strings p_l ? p_s can be a string or a
       list/tuple of strings. In this latter case, r_ is True if at least
       one string among p_s is among p_l.'''
    # The simple case: p_s is a string
    if isinstance(s, str): return s in l
    # The complex case: p_s is a list or tuple
    for elem in s:
        if elem in l:
            return True

def stretchText(s, pattern, char=' '):
    '''Inserts occurrences of p_char within p_s according to p_pattern.
       Example: stretchText("475123456", (3,2,2,2)) returns "475 12 34 56".'''
    res = ''
    i = 0
    for nb in pattern:
        j = 0
        while j < nb:
            res += s[i+j]
            j += 1
        res += char
        i += nb
    return res

def grammarJoin(l, sep=', ', lastSep=' and '):
    '''Joins list p_l with p_sep, excepted the last 2 elements that are joined
       with p_lastSep. grammarJoin(["a", "b", "c"]) produces "a, b and c".'''
    r = ''
    i = 0
    last = len(l) - 1
    for elem in l:
        # Determine the correct separator to use here
        if i == last:
            curSep = ''
        elif i == last-1:
            curSep = lastSep
        else:
            curSep = sep
        # Add the current element, suffixed with the separator, to the result
        r += elem + curSep
        i += 1
    return r

upperLetter = re.compile('[A-Z]')
def produceNiceMessage(msg):
    '''Transforms p_msg into a nice msg'''
    r = ''
    if msg:
        r = msg[0].upper()
        for c in msg[1:]:
            if c == '_':
                r += ' '
            elif upperLetter.match(c):
                r += ' ' + c.lower()
            else:
                r += c
    return r

# ------------------------------------------------------------------------------
def lower(s):
    '''French-accents-aware variant of string.lower.'''
    isUnicode = isinstance(s, unicode)
    if not isUnicode: s = s.decode('utf-8')
    res = s.lower()
    if not isUnicode: res = res.encode('utf-8')
    return res

def upper(s):
    '''French-accents-aware variant of string.upper.'''
    isUnicode = isinstance(s, unicode)
    if not isUnicode: s = s.decode('utf-8')
    res = s.upper()
    if not isUnicode: res = res.encode('utf-8')
    return res

# ------------------------------------------------------------------------------
class WhitespaceCruncher:
    '''Takes care of removing unnecessary whitespace in several contexts'''
    whitechars = u' \r\t\n' # Chars considered as whitespace
    allWhitechars = whitechars + u' ' # nbsp
    @staticmethod
    def crunch(s, previous=None):
        '''Return a version of p_s (expected to be a unicode string) where all
           "whitechars" are:
           * converted to real whitespace;
           * reduced in such a way that there cannot be 2 consecutive
             whitespace chars.
           If p_previous is given, those rules must also apply globally to
           previous+s.'''
        res = ''
        # Initialise the previous char
        if previous:
            previousChar = previous[-1]
        else:
            previousChar = u''
        for char in s:
            if char in WhitespaceCruncher.whitechars:
                # Include the current whitechar in the result if the previous
                # char is not a whitespace or nbsp.
                if not previousChar or \
                   (previousChar not in WhitespaceCruncher.allWhitechars):
                    res += u' '
            else: res += char
            previousChar = char
        # "res" can be a single whitespace. It is up to the caller method to
        # identify when this single whitespace must be kept or crunched.
        return res
# ------------------------------------------------------------------------------
