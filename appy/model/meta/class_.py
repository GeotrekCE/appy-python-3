'''Meta-class for a Appy class'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import collections
import persistent
from persistent.mapping import PersistentMapping


from appy.px import Px
from appy.model import Model
import appy.model.meta.class_
from appy.model.meta import Meta
from appy.model.base import Base
from appy.model.page import Page
from appy.model.user import User
from appy.model.tool import Tool
from appy.model.group import Group
from appy.model.fields import Field
from appy.model.workflow import Role
from appy.model.utils import Object as O
from appy.model.fields.phase import Phase
from appy.model.fields.string import String
from appy.model.translation import Translation
from appy.model.workflow.history import History
from appy.model.workflow.localRoles import LocalRoles
from appy.model.fields.phase import Page as FieldPage

# Errors - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
UNALLOWED_FIELD_NAME = 'You have defined a field or search named "%s" on ' \
  'class "%s". This name is not allowed.'
CREATOR_LOCAL_ROLE = '%s: local role "%s" cannot be used as creator.'
DUPLICATE_SEARCH_NAME = '%s: duplicate search "%s".'
SEARCH_FIELD_HOMONYM = '%s: "%s" is both used as search and field name, this ' \
  'is not allowed.'
CUSTOM_ID_NOT_STRING = 'The custom ID produced by method "generaeId" must be ' \
  'a string.'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Class(Meta):
    '''Represents an Appy class'''

    # Attributes added on Appy classes
    attributes = {'fields': Field}

    # Reserved attribute names unallowed for naming a Field or a Search
    unallowedNames = {
      'id':         None, # The object's identifier
      'iid':        None, # The object's integer identifier
      'values':     None, # Dict storing all field values
      'container':  None, # Info about the objet's container
      'history':    None, # The object's history
      'localRoles': None, # The object's local roles
      'locks':      None, # Locks on object pages
    }

    @classmethod
    def unallowedName(class_, name):
        '''Return True if p_name can't be used for naming a Field or Search'''
        # A name is unallowed if
        # (a) it corresponds to some standard attribute added at object creation
        #     on any Appy object (but not declared at the class level);
        # (b) it corresponds to an attribute or method defined in class Base.
        return (name in class_.unallowedNames) or (name in Base.__dict__)

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Model-construction-time methods
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # The following set of methods allow to build the model when making an app
    # or when starting the server.
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def __init__(self, class_, isBase=False, appOnly=False):
        Meta.__init__(self, class_, appOnly)
        # p_class_ may be of 3 types:
        # ----------------------------------------------------------------------
        # "base" | A class from the base Appy model (from appy.model) that has
        #        | not been overridden by an app's class.
        # ----------------------------------------------------------------------
        # "app"  | An original class from the app, that does not exist in the
        #        | base model.
        # ----------------------------------------------------------------------
        # "over" | A class defined in the app but that overrides a class defined
        #        | in the base Appy model.
        # ----------------------------------------------------------------------
        self.type = 'base' if isBase else 'app'
        # Create the concrete class from which instances will be created.
        # Indeed, In order to bring all Appy functionalities to p_class_, we
        # need to create a new class inheriting from:
        # ----------------------------------------------------------------------
        #   p_class_  | The class defined by the developer or being part of the
        #             | base Appy model.
        # ----------------------------------------------------------------------
        #    Base*    | Class appy.model.base.Base, the base class for any Appy
        #             | class, or one if its sub-classes, depending on p_class_
        #             | name. For example, if the user defines a class named
        #             | "Invoice", it will inherit from Base (=a class of type
        #             | "app"). If the user defines a class named "User", it
        #             | will inherit from class appy.model.user.User (= a class
        #             | of type "over"): using the name of a base class from
        #             | package appy.model implicitly means that the developer
        #             | wants to extend this class.
        #             |
        #             | Note that for not-overridden classes from appy.model (=
        #             | classes of type "base"), there is no base class: the
        #             | class is already a base class.
        # ----------------------------------------------------------------------
        #  Persistent | Class persistent.Persistent allows to store instances in
        #             | the database (ZODB).
        # ----------------------------------------------------------------------
        # Creating the concrete class is not necessary when p_self.appOnly is
        # True.
        if not appOnly:
            # The name of the generated class (tribute to appy.gen)
            genName = 'Gen_%s' % self.name
            if self.type == 'base':
                # The class must only inherit from p_class_ and Persistent
                exec('class %s(class_, persistent.Persistent): pass' % genName)
            else:
                # It must also inherit from a base class or one of its
                # sub-classes.
                base = self.getBaseClass()
                if base != 'Base':
                    # This is an "over" class
                    self.type = 'over'
                exec('class %s(class_, %s, persistent.Persistent): pass' % \
                     (genName, base))
            # This concrete class will have a full name being
            #                appy.model.meta.class_.<genName>
            exec('self.concrete = %s' % genName)
            # Add the class in the namespace of the current package
            # (appy.model.meta.class_). Else, pickle, used by the ZODB to store
            # instances of this class, will not find it.
            setattr(appy.model.meta.class_, genName, self.concrete)
        else:
            self.type = (self.name in Model.baseClasses) and 'over' or 'app'
        # Fields are grouped into pages, themselves grouped into "phases"
        self.phases = collections.OrderedDict()
        # Read fields and static searches
        self.readFields()
        self.readSearches()
        # The class will be linked to a workflow (later, by the loader)
        self.workflow = None
        # Call the "update" method if present: it allows developers to modify
        # this class. One of the most frequent updates will be to update field
        # "title".
        if hasattr(self.python, 'update'): self.python.update(self)

    def getBaseClass(self):
        '''Returns the name of the class being p_self's base class'''
        name = self.name
        return name if name in Model.baseClasses else 'Base'

    def injectProperties(self):
        '''Injects, on p_self.concrete, a property for every field defined on
           this class, in order to get and set its value.'''
        # Other techniques could have been implemented for injecting such
        # virtual attributes, like overriding __getattribute__ and __setattr__,
        # but this should be avoided in conjunction with ZODB and pickle.
        class_ = self.concrete
        # Inject one property for every field
        for name, field in self.fields.items():
            # To get a field value is done via method Field::getValue
            getter = lambda self, field=field: field.getValue(self)    
            # To set a value is done via method Field::store
            setter = lambda self, v, field=field: field.store(self, v)
            setattr(class_, name, property(getter, setter))

    def getFieldClasses(self, class_):
        '''Returns, on p_class_ and its base classes, the list of classes where
           fields may be defined.'''
        # Add p_class_ in itself
        r = [class_]
        # Scan now p_class_'s base class
        if (class_ != self.python) or (self.type == 'base'):
            base = class_.__bases__[0]
        else:
            base = eval(self.getBaseClass())
        if base.__name__ != 'object':
            r  = self.getFieldClasses(base) + r
        return r

    def readPage(self, page):
        '''While browsing a field, a p_page has been encountered. Add it to
           self.phases if not already done.'''
        # Create the phase when appropriate
        name = page.phase
        if name not in self.phases:
            phase = self.phases[name] = Phase(name)
        else:
            phase = self.phases[name]
        # Add the page into it
        if page.name not in phase.pages:
            phase.pages[page.name] = page

    def readFields(self):
        '''Create attribute "fields" as an ordered dict storing all fields
           defined on this class and parent classes.'''
        class_ = self.python
        r = collections.OrderedDict()
        Err = Model.Error
        # Find field in p_class_ and base classes
        for aClass in self.getFieldClasses(class_):
            for name, field in aClass.__dict__.items():
                if name.startswith('__'): continue
                if isinstance(field, Field):
                    # Ensure the field name is acceptable
                    self.checkAttributeName(name)
                    if not aClass.__module__.startswith('appy.model') and \
                       (Class.unallowedName(name)):
                        raise Err(UNALLOWED_FIELD_NAME % (name, self.name))
                    # A field was found.
                    # ~~~
                    # Special field "title" must be duplicated. Else, all app
                    # classes will get the modifications that the developer can
                    # apply to it via "update" methods.
                    if name == 'title':
                        field = String(**Base.titleAttributes)
                    # Late-initialize it.
                    field.init(self, name)
                    r[name] = field
                    self.readPage(field.page)
        self.fields = r

    def readSearches(self):
        '''Create attribute "searches" as an ordered dict storing all static
           searches defined on this class.'''
        class_ = self.python
        r = collections.OrderedDict()
        Err = Model.Error
        if hasattr(class_, 'searches'):
            for search in class_.searches:
                name = search.name
                # Ensure the search name is acceptable
                if Class.unallowedName(name):
                    raise Err(UNALLOWED_FIELD_NAME % (name, self.name))
                # Ensure the search name is unique, also among fields
                if name in r:
                    raise Err(DUPLICATE_SEARCH_NAME % (self.name, name))
                if name in self.fields:
                    raise Err(SEARCH_FIELD_HOMONYM % (self.name, name))
                # Ensure the field name is acceptable
                self.checkAttributeName(name)
                search.init(self)
                r[search.name] = search
        self.searches = r

    def getCreators(self):
        '''Gets the roles allowed to create instances of this class'''
        r = []
        class_ = self.python
        # The info can be defined in a static attribute named "creators"
        creators = getattr(self.python, 'creators', None)
        if not creators: return r
        # Athough a method can be specified in "creators", we can't execute it,
        # so we care about creators only if defined "statically", as a list.
        if not isinstance(creators, list): return r
        # Browse roles
        for creator in creators:
            if isinstance(creator, Role):
                if creator.local:
                    error = CREATOR_LOCAL_ROLE % (self.name,creator.name)
                    raise Model.Error(error)
                r.append(creator)
            else:
                r.append(Role(creator))
        return r

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Instance-creation method
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def new(self, iid, id, login, initialComment=None, initialState=None):
        '''Create and return an instance of the concrete class'''
        o = self.concrete()
        # Set the IDs on the object
        o.iid = iid
        o.id = id
        # Create the object's history
        o.history = History(o)
        # Create a dict storing the object's local roles, and grant role 'Owner'
        # to the user behind this object creation, whose p_login is given.
        o.localRoles = LocalRoles()
        o.localRoles.add(login, 'Owner')
        # Create the dict "values" that will store field values, and set the
        # first values in it.
        o.values = PersistentMapping() # ~{s_fieldName: fieldValue}~
        # Initialise object's history by triggering the _init_ transition
        tr = self.workflow.initialTransition
        state = initialState or tr.states[1]
        tr.trigger(o, initialComment, doSay=False, forceTarget=state)
        return o

    def generateId(self, o):
        '''A method named "generateId" may exist on p_self.python, allowing the
           app's developer to choose itself an ID for the p_o(bject) under
           creation. This method accepts p_o as unique arg and must return the
           ID as a string, or None.'''
        # Return None if no such method is defined on p_self.python
        if not hasattr(self.python, 'generateId'): return
        r = self.python.generateId(o)
        # If the method return None, a standard ID will be generated by Appy
        if r is None: return
        # Raise an error if the returned ID is not a string
        if not isinstance(r, str):
            raise Exception(CUSTOM_ID_NOT_STRING)
        return r

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Run-time methods
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # The following set of methods allow to compute, at run-time,
    # class-dependent elements.
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def getListCss(self, layout='view'):
        '''Returns the CSS class(es) to apply when displaying a list (=a table)
           containing instances of this class.'''
        css = getattr(self.python, 'listCss', None)
        if css: return css
        return 'list' if layout == 'cell' else 'list compact'

    def getListTitle(self, o):
        '''Gets p_o's title as it must appear within lists of objects'''
        if hasattr(self.python, 'listTitle'):
            r = self.python.listTitle(o, nav)
        else:
            r = o.getShownValue('title')
        return r

    def produceUniqueLinks(self):
        '''When producing links ("a" tags) to instances of this class, must
           these links always be unique ?'''
        return hasattr(self.python, 'uniqueLinks') and self.python.uniqueLinks

    def showTransitions(self, o, layout):
        '''When displaying p_self's instance p_o, must we show, on p_layout, the
           buttons/icons for triggering transitions ?'''
        # Never show transitions on edit pages
        if layout == 'edit': return
        # Use the default value if self does not specify it
        if not hasattr(self.python, 'showTransitions'): return layout == 'view'
        r = self.python
        if callable(r): r = r(o)
        # This value can be a single value or a tuple/list of values
        return layout == r if isinstance(r, str) else layout in r

    def getCssFor(self, o, elem):
        '''Gets the name of the CSS class to use for styling some p_elem on
           instance p_o. If this class does not define a dict or method named
           "styles", the defaut CSS class to use will be named p_elem.'''
        styles = getattr(self.python, 'styles', None)
        if not styles: return elem
        elif callable(styles): # A method
            return styles(o, elem) or elem
        else: # A dict or a appy.Object instance
            return styles.get(elem) or elem

    def getCreateVia(self, tool):
        '''How to create instances of this class ? The answer can be: via a
           web form ("form"), via a form pre-filled from a template (a Search
           instance) or programmatically only (None).'''
        # By default, instances are created via an empty web form
        r = getattr(self.python, 'createVia', 'form')
        return r if not callable(r) else r(tool)

    def getCreateLink(self, tool, create, formName,
                      sourceField=None, insert=None):
        '''When instances of p_self must be created from a template (from the
           UI), this method returns the link allowing to query such templates
           from a popup.'''
        r = '%s/query?class=%s&search=fromSearch&popup=1&fromClass=%s' \
            '&formName=%s' % (tool.url, create.class_.__name__, self.name,
                              formName)
        # When object creation occurs via a Ref field, its coordinates are given
        # in p_sourceField as a string: "sourceObjectId:fieldName".
        if sourceField: r += '&sourceField=%s' % sourceField
        # p_insert is filled when the object must be inserted at a given place
        if insert: r += '&insert=%s' % insert
        return r

    def getCreateExclude(self, o):
        '''When an instance of this class must be created from a template
           object, what fields must not be copied from the template ?'''
        r = getattr(self.python, 'createExclude', ())
        return r(o) if callable(r) else r

    def getConfirmPopupWidth(self):
        '''Gets the width (in pixels, as an integer value), of the confirmation
           popup possibly shown when creating or editing p_self's instances.'''
        return getattr(self.python, 'confirmPopup', 500)

    def maySearch(self, tool, layout):
        '''May the user search among instances of this class ?'''
        # When editing a form, one should avoid annoying the user with this
        if layout == 'edit': return
        return self.python.maySearch(tool) \
               if hasattr(self.python, 'maySearch') else True

    def getSearchAdvanced(self, tool):
        '''Gets the "advanced" search defined on this class if present'''
        # This Search instance, when present, is used to define search
        # parameters for this class' special searches: advanced, all and live
        # searches.
        r = getattr(self.python, 'searchAdvanced', None)
        return r if not callable(r) else r(tool)

    def maySearchAdvanced(self, tool):
        '''Is advanced search enabled for this class ?'''
        # Get the "advanced" search
        advanced = self.getSearchAdvanced(tool)
        # By default, advanced search is enabled
        if not advanced: return True
        # Evaluate attribute "show" on this Search instance representing the
        # advanced search.
        return advanced.isShowable(tool)

    def mayNavigate(self, o):
        '''May the user see the navigation panel linked to p_o ?'''
        return o.mayNavigate() if hasattr(self.python, 'mayNavigate') else True

    def isIndexable(self):
        '''Is p_self "indexable" ? In other words: do we need to have a Catalog
           storing index values for instances of this class ?'''
        return getattr(self.concrete, 'indexable', True)

    def getListPods(self):
        '''Finds, among p_self' fields, those being Pod fields showable on
           search results.'''
        return [f for f in self.fields.values() \
                if (f.type == 'Pod') and (f.show == 'query')]

    def getDynamicSearches(self, tool):
        '''Gets the dynamic searches potentially defined on this class'''
        # Stop here if no dynamic search is defined
        if not hasattr(self.python, 'getDynamicSearches'): return
        # Create the cache if it does not exist yet
        handler = tool.H()
        dyn = handler.cache.dynamicSearches
        if dyn is None:
            dyn = handler.cache.dynamicSearches = {}
        # Get the cached searches when present; compute and cache them else
        name = self.name
        if name in dyn:
            r = dyn[name]
        else:
            r = dyn[name] = self.python.getDynamicSearches(tool)
            for search in r: search.init(self)
        return r

    def getGroupedSearches(self, tool, ctx):
        '''Returns an object with 2 attributes:
           * "searches" stores the searches defined for this class, as instances
             of the run-time-specific class appy.model.searches.UiSearch;
           * "default" stores the search being the default one.
        '''
        searches = []
        default = None # Also retrieve the default one here
        groups = {} # The already encountered groups
        page = FieldPage('searches') # A dummy page required by class UiGroup
        # Get the statically defined searches from class's "searches" attribute
        for search in self.searches.values():
            # Ignore search that can't be shown
            if not search.isShowable(tool): continue
            searches.append(search)
        # Get the dynamically computed searches
        dyn = self.getDynamicSearches(tool)
        if dyn: searches += dyn
        # Return the grouped list of UiSearch instances
        r = []
        for search in searches:
            # Create the search descriptor
            ui = search.ui(tool, ctx)
            if not search.group:
                # Insert the search at the highest level, not in any group
                r.append(ui)
            else:
                uiGroup = search.group.insertInto(r, groups, page, self.name,
                                                  content='searches')
                uiGroup.addElement(ui)
            # Is this search the default search?
            if search.default: default = ui
        return O(all=r, default=default)

    def getResultModes(self):
        '''Gets the search result modes for this class'''
        return getattr(self.python, 'resultModes', None)

    def getResultsTop(self, tool, search, mode):
        '''Returns something to display on the results page just before
           displaying search results.'''
        method = getattr(self.python, 'getResultsTop', None)
        return method(tool, search, mode) if method else None

    def getResultCss(self, layout='view'):
        '''Gets the CSS class(es) to apply when displaying a table containing
           p_self's instances.'''
        r = getattr(self.python, 'listCss', None)
        if not r:
            r = 'list' if layout == 'cell' else 'list compact'
        return r

    def getTitleMode(self):
        '''Gets the "title mode" for instances of this class'''
        # Consult homonym method on class appy.model.searches.UiSearch
        return getattr(self.python, 'titleMode', None)

    def hasSubTitle(self):
        '''Does p_self define a method "getSubTitle"?'''
        # This method allows to fill a zone under the title of p_self's
        # instances when rendered in a table.
        return hasattr(self.python, 'getSubTitle')

    def getPortletBottom(self, tool):
        '''Is there a custom zone to display at the bottom of the portlet zone
           for this class ?'''
        if not hasattr(self.python, 'getPortletBottom'): return
        return self.python.getPortletBottom(tool)

    def getListColumns(self, tool):
        '''Return the list of columns to display when rendering p_self's
           instances in a table.'''
        r = getattr(self.python, 'listColumns', ('title',))
        return r if not callable(r) else r(tool)

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # PXs
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    # Icon for creating instances of this class from a template
    pxAddFrom = Px('''
     <a target="appyIFrame" id=":addFormName + '_from'"
        href=":class_.getCreateLink(tool, create, addFormName, sourceField)">
      <input var="css='Small' if fromRef else 'Icon';
                  label=_('object_add_from')"
         type="button" value=":label if fromRef else ''" 
         title=":label" class=":'button%s button' % css"
         onclick="openPopup('iframePopup')" style=":url('addFrom', bg=True)"/>
     </a>''')
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
