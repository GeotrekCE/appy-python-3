# ~license~
# ------------------------------------------------------------------------------
import copy, types, re
from appy.px import Px
from appy import utils
from appy.model.utils import Object
from appy.tr import FieldTranslations
from appy.utils import string as sutils
from appy.model.fields.phase import Page
from appy.model.fields.group import Group
from appy.ui.layout import Layout, Layouts

# In this file, names "list" and "dict" refer to sub-modules. To use Python
# builtin types, use __builtins__['list'] and __builtins__['dict']

# ------------------------------------------------------------------------------
XSS_DETECTED = 'Detected Javascript in user input.'
XSS_WARNING = 'Your behaviour is considered a security attack. System ' \
              'administrator has been warned.'
SEARCH_TRIGGER = '%s field %s:%s: executing search %s...'
SEARCH_DONE = 'fetched %d object(s).'

# ------------------------------------------------------------------------------
class Show:
    '''Provides some frequently used values for field's "show" attributes'''
    # As a convention, a trailing underscore indicates a negation

    # All layouts but edit. To use for users that can consult the field value
    # but cannot modify it. Also used for fields like some Ref fields that are
    # never manipulated via "edit" layouts.
    E_ = ('view', 'result', 'xml')
    # A variant, without "result"
    ER_ = ('view', 'xml')
    # A variant, with layout "buttons" instead of "result". "buttons"
    # corresponds, on lists, to the range of icons and/or buttons present in the
    # "title" column.
    E_B = ('view', 'buttons', 'xml')
    B = ('edit', 'view', 'buttons', 'xml')

    # All layouts but view. To use typically when, on view, the field value is
    # already shown as a part of some custom widget.
    V_ = ('edit', 'result', 'xml')
    # All layouts but view and edit. To use when you need both E_ and V_.
    VE_ = ('result', 'xml')
    # This set is used for showing workflow transitions in lists of objects
    TR = ('view', 'result')
    # This is, a.o., for custom widgets whose edit and view variants are not
    # that different, but that cannot be shown elsewhere (result, xml, etc).
    VE = ('view', 'edit')
    VX = ('view', 'xml')
    EX = ('edit', 'xml')

# ------------------------------------------------------------------------------
class Initiator:
    '''From a given field on a given object, it is possible to trigger the
       creation of another object. The most obvious example is the creation of a
       tied object via a Ref field with add=True. An "initiator" represents the
       (object, field) that initiates the object creation.

       In order to customize initiator behaviour, every Field sub-class can
       propose an Initiator sub-class, via overriding its static attribute
       "initiator".'''

    # The concept of initiator can also be used in the context of visualizing
    # objects. For example, when displaying a tied object via a Ref, its
    # "initiator" is considered to be the source object and the source Ref.

    def __init__(self, tool, req, info):
        self.tool = tool
        self.req = req
        # Extract the initiator object and field from p_info, parsed from a
        # "nav" key in the request, or directly containing a tuple (o, field).
        if isinstance(info, str):
            self.info = info.split('.')
            self.o = tool.getObject(self.info[0])
            self.field = self.extractField(req)
        else:
            self.info = ''
            self.o, self.field = info
        # After having created the object, if we are back from a popup, the
        # initiator may force to go back to some URL.
        self.backFromPopupUrl = None

    def extractField(self, req):
        '''Tries to get the initiator field from the request'''
        r = self.o.getField(self.info[1])
        if r is None:
            # This can be an "objectless" initiator. In that case, p_self.o is
            # the tool and the field's class is specified at another index in
            # p_self.info.
            r = self.o.getField(self.info[1], className=self.info[2])
        return r

    def getUrl(self):
        '''Returns the URL for going back to the initiator object, on the page
           showing self.field.'''
        return self.o.getUrl(sub='view', page=self.field.pageName, nav='no')

    def checkAllowed(self):
        '''Checks that adding an object via this initiator is allowed'''
        return True

    def updateParameters(self, params):
        '''Add the relevant parameters to the object edition page, related to
           this initiator.'''

    def goBack(self):
        '''Once the object has been created, where must we come back ? r_ can be
           - "view"        return to the "view" page of the created object;
           - "initiator"   return to the page, on self.obj, where self.field is.
        '''
        return 'view'

    def getNavInfo(self, new):
        '''If m_goBack is "view" and navigation-related information must be
           shown on the "view" page of the p_new object, this method returns
           it.'''

    def getBackUrl(self, o):
        '''Get the URL to go to after having initiated creation of object p_o'''
        if self.goBack() == 'view':
            # Stay on the "view" page of the newly created object p_o
            r = o.getUrl(nav=self.getNavInfo(o))
        else:
            # Go back to the initiator page
            r = self.getUrl()
        return r

    def manage(self, new):
        '''Once the p_new object has been created, the initiator must surely
           perform a given action with it (ie, for a Ref field, the new object
           must be linked to the initiator object. This is the purpose of this
           method.'''

# ------------------------------------------------------------------------------
class Field:
    '''Basic abstract class for defining any field'''

    # Make some related classes available here
    Translations = FieldTranslations
    Layouts = Layouts

    # Some global static variables
    nullValues = (None, '', [], {}, ())
    validatorTypes = (types.FunctionType, type(re.compile('')))
    labelTypes = ('label', 'descr', 'help')
    viewLayouts = ('view', 'cell')

    # Those attributes can be overridden by subclasses for defining,
    # respectively, names of CSS and Javascript files that are required by this
    # field, keyed by layoutType.
    cssFiles = {}
    jsFiles = {}

    # For most fields, getting its value on some object is automatically done at
    # the framework level. Fields for which this must be disabled override the
    # following static attribute.
    customGetValue = False

    # Some fields are "outer": they are composed or inner fields
    outer = False

    # Parameters needed to re-trigger a search. Some fields applying on sets of
    # objects may need to re-trigger a search from these request parameters.
    searchParams = ('className', 'search', 'sortKey', 'sortOrder', 'filters')

    # The base method for getting a field's searchable value (see
    # m_getSearchableValue).
    searchableBase = 'getIndexValue'

    # The initiator class related to the Field
    initiator = Initiator

    # Render a field. Optional vars:
    # * fieldName   can be given as different as field.name for fields included
    #               in outer fields: in this case, fieldName includes the row
    #               index.
    # * showChanges If True, a variant of the field showing successive changes
    #               made to it is shown.
    # * minimal     If True, the PX related to p_layout is directly called
    #               (view, cell, etc), instead of layout.pxRender. While this
    #               disables some functions like master/slave relationships, it
    #               returns a more lightweight code.
    pxRender = Px('''<x var="minimal=minimal|False;
      showChanges=showChanges|req.showChanges == 'True';
      layout=layout|req.layout;
      isSearch=layout == 'search';
      hostLayout=req.hostLayout;
      name=fieldName or field.name|field.name;
      widgetName='w_%s' % name if isSearch else name;
      rawValue=field.getValueIf(o, name, layout, disable=isSearch);
      value=not isSearch and \
            field.getFormattedValue(o, rawValue, layout, showChanges);
      requestValue=not isSearch and field.getStoredValue(o, name, True);
      inRequest=field.valueIsInRequest(o, req, name, layout);
      error=req['%s_error' % name] or handler.validator.errors.get(name)|None;
      isMultiple=field.isMultiValued();
      masterCss=field.slaves and ('master_%s' % name) or '';
      tagCss=tagCss|None;
      tagCss=field.getTagCss(tagCss, layout);
      o=o or tool;
      tagId='%s_%s' % (o.id, name);
      tagName=field.master and 'slave' or '';
      layoutTarget=field">:field.getPx(minimal, \
                                       hostLayout or layout, _ctx_)</x>''')

    def doRender(self, layout, o, name=None, minimal=False):
        '''Allows to call pxRender from code, to display the content of this
           field on p_o in some specific context, for example in a Computed
           field.'''
        context = {'layout': layout, 'field': self, 'minimal': minimal,
                   'name': name or self.name, 'o': o}
        # Get the current PX context: we will need to copy some entries from it.
        # If no such context exists, create one.
        req = o.req
        if 'pxContext' in req:
            ctx = req.pxContext
            Px.copyBaseVariables(context, ctx)
        else:
            ctx = Px.setBaseVariables(obj.tool, context, obj)
        # Call pxRender
        return self.pxRender(context).encode('utf-8')

    # Show the field content for some object on a list of referred objects
    pxTied = Px('''
     <!-- The "title" field -->
     <x if="field.name == 'title'">
      <x if="mayView">
       <x if="not ifield.menuUrlMethod or \
              (layout != 'cell')">:ifield.pxObjectTitle</x>
       <x if="ifield.menuUrlMethod and (layout == 'cell')"
          var2="target,url=ifield.getMenuUrl(o, \
           tied)">::ui.Title.get(o, target=target, baseUrl=url)</x>
       <x if="not selector and guard.mayAct(o)">:ifield.pxObjectActions</x>
      </x>
      <div if="not mayView">
       <img src=":url('fake')" style="margin-right: 5px"/>
       <x>:_('unauthorized')</x></div>
     </x>
     <!-- Any other field -->
     <x if="mayView and (field.name != 'title') and \
            field.isShowable(o, 'result')"
        var2="layout='cell';
              fieldName=field.name;
              minimal=not field.inlineEdit">:field.pxRender</x>''')

    # Show the field content for some object on a list of results
    pxResult = Px('''
     <!-- The "title" field -->
     <x if="field.name == 'title'"
        var2="navInfo=mode.getNavInfo(currentNumber); target=mode.target;
              backHook=backHook|None">
      <x if="mayView"
         var2="pageName=o.getDefaultPage('view');
               selectJs=popup and uiSearch.initiator.jsSelectOne(q,cbId) or ''">
       <x if="hasattr(o, 'getSupTitle')">::o.getSupTitle(navInfo)</x>
       <x>::ui.Title.get(o, mode=mode.titleMode, nav=navInfo, target=target, \
          page=pageName, popup=popup, selectJs=selectJs, highlight=True, \
          backHook=backHook)</x>
       <span if="hasattr(o,'getSubTitle')" class=":class_.getCssFor('subTitle')"
             style=":mode.showSubTitles and 'display:inline' or 'display:none'"
             name="subTitle">::uiSearch.highlight(o.getSubTitle())</span>

       <!-- Actions -->
       <div if="not popup and uiSearch.showActions and guard.mayAct(o)"
            class="objectActions" style=":'display:%s'% uiSearch.actionsDisplay"
            var2="layoutType='buttons';
                  editable=guard.mayEdit(o);
                  locked=o.Lock.isSet(o, user, 'main')">
        <!-- Edit -->
        <x if="editable">
         <a if="not locked"
            var2="linkInPopup=popup or (target.target != '_self')"
            target=":target.target"
            onclick=":target.getOnClick(backHook or o.id)"
            href=":o.getUrl(sub='edit', page=o.getDefaultPage('edit'), \
                            nav=navInfo, popup=linkInPopup)">
          <img src=":url('edit')" title=":_('object_edit')"/>
         </a>
         <x if="locked" var2="lockStyle=''; page='main'">::o.Lock.px</x>
        </x>
        <!-- Delete -->
        <img if="not locked and guard.mayDelete(o)" class="clickable"
             src=":url('delete')" title=":_('object_delete')"
             onClick=":'onDeleteObject(%s)' % q(o.url)"/>
        <!-- Fields (actions) defined with layout "buttons" -->
        <x if="not popup"
           var2="fields=o.getFields('buttons', 'main');
                 layout='cell'">
         <!-- Call cell and not pxRender to avoid having a table -->
         <x for="field in fields"
            var2="name=field.name; smallButtons=True">:field.cell</x>
        </x>
        <!-- Workflow transitions -->
        <x if="class_.showTransitions(o, 'result')"
           var2="workflow=o.getWorkflow()">:workflow.pxTransitions</x>
       </div>
      </x>
      <x if="not mayView">
       <img src=":url('fake')" style="margin-right: 5px"/>
       <x>:_('unauthorized')</x>
      </x>
     </x>
     <!-- Any other field -->
     <x if="mayView and (field.name != 'title') and \
            field.isShowable(o, 'result')"
        var2="layout='cell';
              fieldName=field.name;
              minimal=not field.inlineEdit">:field.pxRender</x>''')

    # Displays a field label
    pxLabel = Px('''<label if="field.hasLabel and field.renderLabel(layout)"
     lfor=":field.name">::_('label', field=field)</label>''')

    # Displays a field description
    pxDescription = Px('''<span if="field.hasDescr"
     class="discreet">::_('descr', field=field)</span>''')

    # Displays a field help
    pxHelp = Px('''<abbr title=":_('help', field=field)"><img
     src=":url('help')"/></abbr>''')

    # Displays validation-error-related info about a field
    pxValidation = Px('''<x><abbr if="error" title=":error"><img
     src=":url('warning')"/></abbr><img if="not error"
     src=":url('warning_no.gif')"/></x>''')

    # Displays the fact that a field is required
    pxRequired = Px('''<img src=":url('required.gif')"/>''')

    # Button for showing changes to the field
    pxChanges = Px('''
     <div if="zobj.hasHistory(name)" style="margin-bottom: 5px">
      <!-- Button for showing the field version containing changes -->
      <input if="not showChanges"
             var2="label=_('changes_show');
                   css=ztool.getButtonCss(label)" type="button" class=":css"
             value=":label" style=":url('changes', bg=True)"
             onclick=":'askField(%s,%s,%s,null,%s)' % \
                       (q(tagId), q(obj.url), q('view'), q('True'))"/>
      <!-- Button for showing the field version without changes -->
      <input if="showChanges"
             var2="label=_('changes_hide');
                  css=ztool.getButtonCss(label)" type="button" class=":css"
             value=":label" style=":url('changesNo', bg=True)"
             onclick=":'askField(%s,%s,%s,null,%s)' % \
                       (q(tagId), q(obj.url), q('view'), q('False'))"/>
     </div>''')

    # Widget for filtering object values on query results
    pxFilterText = Px('''
     <x var="name=field.name;
             filterId='%s_%s' % (mode.hook, name);
             filterIdIcon='%s_icon' % filterId">
      <!-- Pressing the "enter" key in the field clicks the icon (onkeydown) -->
      <input type="text" size="7" id=":filterId"
             value=":mode.filters.get(name, '')"
             onkeydown=":'if (event.keyCode==13) document.getElementById ' \
                         '(%s).click()' % q(filterIdIcon)"/>
      <img id=":filterIdIcon" class="clickable" src=":url('funnel')"
           onclick=":'askBunchFiltered(%s,%s)' % (q(mode.hook), q(name))"/>
     </x>''')

    def __init__(self, validator, multiplicity, default, defaultOnEdit, show,
      page, group, layouts, move, indexed, mustIndex, indexValue, searchable,
      readPermission, writePermission, width, height, maxChars, colspan, master,
      masterValue, focus, historized, mapping, generateLabel, label, sdefault,
      scolspan, swidth, sheight, persist, inlineEdit, view, cell, edit, xml,
      translations):
        # The validator restricts which values may be defined. It can be an
        # interval (1,None), a list of string values ['choice1', 'choice2'],
        # a regular expression, a custom function, a Selection instance, etc.
        self.validator = validator
        # Multiplicity is a 2-tuple indicating the minimum and maximum
        # occurrences of values.
        self.multiplicity = multiplicity
        # Is the field required or not ? (derived from multiplicity)
        self.required = self.multiplicity[0] > 0
        # Default value
        self.default = default
        # Default value on layout "edit". If None, self.default is used instead.
        self.defaultOnEdit = defaultOnEdit
        # Must the field be visible or not?
        self.show = show
        # When displaying/editing the whole object, on what page and phase must
        # this field value appear?
        self.page = Page.get(page)
        self.pageName = self.page.name
        # Within self.page, in what group of fields must this one appear?
        self.group = Group.get(group)
        # The following attribute allows to move a field back to a previous
        # position (useful for moving fields above predefined ones).
        self.move = move
        # If indexed is True, a database index will be set on the field for
        # fast access.
        self.indexed = indexed
        # If "mustIndex", True by default, is specified, it must be a method
        # returning a boolean value. Indexation will only occur when this value
        # is True.
        self.mustIndex = mustIndex
        if not mustIndex and not callable(mustIndex):
            raise Exception('Value for param "mustIndex" must be a method.')
        # For an indexed field, the value stored in the index is deduced from
        # the field value and from the index type. If you want to store, in the
        # index, a value being transformed in some way, specify, in parameter
        # "indexValue" a method, accepting the stored value as single arg, and
        # returned the transformed (or alternative) value. Note that this
        # transform cannot modify the type of data structure. For example, for a
        # Ref, the received data structure is a list of objects; the method must
        # also produce a list of objects.
        self.indexValue = indexValue
        # If specified "searchable", the field will be added to some global
        # index allowing to perform application-wide, keyword searches.
        self.searchable = searchable
        # Normally, permissions to read or write every attribute in a class are
        # granted if the user has the global permission to read or write
        # instances of that class. Those global permissions are represented by
        # strings "read" and "write". If you want a given attribute, or a
        # sub-set of class attributes, to be protected by specific read and/or
        # write permissions, specify, for attributes "readPermission" and/or
        # "writePermission", alternate strings. When defining a workflow for
        # your class, do not forget to define, for every state and for every
        # custom permission you have mentioned in the following attributes, the
        # list of roles that are granted this permission.
        self.readPermission = readPermission
        self.writePermission = writePermission
        # Widget width and height
        self.width = width
        self.height = height
        # While width and height refer to widget dimensions, maxChars hereafter
        # represents the maximum number of chars that a given input field may
        # accept (corresponds to HTML "maxlength" property). "None" means
        # "unlimited".
        self.maxChars = maxChars or ''
        # If the widget is in a group with multiple columns, the following
        # attribute specifies on how many columns to span the widget.
        self.colspan = colspan or 1
        # The list of slaves of this field, if it is a master
        self.slaves = []
        # The behaviour of this field may depend on another, "master" field
        self.setMaster(master, masterValue)
        # If a field must retain attention in a particular way, set focus=True.
        # It will be rendered in a special way.
        self.focus = focus
        # If we must keep track of changes performed on a field, "historized"
        # must be set to True.
        self.historized = historized
        # Mapping is a dict of contexts that, if specified, are given when
        # translating the label, descr or help related to this field.
        self.mapping = self.formatMapping(mapping)
        self.id = id(self)
        self.type = self.__class__.__name__
        self.pythonType = None # The True corresponding Python type
        # Get the layouts. Consult layout.py for more info about layouts.
        self.layouts = layouts = Layouts.getFor(self, layouts)
        # Derive the following attributes from the layouts, determining the
        # presence of the various types of labels on this field.
        self.hasLabel = layouts.hasPart('l')
        self.hasDescr = layouts.hasPart('d')
        self.hasHelp  = layouts.hasPart('h')
        # Can this field have values that can be edited and validated?
        self.validable = True
        # By default, if the base label for a field is in use in at least one of
        # its layouts (in p_self.layouts), it will be generated automatically in
        # your app's .pot and .po files. That being said, if the base label is
        # not used in any layout, but you still want it to be generated, for
        # using it in some other, non standard place like a pod or a custom
        # report, set the following attribute to True.
        self.generateLabel = generateLabel
        # If you want to avoid generating translation labels for this field, and
        # use instead translations already defined on another field, use the
        # following attribute "label". A label is made of 2 parts: the prefix,
        # based on class name, and the name, which is the field name by default.
        # ----------------------------------------------------------------------
        # If "label" is... | it will be understood as...
        # ----------------------------------------------------------------------
        # a string         | a new prefix = a new class name. Your field will
        #                  | use the label of an homonym field on another class.
        # ----------------------------------------------------------------------
        # a tuple          | a tuple (prefix, name), defining both a new prefix
        #                  | and a new field name. Your field will get the label
        #                  | of a field from another class, having another name.
        #                  | And if you want to reuse labels of another field
        #                  | defined on the same class, use a tuple of the form
        #                  |                 (None, name)
        # ----------------------------------------------------------------------
        self.label = label
        # When you specify a default value "for search" (= "sdefault"), on a
        # search screen, in the search field corresponding to this field, this
        # default value will be present.
        self.sdefault = sdefault
        # Colspan for rendering the search widget corresponding to this field.
        self.scolspan = scolspan or 1
        # Width and height for the search widget
        self.swidth = swidth or width
        self.sheight = sheight or height
        # "persist" indicates if field content must be stored in the database.
        # For some fields it is not wanted (ie, fields used only as masters to
        # update slave's selectable values).
        self.persist = persist
        # Can the field be inline-edited (on "view" or "cell" layouts)? A method
        # can be specified.
        self.inlineEdit = inlineEdit
        # If you want to use alternate PXs than Field.view, Field.cell and
        # Field.edit, you can specify it in parameters "view", "cell" and
        # "edit". Instance attributes "view", "cell" and "edit" below will
        # override their corresponding class attributes.
        if view is not None: self.view = view
        if cell is not None: self.cell = cell
        if edit is not None: self.edit = edit
        # Standard marshallers are provided for converting values of this field
        # into XML. If you want to customize the marshalling process, you can
        # define a method in "xml" that will accept a field value and will
        # return a possibly different value. Be careful: do not return a chunk
        # of XML here! Simply return an alternate value, that will be
        # XML-marshalled.
        if xml is not None: self.xml = xml
        # The PX for filtering field values. If None, it means that the field is
        # not filterable.
        self.filterPx = None
        # The standard system for getting field translations (label,
        # description, etc) is based on translations stored in persistent
        # Translation instances in tool.translations. But one may bypass this
        # system by placing an instance of class
        #            appy.fields.translations.FieldTranslations
        # in this attribute.
        self.translations = translations

    def init(self, class_, name):
        '''Lazy initialisation'''
        # The class into which this field is defined
        self.container = class_
        # The name of the field
        self.name = name
        # Remember master name on every slave
        for slave in self.slaves: slave.masterName = name
        # Determine ids of i18n labels for this field, excepted if translations
        # are already present in self.tranlations.
        if not self.translations:
            prefix = label = None
            if self.label:
                if isinstance(self.label, str):
                    prefix = self.label
                else: # It is a tuple (prefix, name)
                    prefix, label = self.label
            # Complete missing information
            prefix = prefix or class_.name
            label = label or self.name
            # Determine name to use for i18n
            self.labelId = '%s_%s' % (prefix, label)
            self.descrId = '%s_descr' % self.labelId
            self.helpId  = '%s_help' % self.labelId

    def __repr__(self):
        '''String representation for this field'''
        name = '%s::%s' % (self.container.name, self.name) \
               if hasattr(self, 'container') else 'uninit'
        return '<field %s (%s)>' % (name, self.__class__.__name__.lower())

    def isMultiValued(self):
        '''Does this type definition allow to define multiple values?'''
        maxOccurs = self.multiplicity[1]
        return (maxOccurs is None) or (maxOccurs > 1)

    def isSortable(self, usage):
        '''Can fields of this type be used for sorting purposes, when sorting
           search results (p_usage="search") or when sorting reference fields
           (p_usage="ref")?'''
        if usage == 'search':
            indexed = self.indexed
            return indexed and (indexed != 'TextIndex') and \
                   not self.isMultiValued()
        # For usage being "ref", this method will be overridden by fields for
        # which sort is allowed.

    def isShowable(self, o, layout):
        '''When displaying p_o on a given p_layout, must we show this field ?'''
        # Check if the user has the permission to view or edit the field
        perm = self.writePermission if (layout=='edit') else self.readPermission
        if not o.allows(perm): return
        # Evaluate self.show
        if callable(self.show):
            r = self.callMethod(o, self.show)
        else:
            r = self.show
        # Take into account possible values 'view', 'edit', 'result', etc.
        if type(r) in utils.sequenceTypes:
            return layout in r
        elif r in Layouts.types:
            return r == layout
        # For showing a field on some layouts, they must explicitly be returned
        # by the "show" method.
        if layout not in Layouts.explicitTypes:
            return bool(r)

    def isRenderable(self, layout):
        '''In some contexts, computing m_isShowable can be a performance
           problem. For example, when showing some object's fields on layout
           "buttons", there are plenty of fields that simply can't be shown on
           this kind of layout: it is no worth computing m_isShowable for those
           fields. m_isRenderable is meant to define light conditions to
           determine, before calling m_isShowable, if some field has a chance to
           be shown or not.

           In other words, m_isRenderable defines a "structural" condition,
           independent of any object, while m_isShowable defines a contextual
           condition, depending on some object.'''
        # Most fields are not renderable on layout "buttons"
        return False if layout == 'buttons' else True

    def isClientVisible(self, o):
        '''Returns True if p_self is visible according to master/slave
           relationships.'''
        masterData = self.getMasterData()
        if not masterData: return True
        else:
            master, masterValue = masterData
            if masterValue and callable(masterValue): return True
            # Get the master value from the request
            req = o.req
            if (master.name not in req) and (self.name in req):
                # The master is not there: we cannot say if the slave must be
                # visible or not. But the slave is in the request. So we should
                # not prevent this value from being taken into account.
                return True
            reqValue = master.getRequestValue(o)
            # reqValue can be a list or not
            if type(reqValue) not in utils.sequenceTypes:
                return reqValue in masterValue
            else:
                for m in masterValue:
                    for r in reqValue:
                        if m == r: return True

    def inGrid(self, layout='edit'):
        '''Is this field in a group with style "grid" ?'''
        if not self.group: return
        if isinstance(self.group, __builtins__['dict']):
            for lay, group in self.group.items():
                if lay != layout: continue
                return group and (group.style == 'grid')
            return
        return self.group.style == 'grid'

    def formatMapping(self, mapping):
        '''Creates a dict of mappings, one entry by label type (label, descr,
           help).'''
        if isinstance(mapping, __builtins__['dict']):
            # Is it a dict like {'label':..., 'descr':...}, or is it directly a
            # dict with a mapping?
            for k, v in mapping.items():
                if (k not in self.labelTypes) or isinstance(v, str):
                    # It is already a mapping
                    return {'label':mapping, 'descr':mapping, 'help':mapping}
            # If we are here, we have {'label':..., 'descr':...}. Complete
            # it if necessary.
            for labelType in self.labelTypes:
                if labelType not in mapping:
                    mapping[labelType] = None # No mapping for this value
            return mapping
        else:
            # Mapping is a method that must be applied to any i18n message
            return {'label':mapping, 'descr':mapping, 'help':mapping}

    def getPx(self, minimal, layout, context):
        '''Returns the PX corresponding to p_layout'''
        if minimal:
            # Call directly the layout-related PX on the field (bypass the
            # layout PX)
            r = getattr(self, layout)
        else:
            # Get the Layout instance related to p_layout and render its PX
            if layout == 'cell':
                table = self.Layouts.cell
            else:
                table = self.layouts[layout]
            # Add the layout in the context, it is required by its PX
            context['table'] = table
            r = table.pxRender
        return r

    def setMandatoriness(self, required):
        '''Updating mandatoriness for a field is not easy, this is why this
           method exists.'''
        # Update attributes "required" and "multiplicity"
        self.required = required
        self.multiplicity = (1 if required else 0), self.multiplicity[1]
        # Update the "edit" layout
        self.layouts['edit'].setRequired(required)

    def setMaster(self, master, masterValue):
        '''Initialises the master and the master value if any'''
        self.master = master
        if master: self.master.slaves.append(self)
        # The semantics of attribute "masterValue" below is as follows:
        # - if "masterValue" is anything but a method, the field will be shown
        #   only when the master has this value, or one of it if multivalued;
        # - if "masterValue" is a method, the value(s) of the slave field will
        #   be returned by this method, depending on the master value(s) that
        #   are given to it, as its unique parameter.
        self.masterValue = utils.initMasterValue(masterValue)

    def getCss(self, layout, r):
        '''Complete list p_r with the names of CSS files that are required for
           displaying widgets of self's type on a given p_layout. p_r is not a
           set because order of inclusion of CSS files may be important.'''
        if layout in self.cssFiles:
            for name in self.cssFiles[layout]:
                if name not in r:
                    r.append(name)

    def getJs(self, layout, r, config):
        '''Completes list p_r with the names of Javascript files that are
           required for displaying widgets of self's type on a given p_layout.
           p_r is not a set because order of inclusion of Javascript files may
           be important.'''
        if layout in self.jsFiles:
            for name in self.jsFiles[layout]:
                if name not in r:
                    r.append(name)

    def isInner(self):
        '''Returns True if p_self is an inner field within a container field'''
        return '*' in self.name

    def getStoredValue(self, o, name=None, fromRequest=False):
        '''Gets the value in its form as stored in the database, or in the
           request if p_fromRequest is True. It differs from calling
           m_getRequestValue because here, in the case of an inner field, the
           request value is searched within the outer value build and stored on
           the request.'''
        if self.isInner():
            # p_self is a sub-field into an outer field: p_name is of the form
            #            [outerName]*[name]*[rowId]
            outerName, name, rowId = name.split('*')
            if rowId == '-1': r = None # It is a template row
            else:
                # Get the outer value
                r = o.req[outerName] if fromRequest else o.values.get(outerName)
                # Access the inner value
                if r:
                    if rowId.isdigit():
                        rowId = int(rowId)
                        if rowId < len(r):
                            r = getattr(r[rowId], name, None)
                        else:
                            r = None
                    else:
                        r = r.get(rowId, None)
                        if r: r = r.get(name, None)
            # Return an empty string if fromRequest is True
            if fromRequest and (r is None): r = ''
        else:
            r = self.getRequestValue(o, self.name) if fromRequest \
                else o.values.get(self.name)
        return r

    def getRequestValue(self, o, requestName=None):
        '''Gets a value for this field as carried in the request. In the
           simplest cases, the request value is a single value whose name in the
           request is the name of the field.

           Sometimes, several request values must be combined (ie: see the
           overriden method in the Date class).

           Sometimes (ie, a field within a List/Dict), the name of the request
           value(s) representing the field value does not correspond to the
           field name (ie: the request name includes information about
           the container field). In this case, p_requestName must be used for
           searching into the request, instead of the field name (self.name).'''
        name = requestName or self.name
        return o.req.get(name)

    def setRequestValue(self, o):
        '''Sets, in the request, field value on p_obj in its "request" form
           (=the way the value is carried in the request).'''
        # Get a copy of the field value on p_obj and put it in the request
        value = self.getCopyValue(o)
        if value != None:
            o.req[self.name] = value

    def getRequestSuffix(self):
        '''In most cases, in the user interface, there is one homonym HTML
           element for representing this field. Sometimes, several HTML elements
           are used to represent one field (ie, for dates: one field for the
           year, one for the month, etc). In this case, every HTML element's
           name has the form <field name><suffix>. This method returns the
           suffix of the "main" HTML element.'''
        return ''

    def getValue(self, o, name=None, layout=None):
        '''Gets, on p_o(bject), the value for this field (p_self)'''
        # Possible values for parameters are described hereafter.
        # ----------------------------------------------------------------------
        # name    | p_name can be different from self.name if p_self is a
        #         | sub-field into a List: in this case, it includes the row
        #         | number.
        # ----------------------------------------------------------------------
        # layout  | In most cases, we don't care about the layout for getting
        #         | the value of p_self on p_obj. One exception is that a
        #         | default value can be defined specifically on layout "edit".
        #         | In that case, p_layout must be available in order to
        #         | determine the possible specific default value for this
        #         | layout.
        # ----------------------------------------------------------------------
        # Get the value from the database
        value = self.getStoredValue(o, name)
        if self.isEmptyValue(o, value):
            # If there is no value, get the default value if any. Determine
            # which one must be used: p_self.default or p_self.defaultOnEdit.
            if layout == 'edit':
                default = self.defaultOnEdit
                if default is None: default = self.default
            else:
                default = self.default
            # Get the default value, which can be a method
            if callable(default):
                try:
                    # Caching a default value can lead to problems. For example,
                    # the process of creating an object from another one, or
                    # from some data, sometimes consists in (a) creating an
                    # "empty" object, (b) initializing its values and
                    # (c) reindexing it. Default values are computed in (a),
                    # but it they depend on values set at (b), and are cached
                    # and indexed, (c) will get the wrong, cached value.
                    default = self.callMethod(o, default, cache=False)
                except Exception:
                    # Already logged. Here I do not raise the exception,
                    # because it can be raised as the result of reindexing
                    # the object in situations that are not foreseen by
                    # method in self.default.
                    default = None
            return default
        return value

    def getValueIf(self, o, name, layout, disable=False):
        '''Special method only called by the framework. For some fields (or
           according to some p_disable condition), value retrieval as performed
           here must be disabled.'''
        if disable or self.customGetValue: return
        return self.getValue(o, name, layout)

    def getCopyValue(self, o):
        '''Gets the value of this field on p_o as with m_getValue above. But
           if this value is mutable, get a copy of it.'''
        return self.getValue(o)

    def getFormattedValue(self, o, value, layout='view', showChanges=False,
                          language=None):
        '''p_value is a real p_o(bject) value from a field from this type. This
           method returns a pretty, string-formatted version, for displaying
           purposes. Needs to be overridden by some child classes. If
           p_showChanges is True, the result must also include the changes that
           occurred on p_value across the ages. If the formatting implies
           translating some elements, p_language will be used if given, the
           user language else.'''
        if self.isEmptyValue(o, value): return ''
        return value

    def getShownValue(self, o, value, layout='view', showChanges=False,
                      language=None):
        '''Similar to m_getFormattedValue, but in some contexts, only a part of
           p_value must be shown. For example, we may need to display only
           a language-specific part of a multilingual field (see overridden
           method in string.py).'''
        return self.getFormattedValue(o, value, layout, showChanges, language)

    def getXmlValue(self, obj, value):
        '''This method allows a developer to customize the value that will be
           marshalled into XML. It makes use of attribute "xml".'''
        if not self.xml: return value
        return self.xml(obj, value)

    def getSearchValue(self, form, widgetName=None):
        '''Returns the search value (or interval of values) that has been
           encoded in a search p_form for matching values for this field.'''
        # The base search widget corresponding to p_self is prefixed with "w_".
        # p_widgetName can be specified to get the sub-value of another widget
        # that is part of the complete search widget for p_self.
        widgetName = widgetName or ('w_%s' % self.name)
        # p_value is the base (string) value encoded in the search form. But
        # the search value (or interval of values) can be made of several form
        # fields: overriden methods of this method in Field sub-classes may be
        # much more complex.
        r = form.get(widgetName)
        if isinstance(r, __builtins__['list']):
            # It is a list of values. Check if we have an operator for the
            # field, to see if we make an "and" or "or" for all those values.
            # "or" will be the default.
            operKey = 'o_%s' % self.name
            oper = ' %s ' % form.get(operKey, 'or').upper()
            r = oper.join(r)
        elif r:
            r = r.strip()
        return r or None

    def searchValueIsEmpty(self, form, widgetName=None):
        '''In some search p_form, can the search value or interval of values
           specified for this field (p_self) be considered as empty ?'''
        # If, for example, the search widget for this field is made of an
        # interval (from, to), p_widgetName can be given to correspond to the
        # widget part "to", while, by default, the specified part is "from". For
        # some Field sub-classes, the search widget may be even more complex and
        # made of more parts.
        widgetName = widgetName or ('w_%s' % self.name)
        # Conditions in overriden methods can be more complex. For example, if
        # an interval of values (min, max) is expected, specifying only "min" or
        # "max" will allow to perform a search. In this case, we will consider
        # the search value as empty if both "min" and "max" are not specified.
        value = form.get(widgetName)
        if value and isinstance(value, str): value = value.strip()
        return not value

    def getInlineEditableValue(self, obj, value, layoutType):
        '''Returns p_value as it must appear on a view layout, with code
           allowing to inline-edit it when relevant.'''
        if obj.allows('write') and self.getAttribute(obj, 'inlineEdit'):
            hook = '%s_%s' % (obj.id, self.name)
            return '<span class="editable" onclick="askField(\'%s\',\'%s\',' \
              '\'edit:%s\')">%s</span>' % (hook, obj.url, layoutType, value)
        return value

    def getIndexType(self):
        '''Returns the name of the technical, Zope-level index type for this
           field.'''
        # Normally, self.indexed contains a Boolean. If a string value is given,
        # we consider it to be an index type. It allows to bypass the standard
        # way to decide what index type must be used.
        if isinstance(self.indexed, str): return self.indexed
        if self.name == 'title': return 'TextIndex'
        return 'FieldIndex'

    def getIndexValue(self, o):
        '''Return a version for this field value on p_o being ready for indexing
           purposes.'''
        # Must we produce an index value ?
        if not self.getAttribute(o, 'mustIndex'): return
        # The indexed value is based on the stored field value
        r = self.getValue(o)
        # Possibly transform the value
        return self.indexValue(o, r) if self.indexValue else r

    def tokenizeValue(self, value):
        '''Used by m_getSearchableValue to transform p_value into tokens'''
        return str(value).split()

    def getSearchableValue(self, o):
        '''Return a "tokenized" version of this field value on p_o (as a set of
           strings) that is ready to be included in the indexed, keyword-based
           field o.searchable.'''
        # The searchable value is based on the value as defined by attribute
        # "searchableBase". In most cases, it is the indexed value.
        value = getattr(self, self.searchableBase)(o)
        if value is None: return
        # Create the set
        r = set()
        if type(value) not in utils.sequenceTypes:
            # A single value
            for token in self.tokenizeValue(value):
                r.add(token)
        else:
            # A sequence
            for v in value:
                for token in self.tokenizeValue(v):
                    r.add(token)
        return r

    def getIndexName(self, usage='search'):
        '''Gets the name of the Zope index that corresponds to this field.
           Indexes can be used for searching (p_usage="search"), filtering
           ("filter") or sorting ("sort"). The method returns None if the field
           named p_fieldName can't be used for p_usage.'''
        # Manage special cases
        if self.name == 'title':
            # For field 'title', Appy has a specific index 'SortableTitle',
            # because index 'Title' is a TextIndex (for searchability) and can't
            # be used for sorting.
            if usage == 'sort': return 'SortableTitle'
            elif usage == 'filter':
                return self.searchable and 'SearchableText' or 'Title'
            else: return 'Title'
        elif self.name == 'state': return 'State'
        elif self.name == 'SearchableText': return 'SearchableText'
        else:
            res = 'get%s%s'% (self.name[0].upper(), self.name[1:])
            if (usage == 'sort') and self.hasSortIndex(): res += '_sort'
        return res

    def hasSortIndex(self):
        '''Some fields have indexes that prevents sorting (ie, list indexes).
           Those fields may define a secondary index, specifically for sorting.
           This is the case of Ref fields for example.'''
        return

    def getSortValue(self, obj):
        '''Return the value of p_self on p_obj that must be used for sorting.
           While the raw p_value may be the value to use in most cases, it is
           not always true. For example, a string like "Gaëtan" could have
           "gaetan" as sort value.'''
        return self.getValue(obj)

    def getCatalogValue(self, obj, usage='search'):
        '''This method returns the index value that is currently stored in the
           catalog for this field on p_obj.'''
        if not self.indexed:
            raise Exception('Field %s: cannot retrieve catalog version of ' \
                            'unindexed field.' % self.name)
        return obj.getTool().getCatalogValue(obj, self.getIndexName(usage))

    def valueIsInRequest(self, o, req, name=None, layout='view'):
        '''Is there a value corresponding to this field in the request? p_name
           can be different from self.name (ie, if it is a field within another
           (List) field). In most cases, checking that this p_name is in the
           request is sufficient. But in some cases it may be more complex, ie
           for string multilingual fields.'''
        return (name or self.name) in req

    def getStorableValue(self, o, value, complete=False):
        '''p_value is a valid value initially computed through calling
           m_getRequestValue. So, it is a valid representation of the field
           value coming from the request. This method computes the value
           (potentially converted or manipulated in some other way) as can be
           stored in the database.'''
        # More precisely, m_getStorableValue computes a value that can be used
        # as input for m_store. But this latter can further transform it. For
        # example, a value produced by p_getStorableValue for a Ref field can be
        # a list of object IDs; method Ref.store will then convert it to a list
        # of objects and make cross-links between them and p_obj. If p_complete
        # is True, the value produced will be forced to be as close as possible
        # as the database value. In our Ref example, it will be a list of
        # objects (but cross-links will not be established).
        if self.isEmptyValue(o, value): return
        return value

    def getInputValue(self, inRequest, requestValue, value):
        '''Gets the value that must be filled in the "input" widget
           corresponding to this field.'''
        if inRequest:
            return requestValue or ''
        else:
            return value or ''

    def isReadonly(self, o):
        '''Returns True if, when this field is rendered on an edit layout as an
           input field, it must have attribute "readonly" set.'''
        return bool(self.getAttribute(o, 'readonly'))

    def setSlave(self, slaveField, masterValue):
        '''Sets p_slaveField as slave of this field. Normally, master/slave
           relationships are defined when a slave field is defined. At this time
           you specify parameters "master" and "masterValue" for this field and
           that's all. This method is used to add a master/slave relationship
           that was not initially foreseen.'''
        slaveField.master = self
        slaveField.masterValue = utils.initMasterValue(masterValue)
        if slaveField not in self.slaves:
            self.slaves.append(slaveField)
        # Master's init method may not have been called yet
        slaveField.masterName = getattr(self, 'name', None)

    def getMasterData(self):
        '''Gets the master of this field (and masterValue) or, recursively, of
           containing groups when relevant.'''
        if self.master: return self.master, self.masterValue
        group = self.getGroup('edit')
        if group: return group.getMasterData()

    def getMasterTag(self, layout):
        '''Generally, for a field, the name of the tag serving as master for
           driving slave fields is the name of the field itself. But sometimes
           it can be different (see Field sub-classes).'''
        return self.name

    def getTagCss(self, tagCss, layout):
        '''Gets the CSS class(es) that must apply to XHTML tag representing this
           field in the ui. p_tagCss may already give some base class(es).'''
        r = []
        if tagCss: r.append(tagCss)
        # Add a special class when this field is the slave of another field
        if self.master:
            css = 'slave*%s*' % self.master.getMasterTag(layout)
            if not callable(self.masterValue):
                css += '*'.join(self.masterValue)
            else:
                css += '+'
            r.insert(0, css)
        # Define a base CSS class when the field is a sub-field in a List
        if self.isInner(): r.append('no')
        return ' '.join(r)

    def getOnChange(self, o, layout, className=None):
        '''When this field is a master, this method computes the call to the
           Javascript function that will be called when its value changes (in
           order to update slaves).'''
        if not self.slaves: return ''
        # When the field is on a search screen, we need p_className
        name = "'%s'" % className if className else 'null'
        return "updateSlaves(this,null,'%s','%s',%s,true)" % \
               (o.url, layout, name)

    def isEmptyValue(self, o, value):
        '''Returns True if the p_value must be considered as an empty value.'''
        return value in self.nullValues

    def isCompleteValue(self, o, value):
        '''Returns True if the p_value must be considered as "complete". While,
           in most cases, a "complete" value simply means a "non empty" value
           (see m_isEmptyValue above), in some special cases it is more subtle.
           For example, a multilingual string value is not empty as soon as a
           value is given for some language but will not be considered as
           complete while a value is missing for some language. Another example:
           a Date with the "hour" part required will not be considered as empty
           if the "day, month, year" part is present but will not be considered
           as complete without the "hour, minute" part.'''
        return not self.isEmptyValue(o, value)

    def getCheckedInfo(self, req):
        '''Gets the status of checked elements from the p_req(uest)'''
        # It returns a tuple (ids, unchecked):
        # ----------------------------------------------------------------------
        #   "ids"     | is a list of object IDs;
        # "unchecked" | is True if these objects are unchecked, or False if
        #             | they are checked.
        # ----------------------------------------------------------------------
        ids = req.checkedIds.split(',') if req.checkedIds else []
        return ids, req.checkedSem == 'unchecked'

    def getSearchParams(self, req, layout):
        '''Encodes in a string all the params in the request that are require
           for re-triggering a search.'''
        if not req.search or (layout == 'cell'): return ''
        return ':'.join([req.get(key, '') for key in Field.searchParams])

    def getSearchResults(self, tool, searchParams):
        '''Execute the search whose parameters (p_searchParams) are returned by
           m_getSearchParams and return its results. Log the operation.'''
        # Get search parameters as local variables
        cmd = ', '.join(Field.searchParams)
        cmd += " = searchParams.split(':',%d)" % (len(Field.searchParams) - 1)
        exec(cmd)
        # Executing the search may take some time and potentially slow down
        # the system: log this action.
        tool.log(SEARCH_TRIGGER % (self.type, className, self.name, search))
        # (Re-)execute the search, but without restricting the number of results
        r = tool.search(className, searchName=search, sortBy=sortKey,
                        sortOrder=sortOrder, maxResults='NO_LIMIT',
                        filters=sutils.getDictFrom(filters))
        tool.log(SEARCH_DONE % len(r))
        return r

    def keepCheckedResults(self, req, objects):
        '''Among p_objects as retrieved via m_getSearchResults, keep only those
           being checked, according to m_getCheckedInfo.'''
        ids, unchecked = self.getCheckedInfo(req)
        i = len(objects) - 1
        # Remove, from search results, unchecked objects
        while i >= 0:
            if unchecked: remove = objects[i].id in ids
            else:         remove = objects[i].id not in ids
            if remove:
                del objects[i]
            i -= 1

    def validateValue(self, o, value):
        '''This method may be overridden by child classes and will be called at
           the right moment by m_validate defined below for triggering
           type-specific validation. p_value is never empty.'''
        return

    def securityCheck(self, o, value):
        '''This method performs some security checks on the p_value that
           represents user input.'''
        if not isinstance(value, str): return
        # Search Javascript code in the value (prevent XSS attacks)
        if '<script' in value:
            o.log(XSS_DETECTED, type='error')
            raise Exception(XSS_WARNING)

    def validate(self, o, value):
        '''Checks that p_value, coming from the request (p_o is being created or
           edited) and formatted through a call to m_getRequestValue defined
           above, is valid according to this type definition. If it is the case,
           None is returned. Else, a translated error message is returned.'''
        # If the value is required, check that a (complete) value is present
        if not self.isCompleteValue(o, value):
            if self.required and self.isClientVisible(o):
                # If the field is required, but not visible according to
                # master/slave relationships, we consider it not to be required.
                return o.translate('field_required')
            else:
                return
        # Perform security checks on p_value
        self.securityCheck(o, value)
        # Triggers the sub-class-specific validation for this value
        message = self.validateValue(o, value)
        if message: return message
        # Evaluate the custom validator if one has been specified
        value = self.getStorableValue(o, value)
        if self.validator and (type(self.validator) in self.validatorTypes):
            if type(self.validator) != self.validatorTypes[-1]:
                # It is a custom function: execute it
                try:
                    validValue = self.validator(o, value)
                    if isinstance(validValue, str) and validValue:
                        # Validation failed; and p_validValue contains an error
                        # message.
                        return validValue
                    else:
                        if not validValue:
                            return o.translate('field_invalid')
                except Exception as e:
                    return str(e)
                except:
                    return o.translate('field_invalid')
            else:
                # It is a regular expression
                if not self.validator.match(value):
                    return o.translate('field_invalid')

    def store(self, o, value):
        '''Stores the p_value (produced by m_getStorableValue) that complies to
           p_self type definition on p_obj.'''
        if self.persist: o.values[self.name] = value

    def storeFromAjax(self, o):
        '''Stores the new field value from an Ajax request, or do nothing if
           the action was canceled.'''
        req = o.req
        if req.cancel == 'True': return
        # Remember previous value if the field is historized
        isHistorized = self.getAttribute(o, 'historized')
        previousData = o.rememberPreviousData(self) if isHistorized else None
        # Validate the value
        value = req.fieldContent
        if self.validate(o, value):
            # Be minimalist: do nothing and return the previous value
            return
        # Store the new value on p_o
        self.store(o, self.getStorableValue(o, value))
        # Update the object history when relevant
        if isHistorized and previousData: o.historizeData(previousData)
        # Update o's last modification date
        from DateTime import DateTime
        o.modified = DateTime()
        o.reindex()

    def callMethod(self, o, method, cache=True):
        '''This method is used to call a p_method on p_o. p_method is part of
           this type definition (ie a default method, the method of a Computed
           field, a method used for showing or not a field...). Normally, those
           methods are called without any arg. But one may need, within the
           method, to access the related field. This method tries to call
           p_method with no arg *or* with the field arg.'''
        try:
            return o.H().methods.call(o, method, cache=cache)
        except TypeError as te:
            # Try a version of the method that would accept self as an
            # additional parameter. In this case, we do not try to cache the
            # value (we do not call utils.callMethod), because the value may be
            # different depending on the parameter.
            tb = utils.Traceback.get()
            try:
                return method(o, self)
            except Exception as e:
                o.log('method %s:\n%s' % (method.__name__, tb), type='error')
                # Raise the initial error
                raise te
        except Exception as e:
            o.log(utils.Traceback.get(), type='error')
            raise e

    def getAttribute(self, o, name, cache=True):
        '''Gets the value of attribute p_name on p_self, which can be a simple
           value or the result of a method call on p_o.'''
        r = getattr(self, name)
        return r if not callable(r) else self.callMethod(o, r, cache=cache)

    def getGroup(self, layout):
        '''Gets the group into wich this field is on p_layout'''
        # There may be...
        # (a) ... no group at all
        group = self.group
        if group is None: return
        # (b) ... the same group for all layouts
        elif isinstance(group, Group): return group
        # (c) a specific group for this p_layout
        elif layout in group: return group[layout]

    def getGroups(self):
        '''Returns groups as a list'''
        r = []
        if not self.group: return r
        if isinstance(self.group, Group):
            r.append(self.group)
        else: # A dict
            for group in self.group.values():
                if group and (group not in r):
                    r.append(group)
        return r

    def process(self, obj):
        '''This method is a general hook allowing a field to perform some
           processing after an URL on an object has been called, of the form
           <objUrl>/onProcess.'''
        return obj.goto(obj.absolute_url())

    def renderLabel(self, layoutType):
        '''Indicates if the existing label (if hasLabel is True) must be
           rendered by pxLabel. For example, if field is an action, the
           label will be rendered within the button, not by pxLabel.'''
        if not self.hasLabel: return
        # Label is always shown in search forms
        if layoutType == 'search': return True
        # If the field is within a "tabs" group, the label will already be
        # rendered in the corresponding tab. If the field is in a "grid" group,
        # the label is already rendered in a separate column.
        group = self.getGroup(layoutType)
        if group and (group.style in ('tabs', 'grid')): return
        return True

    def getSelectSize(self, isSearch, isMultiple):
        '''If this field must be rendered as a HTML "select" field, get the
           value of its "size" attribute. p_isSearch is True if the field is
           being rendered on a search screen, while p_isMultiple is True if
           several values must be selected.'''
        if not isMultiple: return 1
        prefix = 's' if isSearch else ''
        height = getattr(self, '%sheight' % prefix)
        if isinstance(height, int): return height
        # "height" can be defined as a string. In this case it is used to define
        # height via a attribute "style", not "size".
        return ''

    def getSelectStyle(self, isSearch, isMultiple):
        '''If this field must be rendered as a HTML "select" field, get the
           value of its "style" attribute. p_isSearch is True if the field is
           being rendered on a search screen, while p_isMultiple is True if
           several values must be selected.'''
        prefix = 's' if isSearch else ''
        # Compute CSS attributes
        res = []
        # Height
        height = getattr(self, '%sheight' % prefix)
        if isMultiple and isinstance(height, str):
            res.append('height: %s' % height)
            # If height is an integer value, it will be dumped in attribute
            # "size", not in CSS attribute "height".
        # Width
        width = getattr(self, '%swidth' % prefix)
        if isinstance(width, str):
            res.append('width: %s' % width)
            # If width is an integer value, it represents a number of chars
            # (usable for truncating the shown values), not a width for the CSS
            # attribute.
        return ';'.join(res)

    def getWidthInChars(self, isSearch):
        '''If attribute "width" contains an integer value, it contains the
           number of chars shown in this field (a kind of "logical" width). If
           it contains a string, we must convert the value expressed in px
           (or in another CSS-compliant unit), to a number of chars.'''
        prefix = isSearch and 's' or ''
        width = getattr(self, '%swidth' % prefix)
        if isinstance(width, int): return width
        if isinstance(width, str) and width.endswith('px'):
            return int(width[:-2]) / 5
        return 30 # Other units are currently not supported

    def getListHeader(self, ctx):
        '''When p_self is used as inner-field, within a table-like rendered
           container field, this method returns the content of the header row
           corresponding to this inner field.'''
        return ctx['_']('label', field=self)
# ------------------------------------------------------------------------------
