#!/usr/bin/python3
# ------------------------------------------------------------------------------
import os, shutil
import appy
from pathlib import Path
from appy.bin import Program
from appy.tr.updater import Updater

# File templates ---------------------------------------------------------------
# <site>/bin/site
site = """
#!/usr/bin/python3.6
# ------------------------------------------------------------------------------
import sys
from pathlib import Path
from appy.bin.run import Run

# ------------------------------------------------------------------------------
site = Path('{self.folder}')
app = Path('{self.app}')
for path in (site, site/'lib', app.parent):
    sys.path.insert(0, str(path))

# ------------------------------------------------------------------------------
if __name__ == '__main__':
    Run().run(site, app)
# ------------------------------------------------------------------------------
"""

# <site>/config.py
config = """
# ------------------------------------------------------------------------------
app = '{self.app}'
site = '{self.folder}'

# Complete the config ----------------------------------------------------------
def complete(c):
    c.model.set(app)
    c.server.set(app)
    c.server.address = 'localhost'
    c.server.port = 8000
    c.database.set(site + '/var')
    c.log.set(site + '/var/site.log', site + '/var/app.log')
# ------------------------------------------------------------------------------
"""

# <app>/__init__.py
appInit = '''
# ------------------------------------------------------------------------------
from appy import database, model, ui, server
from appy.database import log
from appy.server import guard

# ------------------------------------------------------------------------------
import appy
class Config(appy.Config):
    server = server.Config()
    security = guard.Config()
    database = database.Config()
    log = log.Config()
    model = model.Config()
    ui = ui.Config()

# ------------------------------------------------------------------------------
try: # to import the site-specific configuration file
    import config
    config.complete(Config)
except ImportError:
    # The "config" module may not be present at maketime
    pass
# ------------------------------------------------------------------------------
'''

# <app>/make
appMake = '''
#!/usr/bin/python3
# ------------------------------------------------------------------------------
from pathlib import Path
from appy.bin.make import App

# ------------------------------------------------------------------------------
App(Path('.')).update()
# ------------------------------------------------------------------------------
'''

# <app>/static/robots.txt
appRobots = '''
# More information about this file on http://robots-txt.com
User-agent: *
Disallow: /
'''

# ------------------------------------------------------------------------------
class Target:
    '''Abstract class representing the site or app to create/update'''

    def createFile(self, path, content, permissions=None):
        '''Create a file on disk @ p_path, with some p_content and
           p_permissions.'''
        folder = path.parent
        # Create the parent folder if it does not exist
        if not folder.exists(): folder.mkdir(parents=True)
        # Patch content with variables
        content = content.format(self=self)[1:]
        # Create the file
        path = str(path)
        f = open(path, 'w')
        f.write(content)
        f.close()
        # Set specific permissions on the create file when required
        if permissions: os.chmod(path, permissions)

# ------------------------------------------------------------------------------
class Site(Target):
    '''A site to create'''
    # A site is made of 3 sub-folders:
    folders = ('bin', 'lib', 'var')
    # "bin" stores the scripts for controlling the app (start/stop), backuping
    #       or restoring its data, etc;
    # "lib" stores or links the Python modules available to the site. It
    #       contains at least the app;
    # "var" stores the data produced or managed by the site: database files and
    #       folders and log files.

    def __init__(self, folder, app):
        # The base folder for the site
        self.folder = folder
        # The folder where the app resides
        self.app = app

    def create(self):
        '''Creates a fresh site'''
        # Create the root folder (and parents if they do not exist)
        self.folder.mkdir(parents=True)
        # Create the sub-folders
        for name in Site.folders: (self.folder/name).mkdir()
        # Create <site>/bin/site
        self.createFile(self.folder/'bin'/'site', site, 0o770)
        # Create <site>/config.py
        self.createFile(self.folder/'config.py', config)

# ------------------------------------------------------------------------------
class App(Target):
    '''An app to create or update'''

    # Mandatory app sub-folders
    subFolders = (
      'tr',    # Stores "po" and "pot" files (for translations)
      'static' # Stores any static content (images, CSS or Javascript files...)
    )

    # Mandatory files to have in <appFolder>/static
    files = (
      
      'favicon.ico',
      # The file read by robots
      'robots.txt'
    )

    def __init__(self, folder):
        # The base folder for the app. Ensure it is absolute.
        if not folder.is_absolute():
            folder = folder.resolve()
        self.folder = folder

    def create(self):
        '''Creates a new app'''
        # Create <app>/__init__.py
        path = self.folder / '__init__.py'
        if not path.exists():
            self.createFile(self.folder/'__init__.py', appInit)
        # Create <app>/make
        path = self.folder / 'make'
        if not path.exists():
            self.createFile(path, appMake, 0o770)
        # Create base folders
        for name in App.subFolders:
            folder = self.folder / name
            if not folder.exists(): folder.mkdir()
            if name == 'static':
                # Ensure mandatory files are present and create them if not
                robots = folder / 'robots.txt' # The file read by robots
                if not robots.exists():
                    self.createFile(robots, appRobots)
                # The icon retrieved by browsers, shown besides the address bar
                favicon = folder / 'favicon.ico'
                if not favicon.exists():
                    # Copy the default one in Appy
                    ico = '%s/ui/static/favicon.ico' % str(appy.path)
                    shutil.copy(ico, str(favicon))

    def update(self):
        '''Updates an existing app'''
        print('Updating %s...' % self.folder)
        # Ensure the base files and folders are created
        self.create()
        # Call the translations updater that will create or update translation
        # files for this app.
        Updater(self.folder/'tr').run()
        print('Done.')

# ------------------------------------------------------------------------------
class Make(Program):
    '''This program allows to create or update an app or a site'''
    # We can create/update an app or a site
    allowedTargets = ('app', 'site')

    # Help messages
    HELP_TARGET = 'can be "app" for creating/updating an app or "site" for ' \
                  'creating a site.'
    HELP_FOLDER = 'folder is the absolute path to the base folder for the ' \
                  'app or site.'
    HELP_A = '[site] the absolute path to the app that will run this site.'

    # Error messages
    WRONG_TARGET = 'Wrong target "%s".'
    SITE_EXISTS = '%s already exists. You must specify an inexistent path ' \
                  'that this script will create and populate with a fresh site.'
    NO_APP = 'No app was specified.'
    WRONG_APP = '%s does not exist or is not a folder.'

    def defineArguments(self):
        '''Define the allowed arguments for this program'''
        parser = self.parser
        # Positional arguments, common to all targets (app and site)
        parser.add_argument('target', help=Make.HELP_TARGET)
        parser.add_argument('folder', help=Make.HELP_FOLDER)
        # Optional arguments specific to "site"
        parser.add_argument('-a', '--app', dest='app', help=Make.HELP_A)

    def analyseArguments(self):
        '''Check and store arguments'''
        # "folder" will be a Path created from the "folder" argument
        self.folder = None
        # Site-specific attributes
        self.app = None # The Path to the app from '-a' option
        # Check arguments
        args = self.args
        # Check target
        target = args.target
        if target not in self.allowedTargets:
            self.exit(self.WRONG_TARGET % target)
        # Get a Path for the "folder" argument
        self.folder = Path(self.args.folder)
        # Check site-specific arguments and values
        if target == 'site':
            # The path to the site must not exist
            if self.folder.exists():
                self.exit(self.SITE_EXISTS % self.folder)
            # The path to the app must be specified
            app = self.args.app
            if not app: self.exit(self.NO_APP)
            # The path must exist
            self.app = Path(app)
            if not self.app.exists() or not self.app.is_dir():
                self.exit(self.WRONG_APP % self.app)
        elif target == 'app':
            # No more check for the moment. The folder can exist or not.
            pass

    def run(self):
        target = self.args.target
        if target == 'site':
            Site(self.folder, self.app).create()
        elif target == 'app':
            action = 'update' if self.folder.exists() else 'create'
            eval('App(self.folder).%s()' % action)
        print('Done.')

# ------------------------------------------------------------------------------
if __name__ == '__main__': Make().run()
# ------------------------------------------------------------------------------
