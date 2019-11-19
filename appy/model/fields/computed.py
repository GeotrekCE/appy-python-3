# ~license~
# ------------------------------------------------------------------------------
from appy.px import Px
from appy.model.fields import Field, Show
from appy.ui.layout import Layouts, Layout
from appy.model.searches import Search, UiSearch

# Error messages ---------------------------------------------------------------
UNFREEZABLE = 'This field is unfreezable.'
WRONG_METHOD = 'Wrong value "%s". Param "method" must contain a method or a PX.'

# ------------------------------------------------------------------------------
class Computed(Field):
    '''Useful for computing a custom field via a Python method'''

    class Layouts(Layouts):
        '''Computed-specific layouts'''
        # Layouts for fields in a grid group, with description
        gd = Layouts('f-drvl')
        # Idem, but with a help icon
        gdh = Layouts('f-dhrvl')

    view = cell = edit = Px('''<x if="field.plainText">:value</x><x
      if="not field.plainText">::value</x>''')

    search = Px('''
     <input type="text" name=":widgetName" maxlength=":field.maxChars"
            size=":field.width" value=":field.sdefault"/>''')

    def __init__(self, multiplicity=(0,1), default=None, defaultOnEdit=None,
      show=None, page='main', group=None, layouts=None, move=0, indexed=False,
      mustIndex=True, indexValue=None, searchable=False, readPermission='read',
      writePermission='write', width=None, height=None, maxChars=None,
      colspan=1, method=None, formatMethod=None, plainText=False, master=None,
      masterValue=None, focus=False, historized=False, mapping=None,
      generateLabel=None, label=None, sdefault='', scolspan=1, swidth=None,
      sheight=None, context=None, view=None, cell=None, edit=None, xml=None,
      translations=None, unfreezable=False, validable=False):
        # The Python method used for computing the field value, or a PX
        self.method = method
        # A specific method for producing the formatted value of this field.
        # This way, if, for example, the value is a DateTime instance which is
        # indexed, you can specify in m_formatMethod the way to format it in
        # the user interface while m_method computes the value stored in the
        # catalog.
        self.formatMethod = formatMethod
        if isinstance(self.method, str):
            # A legacy macro identifier. Raise an exception
            raise Exception(WRONG_METHOD % self.method)
        # Does field computation produce plain text or XHTML?
        self.plainText = plainText
        if isinstance(method, Px):
            # When field computation is done with a PX, the result is XHTML
            self.plainText = False
        # Determine default value for "show"
        if show is None:
            # XHTML content in a Computed field generally corresponds to some
            # custom XHTML widget. This is why, by default, we do not render it
            # in the xml layout.
            show = Show.E_ if self.plainText else Show.TR
        # If method is a PX, its context can be given in p_context
        self.context = context
        Field.__init__(self, None, multiplicity, default, defaultOnEdit, show,
          page, group, layouts, move, indexed, mustIndex, indexValue,
          searchable, readPermission, writePermission, width, height, None,
          colspan, master, masterValue, focus, historized, mapping,
          generateLabel, label, sdefault, scolspan, swidth, sheight, False,
          False, view, cell, edit, xml, translations)
        # When a custom widget is built from a computed field, its values are
        # potentially editable and validable, so "validable" must be True.
        self.validable = validable
        # One classic use case for a Computed field is to build a custom widget.
        # In this case, self.method stores a PX or method that produces, on
        # view or edit, the custom widget. Logically, you will need to store a
        # custom data structure on obj.o, in an attribute named according to
        # this field, ie self.name. Typically, you will set or update a value
        # for this attribute in obj.onEdit, by getting, on the obj.request
        # object, values encoded by the user in your custom widget (edit mode).
        # This "custom widget" use case is incompatible with "freezing". Indeed,
        # freezing a Computed field implies storing the computed value at
        # obj.o.[self.name] instead of recomputing it as usual. So if you want
        # to build a custom widget, specify the field as being unfreezable.
        self.unfreezable = unfreezable
        # Set a filter PX if this field is indexed with a TextIndex
        if self.indexed and (self.indexed == 'TextIndex'):
            self.filterPx = 'pxFilterText'

    def renderPx(self, o, px):
        '''Renders the p_px and returns the result'''
        traversal = o.traversal
        context = traversal.context or traversal.createContext()
        # Complete the context when relevant
        custom = self.context
        custom = custom if not callable(custom) else custom(o)
        if custom:
            context.update(custom)
        return px(context)

    def renderSearch(self, o, search):
        '''Executes the p_search and return the result'''
        traversal = o.traversal
        context = traversal.context or traversal.createContext()
        uiSearch = search.ui(o, context)
        req = o.req
        # This will allow the UI to find this search
        req.search = '%s,%s,view' % (o.id, self.name)
        req.className = o.class_.name
        r = uiSearch.pxResult(context)
        # Reinitialise the context correctly
        context.field = self
        return r

    def getSearch(self, o):
        '''Gets the Search instance possibly linked to this Computed field'''
        method = self.method
        if not method: return
        if isinstance(method, Search): return method
        # Maybe a dynamically-computed Search ?
        r = self.callMethod(o, method, cache=False)
        if isinstance(r, Search): return r

    def getValue(self, obj, name=None, layout=None, forceCompute=False):
        '''Computes the field value on p_obj or get it from the database if it
           has been frozen.'''
        # Is there a database value ?
        if not self.unfreezable and not forceCompute:
            res = obj.__dict__.get(self.name, None)
            if res is not None: return res
        # Compute the value
        meth = self.method
        if not meth: return
        if isinstance(meth, Px): return self.renderPx(obj, meth)
        elif isinstance(meth, Search): return self.renderSearch(obj, meth)
        else:
            # self.method is a method that will return the field value
            res = self.callMethod(obj, meth, cache=False)
            # The field value can be a dynamically computed PX or Search
            if isinstance(res, Px): return self.renderPx(obj, res)
            elif isinstance(res, Search): return self.renderSearch(obj, res)
            return res

    def getFormattedValue(self, obj, value, layoutType='view',
                          showChanges=False, language=None):
        if self.formatMethod:
            res = self.formatMethod(obj, value)
        else:
            res = value
        if not isinstance(res, str): res = str(res)
        return res

    # If you build a custom widget with a Computed field, Appy can't tell if the
    # value in your widget is complete or not. So it returns True by default.
    # It is up to you, in method obj.validate, to perform a complete validation,
    # including verifying if there is a value if your field is required.
    def isCompleteValue(self, obj, value): return True

    def freeze(self, obj, value=None):
        '''Normally, no field value is stored for a Computed field: the value is
           computed on-the-fly by self.method. But if you freeze it, a value is
           stored: either p_value if not None, or the result of calling
           self.method else. Once a Computed field value has been frozen,
           everytime its value will be requested, the frozen value will be
           returned and self.method will not be called anymore. Note that the
           frozen value can be unfrozen (see method below).'''
        if self.unfreezable: raise Exception(UNFREEZABLE)
        obj = obj.o
        # Compute for the last time the field value if p_value is None
        if value is None: value = self.getValue(obj, forceCompute=True)
        # Freeze the given or computed value (if not None) in the database
        if value is not None: setattr(obj, self.name, value)

    def unfreeze(self, obj):
        '''Removes the database value that was frozen for this field on p_obj'''
        if self.unfreezable: raise Exception(UNFREEZABLE)
        obj = obj.o
        if hasattr(obj.aq_base, self.name): delattr(obj, self.name)
# ------------------------------------------------------------------------------
