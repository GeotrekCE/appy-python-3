'''Initiators for searches whose results are shown in popups'''

# ~license~

# Abstract base class for any initiator  - - - - - - - - - - - - - - - - - - - -
class Initiator:
    '''When a search is rendered in a popup, the "initiator", in the main page,
       can be:
       * (a) some object, in view or edit mode, displaying a given Ref field
             for which the popup is used to select one or more objects to link;
       * (b) some class for which we must create an instance from a template;
             the popup is used to select such a template object.

       This class is the abstract class for 2 concrete initiator classes:
       RefInitiator (for case a) and TemplateInitiator (for case b).
    '''

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class RefInitiator(Initiator):
    def __init__(self, o, field, fieldName, mode):
        # The initiator object
        self.o = o
        # The initiator field
        self.field = field
        # As usual, the field name can be different from field.name if it is a
        # sub-field within an outer field.
        self.fieldName = fieldName
        # The mode can be:
        # - "repl" if the objects selected in the popup will replace already
        #          tied objects;
        # - "add"  if those objects will be added to the already tied ones.
        self.mode = mode
        # "hook" is the ID of the initiator field's XHTML tag
        self.hook = '%s_%s' % (o.id, fieldName)
        # The root Ajax hook ID in the popup
        self.popupHook = '%s_popup' % self.hook

    def showCheckboxes(self):
        '''We must show object checkboxes if self.field is multivalued: indeed,
           in this case, several objects can be selected in the popup.'''
        return self.field.isMultiValued()

    def jsSelectOne(self, q, cbId):
        '''Generates the Javascript code to execute when a single object is
           selected in the popup.'''
        return 'onSelectObject(%s,%s,%s)' % \
               (q(cbId), q(self.hook), q(self.o.url))

    def jsSelectMany(self, q, sortKey, sortOrder, filters):
        '''Generates the Javascript code to execute when several objects are
           selected in the popup.'''
        return 'onSelectObjects(%s,%s,%s,%s,null,%s,%s,%s)' % \
          (q(self.popupHook), q(self.hook), q(self.o.url), q(self.mode), \
           q(sortKey), q(sortOrder), q(filters))

    def getAjaxParams(self):
        '''Get initiator-specific parameters for retriggering the Ajax
           request for refreshing objects in the popup.'''
        return

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class TemplateInitiator(Initiator):
    MANY_ERROR = 'Cannot select several objects from a template initiator.'

    def __init__(self, className, formName, insert, sourceField):
        # The class from which we must create an instance based on a template
        # that we will choose in the popup. Indeed, the instance to create may
        # be from a different class that the instances shown in the popup.
        self.className = className
        # The name of the form that will be submitted for creating the object
        # once a template will have been selected in the popup.
        self.formName = formName
        # The root Ajax hook ID in the popup
        self.popupHook = '%s_popup' % className
        # If the object to create must be inserted at a given place in a Ref
        # field, this can be specified in p_insert.
        self.insert = insert or ''
        # The source field
        self.sourceField = sourceField

    def showCheckboxes(self):
        '''We must hide object checkboxes: only one template object can be
           selected.'''
        return

    def jsSelectOne(self, q, cbId):
        '''Generates the Javascript code to execute when a single object is
           selected in the popup.'''
        return 'onSelectTemplateObject(%s,%s,%s)' % \
               (q(cbId), q(self.formName), q(self.insert))

    def jsSelectMany(self, q, sortKey, sortOrder, filters):
        raise Exception(self.MANY_ERROR)

    def getAjaxParams(self):
        r = {'fromClass': self.className, 'formName': self.formName}
        if self.insert:
            r['insert'] = self.insert
        if self.sourceField:
            r['sourceField'] = self.sourceField
        return r
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
