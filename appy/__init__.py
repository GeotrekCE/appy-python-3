'''Appy is the simpliest way to build complex webapps'''

# ~license~
# ------------------------------------------------------------------------------
import pathlib
# Store here the path to the Appy root package, it is often requested
path = pathlib.Path(__file__).parent

# ------------------------------------------------------------------------------
class Config:
    '''Root of all configuration options for your app'''
    # These options are those managed by the app developer: they are not meant
    # to be edited during the app lifetime by end users. For such "end-user"
    # configuration options, you must extend the appy.model.tool.Tool class,
    # designed for that purpose. In short, this Config file represents the "RAM"
    # configuration, while the unique appy.model.tool.Tool instance within every
    # app contains its "DB" configuration.

    # In your app/__init__.py, create a class named "Config" that inherits from
    # this one and will override some of the atttibutes defined here, ie:

    # import appy
    # class Config(appy.Config):
    #     someAttribute = "someValue"

    # If "someAttribute" is not a standard Appy attribute, this is a way to add
    # your own configuration attributes.

    # If you want to modify existing attributes, like model configuration or
    # user interface configuration (that, if you have used appy/bin/make to
    # generate your app, are already instantiated in attributes "model" and
    # "ui"), after the attribute definition, modify it like this:

    # class Config(appy.Config):
    #     ...
    #     ui.languages = ('en', 'fr')
    #     model.rootClasses = ['MyClass']

    # Place here a appy.server.Config instance defining the configuration
    # of the Appy HTTP server.
    server = None
    # Place here a appy.server.guard.Config instance defining security options
    security = None
    # Place here a appy.database.Config instance defining database options
    database = None
    # Place here a appy.database.log.Config instance defining logging options
    log = None
    # Place here a appy.model.Config instance defining the application model
    model = None
    # Place here a appy.ui.Config instance defining user-interface options
    ui = None
    # When using Google analytics, specify here the Analytics ID
    googleAnalyticsId = None

    @classmethod
    def check(self):
        '''Ensures the config is valid. Called at server startup.'''
        self.server.static.check()
        self.security.check()
# ------------------------------------------------------------------------------
