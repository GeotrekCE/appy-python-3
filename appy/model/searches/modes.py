'''Search results can be displayed in various "modes": as a list, grid,
   calendar, etc.'''

# ~license~

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.px import Px
from appy.model.batch import Batch
from appy.utils import string as sutils
from appy.model.utils import Object as O
from appy.ui import LinkTarget, Columns, Title

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Mode:
    '''Abstract base class for search modes. A concrete Mode instance is created
       every time search results must be computed.'''

    # The default mode(s) for displaying instances of any Appy class
    default = ('list',)

    # All available predefined concrete modes
    concrete = ('list', 'grid', 'calendar')

    # The list of custom actions that can be triggered on search results
    pxActions = Px('''
     <table>
      <tr><td for="action in actions"
            var2="field=action; fieldName=field.name;
                  multi=True">:action.pxRender</td></tr>
     </table>''')

    @classmethod
    def get(class_, uiSearch):
        '''Create and return the Mode instance corresponding to the current
           result mode to apply to a list of instances.'''
        name = uiSearch.req.resultMode or uiSearch.getModes()[0]
        # Determine the concrete mode class
        if name in Mode.concrete:
            custom = False
            concrete = eval(name.capitalize())
        else:
            custom = True
            concrete = Custom
        # Create the Mode instance
        r = concrete(uiSearch)
        if custom:
            # The custom PX is named "name" on the model class
            r.px = getattr(self.class_, name)
        r.init()
        return r

    @classmethod
    def getText(class_, name, _):
        '''Gets the i18n text corresponding to mode named p_name'''
        name = name.rsplit('_', 1)[0] if '_' in name else name
        return _('result_mode_%s' % name) if name in Mode.concrete \
                                          else _('custom_%s' % name)

    def __init__(self, uiSearch):
        # The tied UI search
        self.uiSearch = uiSearch
        # The class from which we will search instances
        self.class_ = uiSearch.container
        # Are we in a popup ?
        self.popup = uiSearch.popup
        # The tool
        self.tool = uiSearch.tool
        # The ID of the tag that will be ajax-filled with search results
        self.hook = 'queryResult'
        # Matched objects
        self.objects = None
        # A Batch instance, when only a sub-set of the result set is shown at
        # once.
        self.batch = None
        # Are we sure the result is empty ? (ie, objects could be empty but
        # matched objects could be absent due to filters).
        self.empty = True
        # URL for triggering a new search
        self.newSearchUrl = None
        # The target for "a" tags
        self.target = LinkTarget(self.class_)
        # How to render links to result objects ?
        self.titleMode = uiSearch.getTitleMode(self.popup)

    def init(self):
        '''Every concrete class may have a specific initialization part'''
        # Store criteria for custom searches
        self.criteria = self.tool.req.criteria

    def getAjaxData(self):
        '''Initializes an AjaxData object on the DOM node corresponding to the
           ajax hook for this search result.'''
        search = self.uiSearch
        name = search.name
        params = {'className': self.class_.name, 'search': name,
                  'popup': self.popup}
        # Add initiator-specific params
        if search.initiator:
            initatorParams = search.initiator.getAjaxParams()
            if initatorParams: params.update(initatorParams)
        # Add custom search criteria
        if self.criteria:
            params['criteria'] = self.criteria
        # Concrete classes may add more parameters
        self.updateAjaxParameters(params)
        # Convert params into a JS dict
        params = sutils.getStringFrom(params)
        return "new AjaxData('%s/Search/results', 'POST', %s, '%s')" % \
               (self.tool.url, params, self.hook)

    def updateAjaxParameters(self, params):
        '''To be overridden by subclasses for adding Ajax parameters
           (see m_getAjaxData above)'''

    def getAjaxDataRow(self, o, **params):
        '''Initializes an AjaxData object on the DOM node corresponding to the
           row displaying info about p_o within the results.'''
        return "new AjaxData('%s/pxResult', 'GET', %s, '%s', '%s')"% \
               (o.url, sutils.getStringFrom(params), o.id, self.hook)

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class List(Mode):
    '''Displays search results as a table containing one row per object'''

    px = Px('''
     <table class=":class_.getResultCss(layout)" width="100%">
      <!-- Headers, with filters and sort arrows -->
      <tr if="showHeaders">
       <th for="column in mode.columns"
           var2="field=column.field" width=":column.width" align=":column.align"
           class=":(field == '_checkboxes') and mode.cbClass or ''">
        <x if="column.header">
         <img if="field == '_checkboxes'" src=":url('checkall')"
              class="clickable" title=":_('check_uncheck')"
              onclick=":'toggleAllCbs(%s)' % q(mode.checkboxesId)"/>
         <x if="not column.special">
          <x>::Px.truncateText(_(field.labelId))</x>
          <!-- Sort icons -->
          <x var="sortable=field.isSortable(usage='search')"
             if="sortable and (mode.batch.total &gt; 1)">
           <img if="(mode.sortKey != field.name) or (mode.sortOrder == 'desc')"
                onclick=":'askBunchSorted(%s, %s, %s)' % \
                          (q(mode.hook), q(field.name), q('asc'))"
                src=":url('sortDown')" class="clickable"/>
           <img if="(mode.sortKey != field.name) or (mode.sortOrder == 'asc')"
                onclick=":'askBunchSorted(%s, %s, %s)' % \
                          (q(mode.hook), q(field.name), q('desc'))"
                src=":url('sortUp')" class="clickable"/>
          </x>
          <!-- Filter widget -->
          <x if="field.filterPx and ((mode.batch.total &gt; 1) or \
                 mode.filters)">:getattr(field, field.filterPx)</x>
          <x if="ui.Title.showSub(class_, field)">:ui.Title.pxSub</x>
         </x>
        </x>
       </th>
      </tr>
      <!-- Results -->
      <tr if="not mode.objects">
       <td colspan=":len(mode.columns)+1">::_('query_no_result')</td>
      </tr>
      <x for="o in mode.objects"
         var2="rowCss=loop.o.odd and 'even' or 'odd';
               @currentNumber=currentNumber + 1">:o.pxResult</x>
     </table>
     <!-- The button for selecting objects and closing the popup -->
     <div if="popup and mode.cbShown" align=":dleft">
      <input type="button"
             var="label=_('object_link_many'); css=ui.Button.getCss(label)"
             value=":label" class=":css" style=":url('linkMany', bg=True)"
             onclick=":uiSearch.initiator.jsSelectMany(\
                   q, mode.sortKey, mode.sortOrder, mode.getFiltersString())"/>
     </div>
     <!-- Custom actions -->
     <x var="actions=uiSearch.search.getActions(tool)"
        if="actions and not popup">:mode.pxActions</x>
     <!-- Init checkboxes if present -->
     <script if="mode.checkboxes">:'initCbs(%s)' % q(mode.checkboxesId)</script>
     <script>:'initFocus(%s)' % q(mode.hook)</script>''')

    def init(self):
        '''List-specific initialization'''
        Mode.init(self)
        search = self.uiSearch
        tool = self.tool
        # The search may be triggered via a Ref field
        self.refObject, self.refField = search.getRefInfo()
        # [Custom searches only] build the URL allowing to trigger a new search
        if search.name == 'customSearch':
            # Build the "Ref" part for this URL
            o = self.refObject
            part = '&ref=%s:%s' % (o.id, self.refField) if o else ''
            self.newSearchUrl = '%s/search?className=%s%s' % \
                                (tool.url, self.className, part)
        # Build search parameters (start number, sort and filter)
        req = tool.req
        start = int(req.startNumber or '0')
        self.sortKey = req.sortKey or ''
        self.sortOrder = req.sortOrder or 'asc'
        self.filters = sutils.getDictFrom(req.filters)
        # Run the search
        self.batch = search.search.run(tool.H(), start=start,
          sortBy=self.sortKey, sortOrder=self.sortOrder, filters=self.filters,
          refObject=self.refObject, refField=self.refField)
        self.batch.hook = self.hook
        self.objects = self.batch.objects
        # Show sub-titles ?
        self.showSubTitles = req.showSubTitles
        # Every matched object may be selected via a checkbox
        self.rootHook = search.getRootHook()
        self.checkboxes = search.checkboxes
        self.checkboxesId = self.rootHook + '_objs'
        self.cbShown = search.showCheckboxes()
        self.cbClass = '' if self.cbShown else 'hide'
        # Determine result emptiness
        self.empty = not self.objects and not self.filters
        # Compute info related to every column in the list
        self.columnLayouts = self.getColumnLayouts()
        self.columns = Columns.get(tool, self.class_, self.columnLayouts,
                                   search.dir, addCheckboxes=self.checkboxes)

    def updateAjaxParameters(self, params):
        '''List-specific ajax parameters'''
        params.update(
          {'startNumber': self.batch.start, 'filters': self.filters,
           'sortKey': self.sortKey, 'sortOrder': self.sortOrder,
           'checkboxes': self.checkboxes, 'checkboxesId': self.checkboxesId,
           'totalNumber': self.batch.total,
           'resultMode': self.__class__.__name__.lower()})

    def getColumnLayouts(self):
        '''Returns the column layouts'''
        r = None
        tool = self.tool
        name = self.uiSearch.name
        # Try first to retrieve this info from a potential source Ref field
        o = self.refObject
        if o:
            field = o.getField(self.refField)
            r = field.getAttribute(o, 'shownInfo')
        elif ',' in name:
            id, fieldName, x = name.split(',')
            o = tool.getObject(id)
            field = o.getField(fieldName)
            if field.type == 'Ref':
                r = field.getAttribute(o, 'shownInfo')
        if r: return r
        # Try to retrieve this info via search.shownInfo
        search = self.uiSearch.search
        r = search.shownInfo
        return r if r else self.class_.getListColumns(tool)

    def getFiltersString(self):
        '''Converts dict self.filters into its string representation'''
        filters = self.filters
        if not filters: return ''
        r = []
        for k, v in filters.items():
            r.append('%s:%s' % (k, v))
        return ','.join(r)

    def getNavInfo(self, number):
        '''Gets the navigation string corresponding to the element having this
           p_number within the list of results.'''
        return 'search.%s.%s.%d.%d' % (self.class_.name, self.uiSearch.name, \
                                    self.batch.start + number, self.batch.total)

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Grid(List):
    '''Displays search results as a table containing one cell per object'''

    px = Px('''
     <div style=":mode.gridder.getContainerStyle()">
      <div for="zobj in mode.objects" class="thumbnail"
           var2="obj=zobj.appy(); mayView=zobj.mayView()">
       <table class="thumbtable">
        <tr var="@currentNumber=currentNumber + 1" valign="top"
            for="column in mode.columns"
            var2="field=column.field; backHook='queryResult'">
         <td if="field.name=='title'" colspan="2">:field.pxRenderAsResult</td>
         <x if="field.name!='title'">
          <td><label lfor=":field.name">::_('label', field=field)</label></td>
          <td>:field.pxRenderAsResult</td>
         </x>
        </tr>
       </table>
       <p class="thumbmore"><img src=":url('more')" class="clickable"
          onclick="followTitleLink(this)"/></p>
      </div>
     </div>''',

     js='''
      followTitleLink = function(img) {
        var parent = img.parentNode.parentNode,
            atag = parent.querySelector("a[name=title]");
        atag.click();
      }
      ''')

    def __init__(self, *args):
        List.__init__(self, *args)
        # Extract the gridder defined on p_self.class_ or create a default one
        self.gridder = getattr(self.class_, 'gridder', None) or Gridder()

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Calendar(Mode):
    '''Displays search results in a monthly calendar view'''

    px = Px('''<x var="layoutType='view';
                       field=tool.getField('calendar')">:field.view</x>''')

    def __init__(self, *args):
        Mode.__init__(self, *args)
        # For this calendar view to work properly, objects to show inside it
        # must have the following attributes:
        # ----------------------------------------------------------------------
        # date    | an indexed and required Date field with format =
        #         | Date.WITH_HOUR storing the object's start date and hour;
        # ----------------------------------------------------------------------
        # endDate | a not necessarily required Date field with format =
        #         | Date.WITH_HOUR storing the object's end date and hour.
        # ----------------------------------------------------------------------
        # Optionally, if objects define the following attributes, special icons
        # indicating repeated events will be shown.
        # ----------------------------------------------------------------------
        # successor   | Ref field with multiplicity = (0,1), allowing to
        #             | navigate to the next object in the list (for a repeated
        #             | event);
        # ----------------------------------------------------------------------
        # predecessor | Ref field with multiplicity = (0,1), allowing to
        #             | navigate to the previous object in the list.
        #             | "predecessor" must be the back ref of field "successor"
        #             | hereabove.
        # ----------------------------------------------------------------------

    def init(self):
        '''Creates a stub calendar field'''
        Mode.init(self)
        # Always consider the result as not empty. This way, the calendar is
        # always shown, even if no object is visible.
        self.empty = False
        # The matched objects, keyed by day. For every day, a list of entries to
        # show. Every entry is a 2-tuple (s_entryType, Object) allowing to
        # display an object at this day. s_entryType can be:
        # ----------------------------------------------------------------------
        #  "start"  | the object starts and ends at this day: display its start
        #           | hour and title;
        # ----------------------------------------------------------------------
        #  "start+" | the object starts at this day but ends at another day:
        #           | display its start hour, title and some sign indicating
        #           | that it spans on another day;
        # ----------------------------------------------------------------------
        #  "end"    | the object started at a previous day and ends at this day.
        #           | Display its title and a sign indicating this fact;
        # ----------------------------------------------------------------------
        #  "pass"   | The object started at a previous day and ends at a future
        #           | day.
        # ----------------------------------------------------------------------
        self.objects = {} # ~{s_YYYYmmdd: [(s_entryType, Object)]}~
        # Formats for keys representing dates
        self.dayKey = '%Y%m%d'
        # Format for representing hours in the UI
        self.hourFormat = '%H:%M'
        # If filters are defined from a list mode, get it
        self.filters = sutils.getDictFrom(req.get('filters'))

    def updateAjaxParameters(self, params):
        '''Grid-specific ajax parameters'''
        # If filters are in use, carry them
        if self.filters:
            params['filters'] = self.filters

    # For every hereabove-defined entry type, this dict stores info about how
    # to render events having this type. For every type:
    # --------------------------------------------------------------------------
    # start      | bool | Must we show the event's start hour or not ?
    # end        | bool | Must we show the event's end hour or not ?
    # css        | str  | The CSS class to add the table event tag
    # past       | bool | True if the event spanned more days in the past
    # future     | bool | True if the event spans more days in the future
    # --------------------------------------------------------------------------
    entryTypes = {
     'start':  O(start=True,  end=True,  css=None,      past=None, future=None),
     'start+': O(start=True,  end=False, css='calMany', past=None, future=True),
     'end':    O(start=False, end=True,  css='calMany', past=True, future=None),
     'pass':   O(start=False, end=False, css='calMany', past=True, future=True),
    }

    def addEntry(self, dateKey, entry):
        '''Adds an p_entry as created by m_addEntries below into self.objects
           @key p_dateKey.'''
        r = self.objects
        if dateKey not in r:
            r[dateKey] = [entry]
        else:
            r[dateKey].append(entry)

    def addEntries(self, obj):
        '''Add, in self.objects, entries corresponding to p_obj. If p_obj spans
           a single day, a single entry of the form ("start", p_obj) is added at
           the key corresponding to this day. Else, a series of entries are
           added, each of the form (s_entryType, p_obj), with the same object,
           for every day in p_obj's timespan.

           For example, for an p_obj starting at "1975/12/11 12:00" and ending
           at "1975/12/13 14:00" will produce the following entries:
              key "19751211"  >  value ("start+", obj)
              key "19751212"  >  value ("pass", obj)
              key "19751213"  >  value ("end", obj)
        '''
        # Get p_obj's start and end dates
        start = obj.date
        startKey = start.strftime(self.dayKey)
        end = obj.endDate
        endKey = end and end.strftime(self.dayKey) or None
        # Shorthand for self.objects
        r = self.objects
        if not endKey or (endKey == startKey):
            # A single entry must be added for p_obj, at the start date
            self.addEntry(startKey, ("start", obj))
        else:
            # Add one entry at the start day
            self.addEntry(startKey, ("start+", obj))
            # Add "pass" entries for every day between the start and end days
            next = start + 1
            nextKey = next.strftime(self.dayKey)
            while nextKey != endKey:
                # Add a "pass" event
                self.addEntry(nextKey, ('pass', obj))
                # Go the the next day
                next += 1
                nextKey = next.strftime(self.dayKey)
            # Add an "end" entry at the end day
            self.addEntry(endKey, ('end', obj))

    def search(self, first, grid):
        '''Performs the query, limited to the date range defined by p_grid'''
        # Performs the query, restricted to the visible date range
        last = DateTime(grid[-1][-1].strftime('%Y/%m/%d 23:59:59'))
        dateSearch = Search(date=(first, last), sortBy='date', sortOrder='asc')
        res = self.tool.executeQuery(self.className,
          search=self.uiSearch.search, maxResults='NO_LIMIT',
          search2=dateSearch, filters=self.filters)
        # Produce, in self.objects, the dict of matched objects
        for zobj in res.objects:
            self.addEntries(zobj.appy())

    def dumpObjectsAt(self, date):
        '''Returns info about the object(s) that must be shown in the cell
           corresponding to p_date.'''
        # There may be no object dump at this date
        dateStr = date.strftime(self.dayKey)
        if dateStr not in self.objects: return
        # Objects exist
        r = []
        types = self.entryTypes
        url = self.tool.getIncludeUrl
        for entryType, obj in self.objects[dateStr]:
            # Dump the event hour and title. The back hook allows to refresh the
            # whole calendar view when coming back from the popup.
            eType = types[entryType]
            # What CSS class(es) to apply ?
            css = eType.css and ('calEvt %s' % eType.css) or 'calEvt'
            # Show start and/or end hour ?
            eHour = sHour = ''
            if eType.start:
                sHour = '<td width="2em">%s</td>' % \
                        obj.date.strftime(self.hourFormat)
            if eType.end:
                endDate = obj.endDate
                if endDate:
                    eHour = ' <abbr title="%s">¬</abbr>' % \
                            endDate.strftime(self.hourFormat)
            # Display indicators that the event spans more days
            past = eType.past and '⇠ ' or ''
            future = eType.future and ' ⇢' or ''
            # The event title
            title = Title.get(o, target=self.target, popup=True,
                              backHook='configcalendar', maxChars=24)
            # Display a "repetition" icon if the object is part of a series
            hasSuccessor = obj.ids('successor')
            hasPredecessor = obj.ids('predecessor')
            if hasSuccessor or hasPredecessor:
                # For the last event of a series, show a more stressful icon
                name = not hasSuccessor and 'repeated_last' or 'repeated'
                icon = '<img src="%s" class="help" title="%s"/>' % \
                       (url(name), obj.translate(name))
            else:
                icon = ''
            # Produce the complete entry
            r.append('<table class="%s"><tr valign="top">%s<td>%s%s%s%s%s</td>'\
                     '</tr></table>' % (css,sHour,past,title,future,eHour,icon))
        return '\n'.join(r)

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Custom(Mode):
    '''Displays search results via a custom PX'''

    def init(self):
        '''By default, the Custom mode performs full (unpaginated) searches'''
        r = self.tool.executeQuery(self.className, search=self.uiSearch.search,
                                   maxResults='NO_LIMIT')
        # Initialise Mode's mandatory fields
        self.objects = r.objects
        self.empty = not self.objects
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
