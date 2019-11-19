# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.utils import string as sutils

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Criteria:
    '''Represents a set of search criteria manipulated from the UI'''

    def __init__(self, tool):
        self.tool = tool
        # This attribute will store the dict of search criteria, ready to be
        # injected in a Search class for performing a search in the catalog.
        self.criteria = None

    @classmethod
    def readFromRequest(class_, handler):
        '''Unmarshalls, from request key "criteria", a dict that was marshalled
           from a dict similar to the one stored in attribute "criteria" in
           Criteria instances.'''
        # Get the cached criteria on the handler if found
        cached = handler.cache.criteria
        if cached: return cached
        # Criteria may be absent from the request
        criteria = handler.req.criteria
        if not criteria: return
        # Criteria are present but not cached. Get them from the request,
        # unmarshal and cache them.
        r = eval(criteria)
        handler.cache.criteria = r
        return r

    @classmethod
    def highlight(class_, handler, text):
        '''Highlights parts of p_text if we are in the context of a search whose
           keywords must be highlighted.'''
        # Must we highlight something ?
        criteria = class_.readFromRequest(handler)
        if not criteria or ('SearchableText' not in criteria): return text
        # Highlight every variant of every keyword
        for word in criteria['SearchableText'].strip().split():
            highlighted = '<span class="highlight">%s</span>' % word
            sWord = word.strip(' *').lower()
            for variant in (sWord, sWord.capitalize(), sWord.upper()):
                text = re.sub('(?<= |\(|\>)%s' % variant, highlighted, text)
        return text

    def getDefault(self, form):
        '''Get the default search criteria that may be defined on the
           corresponding Appy class, in field Class.searchAdvanced (field
           values, sort filters, etc), and return it if found.'''
        r = {}
        if 'className' not in form: return r
        # Get the Appy class for which a search is requested
        className = form['className']
        tool = self.tool
        class_ = tool.getAppyClass(className)
        # On this Appy class, retrieve the Search instance containing default
        # search criteria.
        search = tool.getSearchAdvanced(class_)
        if not search: return r
        wrapperClass = tool.getAppyClass(className, wrapper=True)
        search.updateSearchCriteria(r, wrapperClass, advanced=True)
        return r

    def getFromRequest(self):
        '''Retrieve search criteria from the request after the user has filled
           an advanced search form and perform some transforms on it to produce
           p_self.criteria.'''
        req = self.tool.REQUEST
        form = req.form
        # Start by collecting default search criteria
        r = self.getDefault(form)
        className = form['className']
        # Then, retrieve criteria from the request
        for name in form.keys():
            # On the Appy advanced search form, every search field is prefixed
            # with "w_".
            if not name.startswith('w_'): continue
            name = name[2:]
            # Get the field corresponding to request key "name"
            field = self.tool.getAppyType(name, className)
            # Ignore this value if it is empty or if the field is inappropriate
            # for a search.
            if not field or field.searchValueIsEmpty(form) or not field.indexed:
                continue
            # We have a(n interval of) value(s) that is not empty for a given
            # field. Get it.
            r[name] = field.getSearchValue(form)
        # Complete criteria with Ref info if the search is restricted to
        # referenced objects of a Ref field.
        refInfo = req.get('ref', None)
        if refInfo: r['_ref'] = refInfo
        self.criteria = r

    def asString(self):
        '''Returns p_self.criteria, marshalled in a string'''
        return sutils.getStringFrom(self.criteria, stringify=False)
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
