'''Searches represent predefined sets of critera allowing to perform database
   searches. A searched is always attached to a given class from the model.'''

# ~license~

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from DateTime import DateTime

from appy.px import Px
from appy.model.batch import Batch
from appy.ui.criteria import Criteria
from appy.ui.template import Template
from appy.utils import string as sutils
from appy.model.fields.group import Group
from appy.model.searches.modes import Mode
from appy.database.indexer import Keywords, defaultIndexes
from appy.model.searches.initiators import RefInitiator, TemplateInitiator

# Error messages - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
WRONG_FIELD = 'Field "%s" does not exist on %s.'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Search:
    '''Used for specifying a search for a given class'''
    initiator = None # Is it not possible to create an object from a search

    def __init__(self, name=None, group=None, sortBy='', sortOrder='asc',
                 maxPerPage=30, default=False, colspan=1, translated=None,
                 show=True, showActions='all', actionsDisplay='block',
                 translatedDescr=None, checkboxes=False, checkboxesDefault=True,
                 container=None, resultModes=None, shownInfo=None, actions=None,
                 **fields):
        # "name" is mandatory, excepted in some special cases (ie, when used as
        # "select" param for a Ref field).
        self.name = name
        # Searches may be visually grouped in the portlet
        self.group = Group.get(group)
        self.sortBy = sortBy
        self.sortOrder = sortOrder
        self.maxPerPage = maxPerPage
        # If this search is the default one, it will be triggered by clicking
        # on main link.
        self.default = default
        self.colspan = colspan
        # If a translated name or description is already given here, we will
        # use it instead of trying to translate from labels.
        self.translated = translated
        self.translatedDescr = translatedDescr
        # Condition for showing or not this search
        self.show = show
        # Attributes "showActions" and "actionsDisplay" are similar to their
        # homonyms on the Ref class.
        self.showActions = showActions
        self.actionsDisplay = actionsDisplay
        # In the dict below, keys are indexed field names or names of standard
        # indexes, and values are search values.
        self.fields = fields
        # Do we need to display checkboxes for every object of the query result?
        self.checkboxes = checkboxes
        # Default value for checkboxes
        self.checkboxesDefault = checkboxesDefault
        # Most of the time, we know what is the class whose instances must be
        # searched. When it is not the case, the p_container can be explicitly
        # specified.
        self.container = container
        # There can be various ways to display query results
        self.resultModes = resultModes
        # Similar to the homonym Ref attribute, "shownInfo" defines the columns
        # that must be shown on lists of result objects (mode "List" only). If
        # not specified, class's "listColumns" attributes is used.
        self.shownInfo = shownInfo
        # Specify here Action fields that must be shown as custom actions that
        # will be triggered on search results.
        self.actions = actions

    def init(self, class_):
        '''Lazy search initialisation'''
        self.container = class_

    def ui(self, o, ctx):
        '''Gets a UiSearch instance corresponding to this search'''
        return UiSearch(self, o, ctx)

    @staticmethod
    def getIndexName(name, class_, usage='search'):
        '''Gets the name of the Zope index that corresponds to p_name. Indexes
           can be used for searching (p_usage="search"), for filtering
           ("filter") or for sorting ("sort"). The method returns None if the
           field named p_name can't be used for p_usage.'''
        # Manage indexes that do not have a corresponding field
        if name == 'created': return 'Created'
        elif name == 'modified': return 'Modified'
        elif name in defaultIndexes: return name
        else:
            # Manage indexes corresponding to fields
            field = getattr(class_, name, None) 
            if field: return field.getIndexName(usage)
            raise Exception(WRONG_FIELD % (name, class_.__bases__[-1].__name__))

    @staticmethod
    def getSearchValue(fieldName, fieldValue, class_):
        '''Returns a transformed p_fieldValue for producing a valid search
           value as required for searching in the index corresponding to
           p_fieldName.'''
        # Get the field corresponding to p_fieldName
        field = getattr(class_, fieldName, None)
        if field and callable(field): field = None
        if (field and (field.getIndexType() == 'TextIndex')) or \
           (fieldName == 'SearchableText'):
            # For TextIndex indexes. We must split p_fieldValue into keywords.
            res = Keywords(fieldValue).get()
        elif isinstance(fieldValue, str) and fieldValue.endswith('*'):
            v = fieldValue[:-1]
            # Warning: 'z' is higher than 'Z'!
            res = {'query':(v,v+'z'), 'range':'min:max'}
        elif type(fieldValue) in sutils.sequenceTypes:
            if fieldValue and isinstance(fieldValue[0], str):
                # We have a list of string values (ie: we need to
                # search v1 or v2 or...)
                res = fieldValue
            else:
                # We have a range of (int, float, DateTime...) values
                minv, maxv = fieldValue
                rangev = 'minmax'
                queryv = fieldValue
                if minv == None:
                    rangev = 'max'
                    queryv = maxv
                elif maxv == None:
                    rangev = 'min'
                    queryv = minv
                res = {'query':queryv, 'range':rangev}
        else:
            res = fieldValue
        return res

    def updateSearchCriteria(self, criteria, class_, advanced=False):
        '''This method updates dict p_criteria with all the search criteria
           corresponding to this Search instance. If p_advanced is True,
           p_criteria correspond to an advanced search, to be stored in the
           session: in this case we need to keep the Appy names for parameters
           sortBy and sortOrder (and not "resolve" them to Zope's sort_on and
           sort_order).'''
        # Beyond parameters required for performing a search, also store, in
        # p_criteria, other Search parameters if we need to reify a Search
        # instance for performing an advanced search.
        if advanced:
            criteria['showActions'] = self.showActions
            criteria['actionsDisplay'] = self.actionsDisplay
            criteria['resultModes'] = self.resultModes
            criteria['shownInfo'] = self.shownInfo
            criteria['checkboxes'] = self.checkboxes
        # Put search criteria in p_criteria
        for name, value in self.fields.items():
            # Management of searches restricted to objects linked through a
            # Ref field: not implemented yet.
            if name == '_ref': continue
            # Make the correspondence between the name of the field and the
            # name of the corresponding index, excepted if p_advanced is True:
            # in that case, the correspondence will be done later.
            if not advanced:
                indexName = Search.getIndexName(name, class_)
                # Express the field value in the way needed by the index
                criteria[indexName] = Search.getSearchValue(name, value, class_)
            else:
                criteria[name] = value
        # Add a sort order if specified
        if self.sortBy:
            c = criteria
            if not advanced:
                c['sort_on'] = Search.getIndexName(self.sortBy, class_,
                                                   usage='sort')
                c['sort_order']= (self.sortOrder=='desc') and 'reverse' or None
            else:
                c['sortBy'] = self.sortBy
                c['sortOrder'] = self.sortOrder

    def isShowable(self, tool):
        '''Is this Search instance showable ?'''
        class_ = self.container
        r = self.show
        return r if not callable(r) else \
               tool.H().methods.call(tool, self.show, class_=class_)

    def getSessionKey(self, className, full=True):
        '''Returns the name of the key, in the session, where results for this
           search are stored when relevant. If p_full is False, only the suffix
           of the session key is returned (ie, without the leading
           "search_").'''
        res = (self.name == 'allSearch') and className or self.name
        if not full: return res
        return 'search_%s' % res

    mergeFields = ('sortBy', 'sortOrder', 'showActions',
                   'actionsDisplay', 'actions')

    def merge(self, other):
        '''Merge parameters from another search in p_other'''
        self.fields.update(other.fields)
        for name in self.mergeFields: setattr(self, name, getattr(other, name))

    def getActions(self, tool):
        '''Get the actions triggerable on p_self's results'''
        actions = self.actions
        if not actions: return
        r = []
        for action in actions:
            show = action.show
            show = show(tool) if callable(show) else show
            if show:
                r.append(action)
        return r

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
    #  The "run" method
    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    def run(self, handler, batch=True, start=0, ids=False, secure=True,
            sortBy=None, sortOrder='asc', filters=None, refObject=None,
            refField=None, other=None):
        '''Based on p_self's parameters, and this method's attributes, perform a
           search in the corresponding catalog ans return the results.'''
        # If p_batch is True, the result is a appy.model.batch.Batch instance
        # returning only a subset of the results starting at p_start and
        # containing at most p_self.maxPerPage results. Else, it is a list of
        # objects (or object ids if p_ids is True) representing the complete
        # result set. If p_ids is True, p_batch is ignored and implicitly
        # considered being False.
        # ~~~
        # p_secure is transmitted and documented in called method
        # appy.database.catalog.Catalog.search (called via method
        # appy.database.Database.search).
        # ~~~
        # The result is sorted according to the potential sort key and order
        # ('asc'ending or 'desc'ending) as defined in p_self.sortBy and
        # p_self.sortOrder. If p_sortBy is not None, p_sortBy and p_sortOrder
        # override p_self's homonym attributes.
        # ~~~
        # p_filters alter search parameters according to selected filters in the
        # ui.
        # ~~~
        # If p_refObject and p_refField are given, the search is limited to the
        # objects being referenced from p_refObject through p_refField.
        # ~~~
        # If p_other is not None, it is another Search instance whose parameters
        # will be merged with p_self's parameters.
        r = handler.server.database.search(handler, self.container.name,
              ids=ids, secure=secure, sortBy=sortBy, sortOrder=sortOrder)
        if batch:
            r = Batch(r, total=len(r))
        return r

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
    #  Class methods
    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    @classmethod
    def get(class_, name, tool, modelClass, ctx, ui=False):
        '''Gets the Search instance (or a UiSearch instance if p_ui is True)
           corresponding to the search named p_name, on class p_modelClass.'''
        initiator = None
        req = tool.req
        if name == 'customSearch':
            # It is a custom search whose parameters are marshalled in key
            # "criteria". Unmarshal them.
            criteria = Criteria.readFromRequest(tool.H()) or {}
            r = Search('customSearch', container=modelClass, **criteria)
            # Avoid name clash
            if 'group' in criteria: r.fields['group'] = criteria['group']
            # Take into account default params for the advanced search
            advanced = modelClass.getSearchAdvanced(tool)
            if advanced: r.merge(advanced)
        elif (name == 'allSearch') or not name:
            # It is the search for every instance of p_modelClass
            r = Search('allSearch', container=modelClass)
            name = r.name
            # Take into account default params for the advanced search
            advanced = modelClass.getSearchAdvanced(tool)
            if advanced: r.merge(advanced)
        elif name == 'fromSearch':
            # It is the search for selecting a template for creating an object
            fromClass = req.fromClass
            sourceField = req.sourceField
            if sourceField:
                # We are creating an object from a Ref field
                id, fieldName = sourceField.split(':')
                o = tool.getObject(id)
                r = o.getField(fieldName).getAttribute(o, 'createVia')
            else:
                # We are creating a root object
                tool.model.classes.get(fromClass).getCreateVia(tool)
            initiator = TemplateInitiator(fromClass, req.formName, req.insert,
                                          sourceField)
        elif ',' in name:
            # The search is defined in a field
            id, fieldName, mode = name.split(',')
            # Get the object with this "id". In the case of a Ref field with
            # link=popup, the initiator object can be a temp object.
            o = tool.getObject(id)
            field = obj.getField(fieldName)
            if field.type == 'Ref':
                initiator = RefInitiator(o, field, fieldName, mode)
                r = field.getSelect(o)
            elif field.type == 'Computed':
                r = field.getSearch(o)
        else:
            # Search among static searches
            r = modelClass.searches.get(name)
            if not r:
                # Search among dynamic searches
                dyn = modelClass.getDynamicSearches(tool)
                if dyn:
                    for search in dyn:
                        if search.name == name:
                            r = search
                            break
        # The search may not exist
        if not r: tool.raiseUnauthorized(tool.translate('search_broken'))
        # Return a UiSearch if required
        return r if not ui else UiSearch(r, tool, ctx, initiator, name)

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
    #  PXs
    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    # Display results of a search whose name is in the request
    results = Px('''
     <div var="class_=tool.model.classes.get(req.className);
               uiSearch=tool.Search.get(req.search,tool,class_,_ctx_,ui=True);
               resultModes=uiSearch.getModes();
               hook=uiSearch.getRootHook()"
          id=":hook">
      <script>:uiSearch.getCbJsInit(hook)</script>
      <x>::ui.Globals.getForms(tool)</x>
      <div align=":dright" if="len(resultModes) &gt; 1">
       <select name="px"
               onchange=":'switchResultMode(this, %s)' % q('queryResult')">
        <option for="mode in resultModes"
                value=":mode">:uiSearch.Mode.getText(mode, _)</option>
       </select>
      </div>
      <x>:uiSearch.pxResult</x>
     </div>''',

     js='''
       function switchResultMode(select, hook) {
         var mode = select.options[select.selectedIndex].value;
         askAjax(hook, null, {'resultMode': mode});
       }''',

     template=Template.px, hook='content')

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class UiSearch:
    '''Instances of this class are generated on-the-fly for manipulating a
       Search instance from the User Interface.'''
    Mode = Mode

    # Rendering a search
    view = Px('''
     <div class="portletSearch">
      <a href=":'%s?className=%s&amp;search=%s' % \
                 (queryUrl, className, search.name)"
         class=":(search.name == currentSearch) and 'current' or ''"
         onclick="clickOn(this)"
         title=":search.translatedDescr">:search.translated</a>
     </div>''')

    # Render search results
    pxResult = Px('''
     <x var="layout='view';
             class_=class_|tool.model.classes.get(req.className);
             uiSearch=uiSearch|tool.Search.get(req.search, tool, class_,\
                                               _ctx_, ui=True);
             mode=uiSearch.getMode();
             batch=mode.batch;
             showNewSearch=showNewSearch|True;
             showHeaders=showHeaders|True;
             specific=uiSearch.getResultsTop(mode, ajax)">

     <!-- Application, class-specific code before displaying results -->
     <x if="specific">::specific</x>

     <!-- Search results -->
     <div id=":mode.hook">
      <script>:mode.getAjaxData()</script>

      <x if="not mode.empty">
       <!-- Pod templates -->
       <table var="fields=class_.getListPods()"
              if="not popup and mode.objects and fields" align=":dright">
        <tr>
         <td var="o=mode.objects[0]"
             for="field in fields" var2="fieldName=field.name"
             class=":not loop.field.last and 'pod' or ''">:field.pxRender</td>
        </tr>
       </table>

       <!-- Title -->
       <p if="not popup"><x>::uiSearch.translated</x>
        <x if="mode.batch">(<span class="discreet">:mode.batch.total</span>)</x>
        <x if="showNewSearch and mode.newSearchUrl">&nbsp;&mdash;&nbsp;<i> 
         <a href=":mode.newSearchUrl">:_('search_new')</a></i></x>
       </p>
       <table width="100%">
        <tr valign="top">
         <!-- Search description -->
         <td if="uiSearch.translatedDescr">
          <span class="discreet">:uiSearch.translatedDescr</span><br/>
         </td>
         <!-- (Top) navigation -->
         <td if="mode.batch"
             align=":dright" width="200px">:mode.batch.pxNavigate</td>
        </tr>
       </table>

       <!-- Results -->
       <x var="currentNumber=0">:mode.px</x>

       <!-- (Bottom) navigation -->
       <x if="mode.batch">:mode.batch.pxNavigate</x>
      </x>

      <!-- No result -->
      <x if="mode.empty">
       <x>::_('query_no_result')</x>
       <x if="showNewSearch and mode.newSearchUrl"><br/><i class="discreet">
         <a href=":mode.newSearchUrl">:_('search_new')</a></i></x>
      </x>
    </div></x>''')

    def __init__(self, search, tool, ctx, initiator=None, name=None):
        self.search = search
        self.container = search.container
        self.tool = tool
        self.req = tool.req
        self.dir = ctx.dir
        self.popup = ctx.popup
        # "name" can be more than the p_search name, ie, if the search is
        # defined in a field.
        self.name = name or search.name
        self.type = 'search'
        self.colspan = search.colspan
        self.showActions = search.showActions
        self.actionsDisplay = search.actionsDisplay
        className = self.container.name
        if search.translated:
            self.translated = search.translated
            self.translatedDescr = search.translatedDescr or ''
        else:
            # The label may be specific in some special cases
            labelDescr = ''
            if search.name == 'allSearch': label = '%s_plural' % className
            elif search.name == 'customSearch': label = 'search_results'
            elif not search.name: label = None
            else:
                label = '%s_search_%s' % (className, search.name)
                labelDescr = label + '_descr'
            _ = tool.translate
            self.translated = label and _(label) or ''
            self.translatedDescr = labelDescr and _(labelDescr) or ''
        # Strip the description (a single space may be present)
        self.translatedDescr = self.translatedDescr.strip()
        # An initiator instance if the search is in a popup
        self.initiator = initiator
        # When search results are shown in a popup, checkboxes must be present
        # even when not shown. Indeed, we want them in the DOM because object
        # ids are stored on it.
        if initiator:
            self.checkboxes = True
            self.checkboxesDefault = False
        else:
            self.checkboxes = search.checkboxes
            self.checkboxesDefault = search.checkboxesDefault

    def getRootHook(self):
        '''If there is an initiator, return the hook as defined by it. Else,
           return the name of the search.'''
        init = self.initiator
        return init.popupHook if init else (self.search.name or 'search')

    def showCheckboxes(self):
        '''When must checkboxes be shown ?'''
        init = self.initiator
        return init.showCheckboxes() if init else self.checkboxes

    def getCbJsInit(self, hook):
        '''Returns the code that creates JS data structures for storing the
           status of checkboxes for every result of this search.'''
        default = self.checkboxesDefault and 'unchecked' or 'checked'
        return '''var node=findNode(this, '%s');
                  node['_appy_objs_cbs'] = {};
                  node['_appy_objs_sem'] = '%s';''' % (hook, default)

    def getModes(self):
        '''Gets all the modes applicable when displaying search results (being
           instances of p_class_) via this search (p_self). r_ is a list of
           names and not a list of Mode instances.'''
        r = self.search.resultModes or self.container.getResultModes() or \
            Mode.default
        return r if not callable(r) else r(self.tool)

    def getMode(self):
        '''Gets the current mode'''
        return Mode.get(self)

    def getTitleMode(self, popup):
        '''How titles to search results, being instances of p_class_, must be
           rendered ? r_ is:
           * "link" : as links allowing to go to instances' view pages;
           * "select": as objects that can be selected from a popup;
           * "text": as simple, unclickable text.
        '''
        if popup: return 'select'
        # Check if the title mode is specified on the container class
        mode = self.container.getTitleMode()
        if not mode: return 'link'
        return mode if not callable(mode) else mode(self.tool)

    def getResultsTop(self, mode, ajax):
        '''If p_class_ defines something to display on the results page just
           before displaying search results, returns it.'''
        # Get this only on the main page, not when ajax-refreshing search
        # results.
        if ajax: return
        return self.container.getResultsTop(self.tool, self.search, mode)

    def getRefInfo(self, info=None):
        '''When a search is restricted to objects referenced through a Ref
           field, this method returns information about this reference: the
           source class and the Ref field. If p_info is not given, we search
           it among search criteria.'''
        tool = self.tool
        req = tool.req
        if not info and (req.search == 'customSearch'):
            criteria = Criteria.readFromRequest(tool.H())
            if criteria and ('_ref' in criteria): info = criteria['_ref']
        if not info: return None, None
        id, name = info.split(':')
        o = tool.getObject(id)
        return o, name

    def highlight(self, text):
        '''Highlight search results within p_text'''
        return Critera.highlight(self.tool.H(), text)
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
