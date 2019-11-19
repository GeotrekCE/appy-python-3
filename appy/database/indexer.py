'''This file defines code for extracting, from field values, the text to be
   indexed.'''

# ------------------------------------------------------------------------------
from appy.xml import XmlParser
from appy.utils.string import normalizeText

# Default Appy indexes ---------------------------------------------------------
defaultIndexes = {
    'State': 'ListIndex', 'UID': 'FieldIndex', 'Title': 'TextIndex',
    'SortableTitle': 'FieldIndex', 'SearchableText': 'TextIndex',
    'Creator': 'FieldIndex', 'Created': 'DateIndex', 'Modified': 'DateIndex',
    'ClassName': 'FieldIndex', 'Allowed': 'KeywordIndex',
    'Container': 'FieldIndex'}

# Stuff for creating or updating the indexes -----------------------------------
class TextIndexInfo:
    '''Parameters for a text ZCTextIndex'''
    lexicon_id = "text_lexicon"
    index_type = 'Okapi BM25 Rank'

class XhtmlIndexInfo:
    '''Parameters for a html ZCTextIndex'''
    lexicon_id = "xhtml_lexicon"
    index_type = 'Okapi BM25 Rank'

class ListIndexInfo:
    '''Parameters for a list ZCTextIndex'''
    lexicon_id = "list_lexicon"
    index_type = 'Okapi BM25 Rank'

# ------------------------------------------------------------------------------
class XhtmlTextExtractor(XmlParser):
    '''Extracts text from XHTML'''
    def __init__(self, lower=True, dash=False, raiseOnError=False):
        XmlParser.__init__(self, raiseOnError=raiseOnError)
        # Must be lowerise text ?
        self.lower = lower
        # Must we keep dashes ?
        self.dash = dash

    def startDocument(self):
        XmlParser.startDocument(self)
        self.res = []

    def endDocument(self):
        self.res = ' '.join(self.res)
        return XmlParser.endDocument(self)

    # Disable the stack of currently parsed elements
    def startElement(self, elem, attrs): pass
    def endElement(self, elem): pass

    def characters(self, content):
        c = normalizeText(content, lower=self.lower, dash=self.dash)
        if len(c) > 1: self.res.append(c)

# ------------------------------------------------------------------------------
class XhtmlIndexer:
    '''Extracts, from XHTML field values, the text to index'''
    def process(self, texts):
        res = set()
        for text in texts:
            extractor = XhtmlTextExtractor(raiseOnError=False)
            cleanText = extractor.parse('<p>%s</p>' % text)
            res = res.union(splitIntoWords(cleanText))
        return list(res)

# ------------------------------------------------------------------------------
class TextIndexer:
    '''Extracts, from text field values, a normalized value to index'''
    def process(self, texts):
        res = set()
        for text in texts:
            cleanText = normalizeText(text)
            res = res.union(splitIntoWords(cleanText))
        return list(res)

class ListIndexer:
    '''This lexicon does nothing: list of values must be indexed as is'''
    def process(self, texts): return texts

# ------------------------------------------------------------------------------
def splitIntoWords(text, ignore=2, ignoreNumbers=False, words=None):
    '''Splits p_text into words. If p_words is None, it returns the set of
       words (no duplicates). Else, it adds one entry in the p_words dict for
       every encountered word.

       Words whose length is <= p_ignore are ignored, excepted, if
       p_ignoreNumbers is False, words being numbers.'''
    # Split p_text into words
    r = text.split()
    # Browse words in reverse order and remove shorter ones
    i = len(r) - 1
    keepIt = None
    while i > -1:
        word = r[i]
        # Keep this word or not ?
        if len(word) <= ignore:
            keepIt = not ignoreNumbers and word.isdigit()
        else:
            keepIt = True
        # Update "r" or "words" accordingly
        if words != None:
            # Add the word to "words" when we must keep it
            if keepIt:
                words[word] = None
        else:
            # Remove the word from "r" if we must not keep it
            if not keepIt:
                del r[i]
        i -= 1
    # Return the result as a set when relevant
    if words == None:
        return set(r)

# ------------------------------------------------------------------------------
class Keywords:
    '''This class allows to handle keywords that a user enters and that will be
       used as basis for performing requests in a TextIndex/XhtmlIndex.'''
    toRemove = '?-+*()'
    def __init__(self, keywords, operator='AND', ignore=2):
        # Clean the p_keywords that the user has entered
        words = sutils.normalizeText(keywords)
        if words == '*': words = ''
        for c in self.toRemove: words = words.replace(c, ' ')
        self.keywords = splitIntoWords(words, ignore=ignore)
        # Store the operator to apply to the keywords (AND or OR)
        self.operator = operator

    def merge(self, other, append=False):
        '''Merges our keywords with those from p_other. If p_append is True,
           p_other keywords are appended at the end; else, keywords are appended
           at the begin.'''
        for word in other.keywords:
            if word not in self.keywords:
                if append:
                    self.keywords.append(word)
                else:
                    self.keywords.insert(0, word)

    def get(self):
        '''Returns the keywords as needed by the TextIndex.'''
        if self.keywords:
            op = ' %s ' % self.operator
            return op.join(self.keywords)+'*'
        return ''
# ------------------------------------------------------------------------------
