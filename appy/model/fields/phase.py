# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import collections
from appy.px import Px
from appy.model.utils import Object

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Page:
    '''Used for describing a page, its related phase, show condition, etc.'''
    subElements = ('save', 'cancel', 'previous', 'next', 'edit')

    def __init__(self, name, phase='main', show=True, showSave=True,
                 showCancel=True, showPrevious=True, showNext=True,
                 showEdit=True, label=None):
        self.name = name
        self.phase = phase
        self.show = show
        # When editing the page, must I show the "save" button?
        self.showSave = showSave
        # When editing the page, must I show the "cancel" button?
        self.showCancel = showCancel
        # When editing the page, and when a previous page exists, must I show
        # the "previous" button?
        self.showPrevious = showPrevious
        # When editing the page, and when a next page exists, must I show the
        # "next" button?
        self.showNext = showNext
        # When viewing the page, must I show the "edit" button?
        self.showEdit = showEdit
        # The i18n label may be forced here instead of being deduced from the
        # page name.
        self.label = label

    @staticmethod
    def get(pageData):
        '''Produces a Page instance from p_pageData. User-defined p_pageData
           can be:
           (a) a string containing the name of the page;
           (b) a string containing <pageName>_<phaseName>;
           (c) a Page instance.
           This method returns always a Page instance.'''
        r = pageData
        if r and isinstance(r, str):
            # Page data is given as a string
            pageElems = pageData.rsplit('_', 1)
            if len(pageElems) == 1: # We have case (a)
                r = Page(pageData)
            else: # We have case (b)
                r = Page(pageData[0], phase=pageData[1])
        return r

    def isShowable(self, o, layout, elem='page'):
        '''Is this page showable for p_o on p_layout ("view" or "edit")?

           If p_elem is not "page", this method returns the fact that a
           sub-element is viewable or not (buttons "save", "cancel", etc).'''
        # Define what attribute to test for "showability"
        attr = 'show' if elem == 'page' else 'show%s' % elem.capitalize()
        # Get the value of the "show" attribute as identified above
        r = getattr(self, attr)
        if callable(r):
            r = o.H().methods.call(o, r)
        if isinstance(r, str): return r == layout
        return r

    def nextName(self):
        '''If this page has a name being part of a series (ie numeric:
           1, 2, 3... or alphabetical like a, b, c...), this method returns the
           next name in the series.'''
        name = self.name
        if name.isdigit():
            # Increment this number by one and get the result as a string
            r = str(int(name) + 1)
        elif (len(name) == 1) and name.islower() and (name != 'z'):
            r = chr(ord(name) + 1)
        else:
            # Repeat the same name
            r = name
        return r

    def __repr__(self): return '<Page %s - phase %s>' % (self.name, self.phase)

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class UiPage:
    '''A page object built at run time, containing only information tied to the
       execution context.'''

    def __init__(self, uiPhase, page, showOnView, showOnEdit):
        # The link to the container phase
        self.uiPhase = uiPhase
        # The corresponding Page instance
        self.page = page
        self.name = page.name
        # Must the page be shown on view/edit layouts ?
        self.showOnView = showOnView
        self.showOnEdit = showOnEdit
        # Must other sub-elements (buttons "save", "next", etc) be shown ?
        phases = uiPhase.container
        o = phases.o
        layout = phases.layout
        for elem in Page.subElements:
            showable = page.isShowable(o, layout, elem)
            setattr(self, 'show%s' % elem.capitalize(), showable)
        # Make a link between this page and the previous one when relevant =
        # when there is a previous page and when both pages are visible on the
        # current layout.
        self.previous = uiPhase.container.lastPage
        self.next = None
        if self.previous and \
           self.previous.showable(layout) and self.showable(layout):
            self.previous.next = self

    def getLabel(self):
        '''Returns the translated label for this page, potentially based on a
           fixed label if p_self.label is not empty.'''
        page = self.page
        o = self.uiPhase.container.o
        label = page.label or '%s_page_%s' % (o.class_.name, page.name)
        return o.translate(label)

    def showable(self, layout):
        '''Return True if this page is showable on p_layout'''
        return self.showOnEdit if layout == 'edit' else self.showOnView

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Phase:
    '''A phase is a group of pages within a class'''
    # This class is used only in order to generate phase- and page-related i18n
    # labels, and as general information about all phases and pages defined for
    # a class in the app's model.

    # It is not used by the Appy developer: if a phase must be defined by him in
    # an app, he will do it via a phase name specified as a string, in attribute
    # "phase" of class Page hereabove.

    # It is not used by Appy at run-time neither: class UiPhases is used
    # instead. Indeed, at run-time, the set of phases and pages which are
    # visible by the logged user can be a sub-set of all statically-defined
    # phases and pages.

    def __init__(self, name):
        self.name = name
        # A phase is made of pages ~{p_name: appy.model.fields.page.Page}~
        self.pages = collections.OrderedDict()

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class UiPhase:
    '''A phase object built at run time, containing only the visible pages
       depending on user's permissions.'''

    view = Px('''
     <table class="phase">
      <tr valign="top">
       <!-- The page(s) within the phase -->
       <td for="opage in phase.pages.values()"
           class=":(opage.name == page) and 'currentPage' or ''">
        <!-- Page name and icons -->
        <x var="label=opage.getLabel()">
         <a if="opage.showOnView"
            href=":o.getUrl(sub='view', page=opage.name, \
                            popup=popup)">::label</a>
         <x if="not opage.showOnView">::label</x>
        </x>
        <x var="locked=o.Lock.isSet(o, user, opage.name);
                editable=mayEdit and opage.showOnEdit and opage.showEdit">
         <a if="editable and not locked"
            href=":o.getUrl(sub='edit', page=opage.name, popup=popup)">
          <img src=":url('edit')" title=":_('object_edit')"/></a>
         <x var="page=opage.name; lockStyle=''">::o.Lock.px</x>
        </x>
       </td>
      </tr>
     </table>''')

    def __init__(self, name, phases):
        # The name of the phase
        self.name = name
        # Its translated label
        o = phases.o
        self.label = o.translate('%s_phase_%s' % (o.class_.name, name))
        # A link to the global UiPhases object
        self.container = phases
        # The included pages, as a dict of UiPage instances
        self.pages = collections.OrderedDict()
        # The pages that were already walked, but that must not be shown
        self.hidden = {}

    def singlePaged(self):
        '''Is p_self a phase containing a single page ?'''
        return len(self.pages) == 1

    def addPage(self, page):
        '''Adds page-related information in the phase'''
        # If the page is already there, we have nothing more to do
        if (page.name in self.pages) or (page.name in self.hidden): return
        # Add the page only if it must be shown
        o = self.container.o
        currentPage = self.container.currentPage
        showOnView = page.isShowable(o, 'view')
        showOnEdit = page.isShowable(o, 'edit')
        if showOnView or showOnEdit:
            # The page must be added
            self.pages[page.name] = self.container.lastPage = \
              UiPage(self, page, showOnView, showOnEdit)
            # Set it as current page when relevant
            if currentPage is None and \
               (page.name == self.container.currentPageName):
                self.container.currentPage = self.container.lastPage
        else:
            # The page must be hidden, and we must remember that fact
            self.hidden[page.name] = None

    def __repr__(self):
        if self.pages:
            pages = ': page(s) %s' % ','.join(list(self.pages.keys()))
        else:
            pages = ' (empty)'
        return '<phase %s%s>' % (self.name, pages)

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class UiPhases:
    '''Represents the (sub-)set of phases and pages for some object that the
       currently logged user may see or edit.'''

    # PX displaying all phases of a given object
    view = Px('''
     <x if="not phases.singlePage()"
        var2="mayEdit=guard.mayEdit(o);
              singlePhase=phases.singlePhase();
              id=o.id">
      <!-- Single phase: display its pages -->
      <x if="singlePhase" var2="phase=phases.default">:phase.view</x>
      <!-- Several phases: add a tab for every phase -->
      <x if="not singlePhase">
       <table cellpadding="0" cellspacing="0">
        <!-- First row: the tabs -->
        <tr><td style="border-bottom: 1px solid #ff8040; padding-bottom: 1px">
         <table cellpadding="0" cellspacing="0" class="tabs" id=":'tabs_%s'%id">
          <tr valign="middle">
           <x for="phase in phases.all.values()"
              var2="suffix='%s_%s' % (id, phase.name);
                    tabId='tab_%s' % suffix">
            <td><img src=":url('tabLeft')" id=":'%s_left' % tabId"/></td>
            <td style=":url('tabBg',bg=True)" id=":tabId" class="tab">
             <a onclick=":'showTab(%s)'% q(suffix)"
                class="clickable">:phase.label</a>
            </td>
            <td><img id=":'%s_right' % tabId" src=":url('tabRight')"/></td>
           </x>
          </tr>
         </table>
        </td></tr>
        <!-- Other rows: the fields -->
        <tr for="phase in phases.all.values()"
            id=":'tabcontent_%s_%s' % (id, phase.name)"
          style=":(loop.phase.nb==0) and 'display:table-row' or 'display:none'">
         <td>:phase.view</td>
        </tr>
       </table>
       <script>:'initTab(%s,%s)' % \
             (q('tab_%s' % id), q('%s_%s' % (id, phases.default.name)))</script>
      </x>
     </x>''')

    def __init__(self, page, o, layout):
        '''Initialises a structure allowing to render currently visible phases
           for p_o, for which the page named p_page is currently shown.'''
        # The object for which phases must be produced
        self.o = o
        # The layout
        self.layout = layout
        # The involved phases will be stored here, as UiPhase instances
        self.all = collections.OrderedDict()
        # The default phase (= the first encountered one)
        self.default = None
        # The currently shown page
        self.currentPageName = page
        self.currentPage = None
        # p_o's default page on p_layout
        self.defaultPageName = o.getDefaultPage(layout)
        # The last inserted page
        self.lastPage = None

    def singlePhase(self):
        '''Returns True if there is a single phase'''
        return len(self.all) == 1

    def singlePage(self):
        '''Returns True if there is a single page within a single phase'''
        if not self.singlePhase(): return
        return len(self.default.pages) == 1

    def addField(self, field):
        '''A new p_field has been encountered: it implies updating phases and
           pages.'''
        # Insert p_fields' phase and page into p_self.all
        phase = field.page.phase
        if phase not in self.all:
            uiPhase = self.all[phase] = UiPhase(phase, self)
            # Set it as default phase if there is no default phase yet
            if self.default is None:
                self.default = uiPhase
        else:
            uiPhase = self.all[phase]
        uiPhase.addPage(field.page)

    def unshowableCurrentPage(self):
        '''Return True if the current page can't be shown'''
        # The default page is always supposed to be showable
        if self.currentPageName == self.defaultPageName: return
        current = self.currentPage
        return not current or not current.showable(self.layout)

    def finalize(self):
        '''Finalize phases, ie, by removing phases without any visible page'''
        # Remove phases without page
        for name in self.all.keys():
            if not self.all[name].pages:
                del(self.all[name])
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
