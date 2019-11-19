'''Navigation management'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.px import Px
from appy.model.batch import Batch

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Sibling:
    '''Represents a sibling element, accessible via navigation from
       another one.'''
    # Existing types of siblings
    types = ('previous', 'next', 'first', 'last')
    # Names of icons corresponding to sibling types
    icons = {'previous': 'arrowLeft',  'next': 'arrowRight',
             'first':    'arrowsLeft', 'last': 'arrowsRight'}

    def __init__(self, o, type, nav, page, popup=False):
        # The sibling object
        self.o = o
        # The type of sibling
        self.type = type
        # The "nav" key
        self.nav = nav
        # The page that must be shown on the object
        self.page = page
        # Are we in a popup or not ?
        self.popup = popup

    def get(self, ctx):
        '''Get the HTML chunk allowing to navigate to this sibling'''
        js = "gotoSibling('%s/view','%s','%s','%s')" % \
             (self.o.url, self.nav, self.page, self.popup)
        return '<img src="%s" title="%s" class="clickable" onclick="%s"/>' % \
               (ctx.url(Sibling.icons[self.type]),
                ctx._('goto_%s' % self.type), js)

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Siblings:
    '''Abstract class containing information for navigating from one object to
       its siblings.'''

    pxGotoNumber = Batch.pxGotoNumber
    # Attributes storing the siblings for going "backwards" (True) or "forwards"
    # (False)
    byType = {True: ('firstSibling', 'previousSibling'),
              False: ('nextSibling',  'lastSibling')}

    # Icons for going to the current object's siblings    
    pxNavigate = Px('''
      <!-- Go to the source URL (search or referred object) -->
      <x if="not popup">::self.getGotoSource(url, _)</x>

      <!-- Form used to navigate to any sibling -->
      <form name=":self.siblingsFormName" method="post" action=""
            style="display: inline">
       <input type="hidden" name="nav" value=""/>
       <input type="hidden" name="page" value=""/>
       <input type="hidden" name="popup" value=""/>
       <input type="hidden" name="criteria" value=""/>
      </form>

      <!-- Go to the first and/or previous page -->
      <x>::self.getIcons(_ctx_, previous=True)</x>

      <!-- Explain which element is currently shown -->
      <span class="discreet"> 
       <x>:self.number</x> <b>//</b> <x>:self.total</x> </span>

      <!-- Go to the next and/or last page -->
      <x>::self.getIcons(_ctx_, previous=False)</x>

      <!-- Go to the element number... -->
      <x if="self.showGotoNumber()"
         var2="field=self.field; sourceUrl=self.sourceObject.url;
               total=self.total"><br/><x>:self.pxGotoNumber</x></x>''',
     js='''
       function gotoCustomSearch() {
         // Post a form allowing to re-trigger a custom search
         var f = document.forms['gotoSource'];
         // Add search criteria from the browser's session storage
         f.criteria.value = sessionStorage.getItem(f.className.value);
         f.submit();
       }
       function gotoSibling(url, nav, page, popup) {
         var formName = (popup == '1') ? 'siblingsPopup' : 'siblings',
             f = document.forms[formName];
         // Navigate to the sibling by posting a form
         f.action = url;
         f.nav.value = nav;
         f.page.value = page;
         f.popup.value = popup;
         if (nav) {
           // For a custom search, get criteria from the session storage
           var elems = nav.split('.');
           if ((elems[0] == 'search') && (elems[2] == 'customSearch')) {
             f.criteria.value = sessionStorage.getItem(elems[1]);
           }
         }
         f.submit();
        }''')

    @staticmethod
    def get(nav, tool, popup):
        '''Analyse the navigation info p_nav and returns the corresponding
          concrete Siblings instance.'''
        elems = nav.split('.')
        Siblings = (elems[0] == 'ref') and RefSiblings or SearchSiblings
        return Siblings(tool, popup, *elems[1:])

    def computeStartNumber(self):
        '''Returns the start number of the batch where the current element
           lies.'''
        # First index starts at O, so we calibrate self.number
        number = self.number - 1
        batchSize = self.getBatchSize()
        res = 0
        while (res < self.total):
            if (number < res + batchSize): return res
            res += batchSize
        return res

    def __init__(self, tool, popup, number, total):
        self.tool = tool
        self.req = tool.req
        # Are we in a popup window or not ?
        self.popup = popup
        self.siblingsFormName = popup and 'siblingsPopup' or 'siblings'
        # The number of the current element
        self.number = int(number)
        # The total number of siblings
        self.total = int(total)
        # Do I need to navigate to first, previous, next and/or last sibling ?
        self.previousNeeded = False # Previous ?
        self.previousIndex = self.number - 2
        if (self.previousIndex > -1) and (self.total > self.previousIndex):
            self.previousNeeded = True
        self.nextNeeded = False     # Next ?
        self.nextIndex = self.number
        if self.nextIndex < self.total: self.nextNeeded = True
        self.firstNeeded = False    # First ?
        self.firstIndex = 0
        if self.previousIndex > 0: self.firstNeeded = True
        self.lastNeeded = False     # Last ?
        self.lastIndex = self.total - 1
        if (self.nextIndex < self.lastIndex): self.lastNeeded = True
        # Compute the IDs of the siblings of the current object
        self.siblings = self.getSiblings()
        # Compute the URL allowing to go back to the "source" = a given page of
        # query results or referred objects.
        self.sourceUrl = self.getSourceUrl()
        # Compute Sibling objects and store them in attributes named
        # "<siblingType>Sibling".
        nav = self.getNavKey()
        page = self.req.page or 'main'
        for siblingType in Sibling.types:
            needIt = eval('self.%sNeeded' % siblingType)
            name = '%sSibling' % siblingType
            setattr(self, name, None)
            if not needIt: continue
            index = eval('self.%sIndex' % siblingType)
            o = None
            try:
                # self.siblings can be a list (ref) or a dict (search) and can
                # contain true objects or IDs.
                o = self.siblings[index]
                o = self.tool.getObject(o) if isinstance(o, str) else o
                if o is None: continue
            except (KeyError, IndexError):
                continue
            # Create the Sibling instance
            sibling = Sibling(o, siblingType, nav % (index+1), page, popup)
            setattr(self, name, sibling)

    def getSuffixedBackText(self, _):
        '''Gets the p_backText, produced by m_getBackText (see sub-classes),
           suffixed with a standard text.'''
        return '%s - %s' % (self.getBackText(), _('goto_source'))

    def getIcons(self, ctx, previous=True):
        '''Produce icons for going to
           - the first or the previous page if p_previous is True;
           - the next or last page else.
        '''
        r = ''
        for name in Siblings.byType[previous]:
            sibling = getattr(self, name)
            if sibling: r += sibling.get(ctx)
        return r

    def getGotoSource(self, url, _):
        '''Get the link allowing to return to the source URL'''
        return '<a href="%s"><img src="%s" title="%s"/></a>' % \
               (self.sourceUrl, url('gotoSource'), self.getSuffixedBackText(_))

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class RefSiblings(Siblings):
    '''Class containing information for navigating from one object to another
       within tied objects from a Ref field.'''
    prefix = 'ref'

    def __init__(self, tool, popup, sourceId, fieldName, number, total):
        # The source object of the Ref field
        self.sourceObject = tool.getObject(sourceId)
        # The Ref field in itself
        self.field = self.sourceObject.getField(fieldName)
        # Call the base constructor
        Siblings.__init__(self, tool, popup, number, total)

    def getNavKey(self):
        '''Returns the general navigation key for navigating to another
           sibling.'''
        return self.field.getNavInfo(self.sourceObject, None, self.total)

    def getBackText(self):
        '''Computes the text to display when the user want to navigate back to
           the list of tied objects.'''
        _ = self.tool.translate
        return '%s - %s' % (self.sourceObject.title, _(self.field.labelId))

    def getBatchSize(self):
        '''Returns the maximum number of shown objects at a time for this
           ref.'''
        return self.field.maxPerPage

    def getSiblings(self):
        '''Returns the siblings of the current object'''
        return getattr(self.sourceObject, self.field.name, ())

    def getSourceUrl(self):
        '''Computes the URL allowing to go back to self.sourceObject's page
           where self.field lies and shows the list of tied objects, at the
           batch where the current object lies.'''
        # Allow to go back to the batch where the current object lies
        field = self.field
        startNumberKey = '%s_%s_objs_start' % \
                         (self.sourceObject.id, field.name)
        startNumber = str(self.computeStartNumber())
        return self.sourceObject.getUrl(sub='view', page=field.pageName,
                                       nav='no', **{startNumberKey:startNumber})

    def showGotoNumber(self):
        '''Show "goto number" if the Ref field is numbered'''
        return self.field.isNumbered(self.sourceObject)

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class SearchSiblings(Siblings):
    '''Class containing information for navigating from one object to another
       within results of a search.'''
    prefix = 'search'

    def __init__(self, tool, popup, className, searchName, number, total):
        # The class determining the type of searched objects
        self.className = className
        # Get the search object
        self.searchName = searchName
        self.uiSearch = tool.getSearch(className, searchName, ui=True)
        self.search = self.uiSearch.search
        Siblings.__init__(self, tool, popup, number, total)

    def getNavKey(self):
        '''Returns the general navigation key for navigating to another
           sibling.'''
        return 'search.%s.%s.%%d.%d' % (self.className, self.searchName,
                                        self.total)

    def getBackText(self):
        '''Computes the text to display when the user want to navigate back to
           the list of searched objects.'''
        return self.uiSearch.translated

    def getBatchSize(self):
        '''Returns the maximum number of shown objects at a time for this
           search.'''
        return self.search.maxPerPage

    def getSiblings(self):
        '''Returns the siblings of the current object. For performance reasons,
           only a part of it is stored, in the session object.'''
        session = self.session
        searchKey = self.search.getSessionKey(self.className)
        if session.has_key(searchKey): res = session[searchKey]
        else: res = {}
        if (self.previousNeeded and not res.has_key(self.previousIndex)) or \
           (self.nextNeeded and not res.has_key(self.nextIndex)):
            # The needed sibling UID is not in session. We will need to
            # retrigger the query by querying all objects surrounding this one.
            newStartNumber = (self.number-1) - (self.search.maxPerPage / 2)
            if newStartNumber < 0: newStartNumber = 0
            self.tool.executeQuery(self.className, search=self.search,
                                   startNumber=newStartNumber, remember=True)
            res = session[searchKey]
        # For the moment, for first and last, we get them only if we have them
        # in session.
        if not res.has_key(0): self.firstNeeded = False
        if not res.has_key(self.lastIndex): self.lastNeeded = False
        return res

    def getSourceUrl(self):
        '''Computes the (non-Ajax) URL allowing to go back to the search
           results, at the batch where the current object lies, or to the
           originating field if the search was triggered from a field.'''
        if ',' in self.searchName:
            # Go back to the originating field
            id, name, mode = self.searchName.split(',')
            o = self.tool.getObject(id, appy=True)
            field = obj.getField(name)
            return '%s/view?page=%s' % (o.url, field.page.name)
        else:
            url = '%s/query' % self.tool.url
            # For a custom search, do not add URL params: we will build a form
            # and perform a POST request with search criteria.
            if self.searchName == 'customSearch': return url
            params = 'className=%s&search=%s&start=%d' % \
                    (self.className, self.searchName, self.computeStartNumber())
            ref = self.req.ref
            if ref: params += '&ref=%s' % ref
            return '%s?%s' % (url, params)

    def getGotoSource(self, url, _):
        '''Get the link or form allowing to return to the source URL'''
        if self.searchName != 'customSearch':
            return Siblings.getGotoSource(self, url, _)
        # For a custom search, post a form with the search criteria retrieved
        # from the browser's session.
        return '<form method="post" action="%s" name="gotoSource">' \
          '<input type="hidden" name="className" value="%s"/>' \
          '<input type="hidden" name="search" value="customSearch"/>' \
          '<input type="hidden" name="start" value="%d"/>' \
          '<input type="hidden" name="ref" value="%s"/>' \
          '<input type="hidden" name="criteria" value=""/></form>' \
          '<img class="clickable" src="%s" title="%s" ' \
          'onclick="gotoCustomSearch()"/>' % \
          (self.sourceUrl, self.className, self.computeStartNumber(),
           self.req.ref or '', url('gotoSource'), self.getSuffixedBackText(_))

    def showGotoNumber(self): return
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
