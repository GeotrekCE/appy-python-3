'''Loads and returns a Model instance'''

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import sys, inspect, pathlib

from appy.tr import po
from appy.model import Model
from appy.ui.layout import Layouts
from appy.model.workflow import standard
from appy.model.meta.class_ import Class
from appy.model.utils import importModule
from appy.model.workflow.state import State
from appy.model.meta.workflow import Workflow
from appy.all import Field, String, Computed, Page

# Errors - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
NO_SEARCH = "Note that Appy classes and workflows are not searched within " \
  "your app's __init__.py file, nor within sub-modules."
NO_PYTHON_FILE = 'No Python file was found in your app @%%s. %s' % NO_SEARCH
NO_APPY_CLASS = 'No Appy class was found in your app @%%s. %s' % NO_SEARCH
DUPLICATE_NAME = '2 or more Appy classes and/or workflows named "%s" have ' \
  'been found in your model. This is not allowed, even if they are in ' \
  'separate Python modules.'
UNDERSCORED_NAME = 'Class or workflow "%s" contains at least one underscore, ' \
  'which is not allowed. Please consider naming your classes and workflows ' \
  'in CamelCase style, the first letter being an uppercase letter. For ' \
  'example: "MyClass", instead of "my_class".'
LOADED_RUNTIME = 'Model loaded (base+app) - %d classes - %d workflows - ' \
  '%s labels.'
LOADED_MAKETIME = 'Model loaded (app) - %d class(es) - %d workflow(s).'
NOT_WORKFLOW = '"%s", defined as workflow for class "%s", is not a workflow ' \
  'class.'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Loader:
    '''Reads the application model, completes it with the base Appy model, and
       returns a appy.model.Model instance.'''

    def __init__(self, config, appConfig, logger, appOnly):
        # The model config (a appy.model.Config instance)
        self.config = config
        # The root app config
        self.appConfig = appConfig
        # A logger. If None, output will go to stdout.
        self.logger = logger
        # If p_appOnly is True, we will not load the Appy base model: only the
        # classes and workflows defined in the app will be loaded. This
        # minimalist model loading is performed by the appy.tr.updater.Updater
        # (called by <appFolder>/bin/make), for creating or updating the app's
        # i18n files.
        self.appOnly = appOnly

    def log(self, message):
        '''Logs p_message to p_self.logger if it exists, to stdout else'''
        if self.logger:
            self.logger.info(message)
        else:
            print(message)

    def determineMetaClass(self, class_):
        '''If p_class_ is:
           * a Appy class, this method returns meta-class Class;
           * a Appy workflow, this method returns meta-class Wokflow;
           * none of it, this method returns None.
        '''
        # If p_class_ declares at least one static attribute being an instance of
        # appy.fields.Field, it will be considered a Appy class. If it declares
        # at least one static attribute being an instance of
        # appy.fields.workflow.State, it will be considered a Appy workflow.
        for attr in class_.__dict__.values():
            if isinstance(attr, Field): return Class
            elif isinstance(attr, State): return Workflow

    def complete(self, model):
        '''After the model loader has loaded the app's model (m_run), Appy base
           classes (see Model.baseClasses) may have been redefined or not at the
           app level. In order to have a complete model in self.classes, we must
           add all base classes not being redefined at the app level.

           We must also load standard workflows into self.workflows.
        '''
        # Complete self.classes
        for name in Model.baseClasses:
            if name not in model.classes:
                # Import the corresponding base class
                exec('from appy.model.%s import %s' % (name.lower(), name))
                pythonClass = eval(name)
                model.classes[name] = Class(pythonClass, isBase=True)
        # Complete self.workflows
        for name in Model.baseWorkflows:
            model.workflows[name] = Workflow(getattr(standard, name),
                                             isBase=True)

    def updateRefs(self, model):
        '''For "base" and "over" classes, Refs may still point to "base"
           classes. For example, Tool.users may point to appy.model.user.User
           instead of "over" class someApp.user.User. This method updates Refs
           accordingly.'''
        for class_ in model.classes.values():
            # Ignore non-base classes
            if class_.type == 'app': continue
            # Browse forward Ref fields
            for field in class_.fields.values():
                if (field.type != 'Ref') or field.isBack: continue
                # Get the target class
                refClass = model.classes[field.class_.__name__]
                # If this class has been overridden, we must update it with the
                # overridden class.
                if refClass.type == 'over':
                    field.class_ = refClass.python
                    # Update the back ref, too
                    if field.back:
                        field.back.class_ = class_.python

    def linkWorkflows(self, model):
        '''Associate classes and workflows at the model level, based on static
           attributes "workflows" defined on classes, and check that such
           classes are really workflows.'''
        for class_ in model.classes.values():
            workflow = getattr(class_.python, 'workflow', standard.Anonymous)
            name = workflow.__name__
            # Get the corresponding Workflow instance
            workflowClass = model.workflows.get(name)
            if not workflowClass:
                raise Model.Error(NOT_WORKFLOW % (name, class_.name))
            # Make the link
            class_.workflow = workflowClass

    def setTranslationFields(self, pot, translationClass, message, page):
        '''Sets, on this p_translationClass, 2 fields on p_page:
           (1) a Computed field allowing to display the text in the source
               language;
           (2) an editable String field for storing the corresponding i18n
               p_message.
        '''
        # Create the Computed field displaying the text in the source message
        pythonClass = translationClass.python
        labelField = Computed(method=pythonClass.computeLabel,
                       page=page, show=pythonClass.showField, layouts=Layouts.f)
        name = '%s_label' % message.id
        labelField.init(translationClass, name)
        translationClass.fields[name] = labelField
        # Create the String field for storing the translation
        params = {'page': page, 'layouts': Layouts.f,
                  'show': pythonClass.showField}
        # Scan all messages corresponding to p_messageId from all translation
        # files corresponding to p_pot. We will define field length from the
        # longer found message content.
        maxLine = 100 # We suppose a line is 100 chars long
        width = 0
        height = 0
        potBase = pot.stem
        for fileName, poFile in self.translationFiles.items():
            # Ignore po files not corresponding to p_pot
            if not fileName.startswith('%s-' % potBase): continue
            msgContent = poFile.messages[message.id].msg
            # Compute width
            width = max(width, len(msgContent))
            # Compute height (a "\n" counts for one line)
            mHeight = int(len(msgContent)/maxLine) + msgContent.count('<br/>')
            height = max(height, mHeight)
        if height < 1:
            # Propose a one-line field
            params['width'] = width
        else:
            # Propose a multi-line field, or a very-long-single-lined field
            params['format'] = String.TEXT
            params['height'] = height
        field = String(**params)
        field.init(translationClass, message.id)
        translationClass.fields[message.id] = field

    def updateTranslations(self, model):
        '''Injects, on class Translation, a field for every defined i18n
           label. Returns the total number of i18n labels.'''
        # i18n labels are collected from 3 sources:
        # ----------------------------------------------------------------------
        # Name       | Location   | Description
        # ----------------------------------------------------------------------
        # Appy.pot   | appy/tr/po | The labels used in the base Appy classes.
        # <app>.pot  | <app>/tr   | The labels automatically generated by Appy
        #            |            | from the app model.
        # Custom.pot | <app>/tr   | The custom labels managed "by hand" by the
        #            |            | app's developer.
        # ----------------------------------------------------------------------
        # Translations for Appy.pot labels are not modifiable as-is by the app's
        # user. If the app's developer wants to make some Appy.pot label
        # modifiable, he must define its homonym in Custom.pot.
        # As a preamble, load translations from po(t) files
        trPath = self.config.appPath / 'tr'
        self.translationFiles = po.load(path=trPath, pot=False)
        r = 0
        # Get the Translation class
        translationClass = model.classes['Translation']
        # Read the 3 "pot" files
        appyPot = pathlib.Path(inspect.getfile(po)).parent / 'Appy.pot'
        appPot = trPath / ('%s.pot' % self.config.appPath.stem)
        customPot = trPath / 'Custom.pot'
        for pot in (appyPot, appPot, customPot):
            # Get messages from the current pot file
            messages = po.Parser(pot).parse().messages
            r += len(messages)
            # Manage messages from Appy.pot
            if pot.stem == 'Appy':
                for message in messages.values():
                    # For every message, create a hidden String field. Indeed,
                    # the user will not be allowed to update them (but will be
                    # allowed to modify translations from the app's pot file,
                    # see below).
                    field = String(show=False, layouts='f')
                    field.init(translationClass, message.id)
                    # Add it to class Translation
                    translationClass.fields[message.id] = field
            # Manage messages from app's pot files
            else:
                if pot.stem == 'Custom':
                    phase = 'custom'
                    pageName = 'a'
                else:
                    phase = 'main'
                    pageName = '1'
                page = Page(pageName, phase=phase)
                i = 0
                for message in messages.values():
                    # If this message overrides one from Appy.pot, remove the
                    # overridden field added from Appy.pot. This way, we keep
                    # app's fields in the right order.
                    if message.id in translationClass.fields:
                        del(translationClass.fields[message.id])
                    i += 1
                    # For every message, create 2 fields:
                    # - a Computed used to display the text to translate;
                    # - a String holding the translation in itself.
                    self.setTranslationFields(pot, translationClass,
                                              message, page)
                    if (i % model.config.ui.translationsPerPage) == 0:
                        # A new page must be defined
                        page = Page(page.nextName(), phase=page.phase)
        return r

    def run(self):
        '''Loads the model'''
        config = self.config
        # Search Appy classes and workflow, in Python files at the root of the
        # App module, __init__.py excepted.
        pythonFiles = []
        for path in config.appPath.glob('*.py'):
            if path.name != '__init__.py':
                pythonFiles.append(path)
        # Raise an error if no Python file has been found
        if not pythonFiles:
            raise Model.Error(NO_PYTHON_FILE % str(config.appPath))
        # Import every found Python file, searching for Appy classes/workflows
        classType = type(Model)
        classes = {} # ~{s_name: Class}~
        workflows = {} # ~{s_name: Workflow}~
        # Import all modules before reading classes in it. That way, cross-
        # module back references are correctly initialized. Ensure the app's
        # path is in sys.path.
        appPath = str(self.config.appPath)
        if appPath not in sys.path:
            sys.path.insert(0, appPath)
        modules = []
        for path in pythonFiles:
            # We don't use function appy.model.utils.importModule for loading
            # app modules here. Indeed, "importModule" loads a fresh copy of a
            # module, instead of returning the module as already loaded via an
            # "import" statement. But we specifically need to retrieve the
            # already loaded modules, because their classes were already patched
            # with back references.
            exec('import %s' % path.stem)
            module = eval(path.stem)
            modules.append(module)
        # Browse now the loaded modules
        for module in modules:
            # Find classes within this module
            for element in module.__dict__.values():
                # Ignore non-classes or classes imported from other modules
                if (type(element) != classType) or \
                   (element.__module__ != module.__name__): continue
                # Ignore non-Appy classes
                metaClass = self.determineMetaClass(element)
                if not metaClass: continue
                # Add the classes to "classes" or "workflows"
                name = element.__name__
                if (name in classes) or (name in workflows):
                    raise Model.Error(DUPLICATE_NAME % name)
                if '_' in name:
                    raise Model.Error(UNDERSCORED_NAME % name)
                d = classes if metaClass == Class else workflows
                d[name] = metaClass(element, appOnly=self.appOnly)
        # Ensure we have found at least one class
        if not classes:
            raise Model.Error(NO_APPY_CLASS % str(config.appPath))
        # Create the Model instance
        model = Model(self.appConfig, classes, workflows)
        if not self.appOnly:
            # Complete the model with base classes from appy.model
            self.complete(model)
            # Update Refs with "over" classes if defined in the app
            self.updateRefs(model)
            # Link classes with their workflows
            self.linkWorkflows(model)
            # Load translation files and inject every message ID as a field on
            # the Translation class.
            labelsCount = self.updateTranslations(model)
            # Store grantable roles
            model.grantableRoles = model.getRoles(local=False, grantable=True)
            # Inject virtual attributes for every field in every class, in the
            # form of properties.
            for class_ in classes.values(): class_.injectProperties()
            self.log(LOADED_RUNTIME % (len(model.classes), len(model.workflows),
                                       labelsCount))
        else:
            self.log(LOADED_MAKETIME % (len(model.classes),
                                        len(model.workflows)))
        # On server init, also return the translation files, that were already
        # requested while loading the model, in order to determine the length of
        # fields storing translations.
        return model if self.appOnly else (model, self.translationFiles)
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
