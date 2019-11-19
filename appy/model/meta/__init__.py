'''The Appy meta-model contains meta-classes representing classes of Appy
   classes: essentially, Appy classes and workflows.'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.model import Model

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
ATTR = 'Attribute "%s" in %s "%s"'
UNDERSCORED_NAME = '%s contains at least one underscore, which is not ' \
  'allowed. Please consider naming your fields, searches, states and ' \
  'transitions in camelCase style, the first letter being a lowercase ' \
  'letter. For example: "myField", instead of "my_field". Furthermore, there ' \
  'is no need to define "private" fields starting with an underscore.' % ATTR
UPPERSTART_NAME = '%s must start with a lowercase letter. This rule holds ' \
  'for any field, search, state or transition.' % ATTR
LOWERSTART_NAME = 'Name of %s "%s" must start with an uppercase letter.'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Meta:
    '''Abstract base class representing a Appy class or workflow'''

    def __init__(self, class_, appOnly):
        # p_class_ is the Python class found in the Appy app. Its full name is
        #              <Python file name>.py.<class name>
        self.python = class_
        # Make this link bidirectional
        class_.meta = self
        # Its name. Ensure it is valid.
        self.name = self.checkClassName(class_)
        # If p_appOnly is True, stuff related to the Appy base model must not be
        # defined on this meta-class. This minimalist mode is in use when
        # loading the model for creating or updating translation files.
        self.appOnly = appOnly

    def asString(self):
        r = '<class %s.%s' % (self.__module__, self.name)
        for attribute in self.attributes.keys():
            r += '\n %s:' % attribute
            for name, field in getattr(self, attribute).items():
                r += '\n  %s : %s' % (name, str(field))
        return r

    def checkClassName(self, class_):
        '''A class or workflow must start with an uppercase letter'''
        name = class_.__name__
        if name[0].islower():
            type = self.__class__.__name__.lower()
            raise Model.Error(LOWERSTART_NAME % (type, name))
        return name

    def checkAttributeName(self, name):
        '''Checks if p_name is valid for being used as attribute (field, search,
           state or transition) for this class or workflow.'''
        # Underscores are not allowed
        if '_' in name:
            type = self.__class__.__name__.lower()
            raise Model.Error(UNDERSCORED_NAME % (name, type, self.name))
        # The name must start with a lowercase char
        if not name[0].islower():
            type = self.__class__.__name__.lower()
            raise Model.Error(UPPERSTART_NAME % (name, type, self.name))

    def __repr__(self): return '<class %s.%s>' % (self.__module__, self.name)
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
