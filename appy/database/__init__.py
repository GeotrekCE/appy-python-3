'''Appy module managing database files'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import os, time, pathlib

import ZODB, transaction
from DateTime import DateTime
from zc.lockfile import LockError
from BTrees.IOBTree import IOBTree
from persistent.mapping import PersistentMapping
from ZODB.POSException import ConnectionStateError

from appy.database.lock import Lock
from appy.utils import path as putils
from appy.database.catalog import Catalog

# Constants  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
DB_CREATED = 'Database created @%s.'
DB_NOT_FOUND = 'Database does not exist @%s.'
DB_LOCKED = 'The datase is currently locked (%s)'
DB_PACKING = 'Packing %s (may take a while)...'
DB_PACKED = 'Done. Went from %s to %s.'
TEMP_STORE_NOT_FOUND = 'Temp store does not exist in %s.'
OBJECT_STORE_NOT_FOUND = 'Object store does not exist in %s.'
TOOL_NOT_FOUND = 'Tool does not exist in %s.'
METHOD_NOT_FOUND = 'Method "%s" does not exist on the tool.'
TEMP_STORE_EMPTY = 'No temp object has been deleted in %s.'
TEMP_OBJECTS_DELETED = '%s temp object(s) removed from %s.'
OBJECT_EXISTS = 'An object with id "%s" already exists.'
CLASS_NOT_FOUND = 'Class "%s" does not exist.'
CUSTOM_ID_NO_IKEY = 'It is not possible to get an ikey for object having a ' \
  'custom ID (%s).'
NEW_TEMP_WITH_ID = 'An ID cannot be specified when creating a temp object.'
CUSTOM_ID_NOT_STR = 'Custom ID must be a string.'
SEARCH_NO_CATALOG = 'Invalid operation: there is no catalog for instances ' \
  'of class "%s".'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Config:
    '''Database-related parameters. The database used by Appy is the Zope Object
       Database (ZODB).'''

    def __init__(self):
        # The path to the .fs file, the main database file
        self.filePath = None
        # The path to the folder containing database-controlled binary files
        self.binariesFolder = None
        # Typically, we have this configuration: within a Appy <site>, we have a
        # folder named "var" containing all database-related stuff: the main
        # database file named appy.fs and the sub-folders containing
        # database-controlled binaries. In this case:
        #   "filePath"       is <site>/var/appy.fs
        #   "binariesFolder" is <site>/var

        # What roles can unlock locked pages ? By default, only a Manager can
        # do it. You can place here roles expressed as strings or Role
        # instances, global or local.
        self.unlockers = ['Manager']

    def set(self, folder, filePath=None):
        '''Sets site-specific configuration elements. If filePath is None,
           p_folder will both hold binaries and the database file that will be
           called appy.fs.'''
        self.binariesFolder = pathlib.Path(folder)
        if filePath is None:
            self.filePath = self.binariesFolder / 'appy.fs'
        else:
            self.filePath = pathlib.Path(filePath)

    def getDatabase(self, server, handler, poFiles, method=None):
        '''Create and/or connect to the site's database (as instance of class
           Database), set it as attribute to p_server and perform the task
           linked to p_server.mode.'''
        path = str(self.filePath)
        logger = server.loggers.app
        server.database = None
        # Are we running the server in "classic" mode (fg or bg) ?
        classic = server.mode in ('fg', 'bg')
        if not self.filePath.exists():
            # The database does not exist. For special modes, stop here.
            if not classic:
                logger.error(DB_NOT_FOUND % str(self.filePath))
                return
            # The database will be created - log it
            logger.info(DB_CREATED % path)
            created = True
        else:
            created = False
        # Create or get the ZODB database
        try:
            database = Database(path, server)
        except LockError as err:
            logger.error(DB_LOCKED % str(err))
            return
        server.database = database
        # Perform the appropriate action on this database, depending on server
        # mode.
        if classic:
            # We are starting the server: initialise the database. This is the
            # "initialization" connection, allowing to perform database
            # initialization or update at server startup.
            database.init(created, handler, poFiles)
        elif server.mode == 'clean':
            # Clean the database temp folder and pack it
            database.clean(handler, logger)
        elif server.mode == 'run':
            # Execute method named p_method on the tool
            database.run(method, handler, logger)

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Database:
    '''Represents the app's database'''

    # Database-specific exception class
    class Error(Exception): pass

    # Modulo for computing "ikeys" (see m_init's doc) from object's integer IDs
    MOD_IKEY = 10000

    def __init__(self, path, server):
        # The ZODB database object
        self.db = ZODB.DB(path)
        # The main HTTP server
        self.server = server

    def openConnection(self):
        '''Opens and returns a connection to this database'''
        return self.db.open()

    def closeConnection(self, connection):
        '''Closes the p_connection to this database'''
        try:
            connection.close()
        except ConnectionStateError:
            # Some updates are probably uncommitted. Abort the current
            # transaction and then try again to close the connection.
            transaction.abort()
            connection.close()

    def commit(self, handler):
        '''Commits the current transaction related to p_handler'''
        transaction.commit()

    def abort(self, connection=None, message=None, logger=None):
        '''Abort the current transaction'''
        # Logs a p_message when requested
        if message: logger.error(message)
        # Abort the ongoing transaction
        transaction.abort()
        # Close the p_connection if given
        if connection: connection.close()

    def close(self, abort=False):
        '''Closes the database'''
        # Must we first abort any ongoing transaction ?
        if abort: transaction.abort()
        try:
            self.db.close()
        except ConnectionStateError:
            # Force aborting any ongoing transaction
            transaction.abort()
            self.db.close()

    def init(self, created, handler, poFiles):
        '''Create the basic data structures and objects in the database'''
        # Get a connection to the database. This is the "initialization"
        # connection, allowing to perform database initialization or update at
        # server startup.
        connection = self.db.open()
        # Make this connection available to the initialisation p_handler
        handler.connection = connection
        # Get the root object
        root = connection.root
        # If the database is being p_created, add the following attributes to
        # the root object. Class "PersistentMapping" is named "PM" for
        # conciseness.
        # ----------------------------------------------------------------------
        # name       |  type  | description
        # ----------------------------------------------------------------------
        # iobjects   |  PM+   | The main persistent dict, storing all persistent
        #            |        | objects. Any object stored here has an attribute
        #            |        | named "iid" storing an identifier being an
        #            |        | incremental integer value. The last used integer
        #            |        | is in attribute "lastId" (see below). The dict
        #            |        | is structured that way: keys are integers made
        #            |        | of the 4 last digits of objects identifiers
        #            |        | (such a key is named an "ikey"), and values are
        #            |        | IOBTrees whose keys are object identifiers and
        #            |        | values are the objects themselves.
        # ----------------------------------------------------------------------
        # objects    |  PM    | A secondary persistent dict storing objects
        #            |        | that, in addition to their integer ID, have
        #            |        | also a string identifier, in attribute "id".
        #            |        | Such a string ID is part of the object URL and
        #            |        | is defined for its readability or ease of use.
        #            |        | The number of objects getting this kind of ID is
        #            |        | not meant to be huge: this is why we have chosen
        #            |        | not to store them in a OOBTree, but in a
        #            |        | PersistentMapping. Basic objects, like the tool
        #            |        | and translations, get such an ID. Unlike
        #            |        | "iobjects", the "objects" data structure has a
        #            |        | single level: keys are IDs (as strings) and
        #            |        | values are the objects themselves.
        #            |        |
        #            |        | An object without string ID:
        #            |        | - has attributes "id" and "iid" both storing the
        #            |        |   integer ID;
        #            |        | - is stored exclusively in "iobjects".
        #            |        |
        #            |        | An object with a string ID:
        #            |        | - has attribute "id" storing the string ID;
        #            |        | - has attribute "iid" storing the integer ID;
        #            |        | - is stored both in "iobjects" (based on its
        #            |        |   "iid") and in "objects" (based on is "id").
        # ----------------------------------------------------------------------
        # temp       |  PM    | A persistent mapping storing objects being
        #            |        | created via the ui. The process of creating an
        #            |        | object is the following: a temporary object is
        #            |        | created in this dict, with a negative integer ID
        #            |        | being an incremental value (see attribute
        #            |        | "lastTempId" below). The dict's keys are such
        #            |        | IDs, while values are the temp objects under
        #            |        | creation. Once the user has filled and saved
        #            |        | the corresponding form in the ui, the object is
        #            |        | moved to "iobjects"; additionally, it is also
        #            |        | stored in "objects" if its ID is a string ID.
        #            |        | If the user cancels the form, the object is
        #            |        | simply deleted from the "temp" dict. Restarting
        #            |        | the site does not empty the "temp" folder;
        #            |        | cleaning it may occur in the "nightlife" script.
        #            |        | Objects created "from code" do not follow the
        #            |        | same route and are directly created in
        #            |        | "(i)objects".
        # ----------------------------------------------------------------------
        # lastId     |  int   | An integer storing the last ID granted to an
        #            |        | object being stored in "iobjects".
        # ----------------------------------------------------------------------
        # lastTempId |  int   | An integer storing the last ID granted to a
        #            |        | temporary object stored in "temp".
        # ----------------------------------------------------------------------
        # catalogs   |  PM    | A persistent mapping of catalogs. For every
        #            |        | "indexable" class in the model, there will be
        #            |        | one entry whose key is the class name and whose
        #            |        | value is a Catalog instance
        #            |        | (see appy/database/catalog.py).
        # ----------------------------------------------------------------------
        if created:
            root.iobjects = PersistentMapping()
            root.objects = PersistentMapping()
            root.temp = PersistentMapping()
            root.lastId = root.lastTempId = 0
            root.catalogs = PersistentMapping()
        # The "iobjects" structure, made of 2 levels, allows to have the first
        # level as an always-in-memory persistent mapping made of at most
        # 10 000 entries. This structure, when full, should be of approximately
        # 100Kb. The second level is made of IOBTrees. An IOBTree is an optimal
        # data structure for storing a large number of objects. Like any BTree
        # structure, it behaves like a dict, but, internally, is made of
        # sub-nodes that, for some of them, can be on disk and others can be
        # loaded in memory. On the contrary, a standard mapping (or its
        # persistent counterpart) must be loaded in memory in its entirety.
        # BTree's sub-nodes group objects by sorted identifiers. By using
        # incremental integers, objects are grouped in some chronological way.
        # Sub-nodes corresponding to past objects are probably less loaded in
        # memory. Getting a recent object loads the sub-node in memory, with
        # objects that could also need to be retrieved by other requests because
        # of their temporal proximity.
        # ----------------------------------------------------------------------
        # Ensure all base objects are created in the database: the tool, base
        # users, translation files and catalogs. Create any object that would
        # be missing.
        # ----------------------------------------------------------------------
        try:
            # Create the tool if it does not exist yet
            tool = root.objects.get('tool') or \
                   self.new(handler, 'Tool', id='tool', secure=False)
            # Update the initialisation handler
            handler.tool = tool
            # Create or update catalogs
            Catalog.manageAll(root, handler)
            # Let the tool initialise itself and create sub-objects as required
            tool.init(handler, poFiles)
            # Commit changes
            transaction.commit()
        except self.Error as e:
            transaction.abort()
            raise e
        except Exception as e:
            transaction.abort()
            raise e
        finally:
            connection.close()

    #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Methods for searching objects
    #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def search(self, handler, className, ids=False, **kwargs):
        '''Perform a search on instances of a class whose name is p_className
           and return the list of matching objects. If p_ids is True, it returns
           a list of object IDS instead of a list of true objects.'''
        # p_ids being True can be useful for some usages like determining the
        # number of objects without needing to get information about them.
        # ~~~
        # Ensure there is a catalog for p_className
        catalog = handler.connection.root.catalogs.get(className)
        if not catalog:
            raise self.Error(SEARCH_NO_CATALOG % className)
        r = catalog.search(handler, **kwargs)
        if r and not ids:
            # Convert the list of integers to real objects
            return [self.getObject(handler, id) for id in r]
        return r or []

    def reindexObject(self, handler, o, **kwargs):
        '''(re)indexes this object in the catalog corresponding to its class'''
        # Ensure p_o is "indexable"
        className = o.class_.name
        catalog = handler.connection.root.catalogs.get(className)
        if not catalog:
            raise self.Error(SEARCH_NO_CATALOG % className)
        return catalog.reindexObject(o, **kwargs)
        
    def count(self, className): pass
    def compute(self, className): pass

    #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Global database operations
    #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def pack(self, logger=None):
        '''Packs the database'''
        # Get the absolute path to the database file
        path = self.db.storage.getName()
        # Get its size, in bytes, before the pack
        size = os.stat(path).st_size
        # Perform the pack
        logger.info(DB_PACKING % path)
        self.db.pack()
        # Get its size, in bytes, after the pack
        newSize = os.stat(path).st_size
        # Log the operation
        if logger:
            logger.info(DB_PACKED % (putils.getShownSize(size),
                                     putils.getShownSize(newSize)))

    def clean(self, handler, logger):
        '''Cleaning the database means removing any temp object from it'''
        # Create a specific connection
        connection = handler.connection = self.db.open()
        # Get the temp store
        temp = getattr(connection.root, 'temp', None)
        dbFile = handler.server.config.database.filePath
        dbPath = str(dbFile)
        if temp is None:
            return self.abort(connection, TEMP_STORE_NOT_FOUND % dbPath, logger)
        count = len(temp)
        if count == 0:
            logger.info(TEMP_STORE_EMPTY % dbPath)
        else:
            # For removing temp objects, it is useless to call m_delete, because
            # the object is not yet linked to any other object, does not have
            # yet a related filesystem space, etc.
            connection.root.temp = PersistentMapping()
            # Reset the ID counter
            connection.root.lastTempId = 0
            logger.info(TEMP_OBJECTS_DELETED % (count, dbPath))
            transaction.commit()
        connection.close()
        # Pack the database
        self.pack(logger)

    def run(self, method, handler, logger):
        '''Executes method named m_method on the tool'''
        # Create a specific connection
        connection = handler.connection = self.db.open()
        # Get the store containing the tool
        root = connection.root
        store = getattr(root, 'objects', None)
        dbFile = handler.server.config.database.filePath
        dbPath = str(dbFile)
        # Ensure the "objects" store exists
        abort = self.abort
        if store is None:
            return abort(connection, OBJECT_STORE_NOT_FOUND % dbPath, logger)
        # Ensure the tool exists
        tool = root.objects.get('tool')
        if tool is None:
            return abort(connection, TOOL_NOT_FOUND % dbPath, logger)
        # Ensure p_method is defined on the tool
        if not hasattr(tool, method):
            return abort(connection, METHOD_NOT_FOUND % method, logger)
        # Execute the method
        try:
            getattr(tool, method)()
        except Exception as err:
            handler.server.logTraceback()
            return abort(connection)
        # Suppose p_method has changed something in the database
        transaction.commit()
        connection.close()

    def getIkey(self, id=None, o=None):
        '''Gets an "ikey" = the first level key for finding an object in store
           "iobjects" (more info on m_init). The ikey can be computed from a
           given integer p_id or from p_o's ID.'''
        id = id if o is None else o.id
        if not isinstance(id, int):
            raise self.Error(CUSTOM_ID_NO_IKEY % id)
        return abs(id) % Database.MOD_IKEY

    def newId(self, root, temp=False):
        '''Computes and returns a new integer ID for an object to create'''
        # Get the attribute storing the last used ID
        attr = 'lastTempId' if temp else 'lastId'
        # Get the last ID in use
        last = getattr(root, attr)
        r = last + 1
        setattr(root, attr, r)
        return -r if temp else r

    def getStore(self, o=None, id=None, root=None, create=False):
        '''Get the store where p_o is supposed to be contained according to its
           ID. Instead of p_o, an p_id can be given. If p_create is True, the
           object's ID is a positive integer and the sub-store at its "ikey"
           does not exist, it is created. If the p_root database object is None,
           it will be retrieved from p_o.'''
        # Get the root database object
        root = root or o.H().connection.root
        id = id or o.id
        # It may be the store of objects with custom IDs...
        if isinstance(id, str):
            r = root.objects
        # ... or the temp store ...
        elif id < 0:
            r = root.temp
        # ... or a sub-store in the standard store "iobjects"
        else:
            r = root.iobjects
            ikey = self.getIkey(id=id)
            if ikey in r:
                r = r[ikey]
            else:
                # The sub-store does not exist. Create it if required.
                if create:
                    r[ikey] = sub = IOBTree()
                    r = sub
                else:
                    r = None
        return r

    def exists(self, o=None, id=None, store=None, raiseError=False):
        '''Checks whether an object exists in the database, or an ID is already
           in use.'''

        # If p_o is...
        # ----------------------------------------------------------------------
        # not None | p_id and p_store are ignored, and the method checks if p_o
        #          | is present in the database.
        # ----------------------------------------------------------------------
        #   None   | p_id and p_store must be non empty and the method checks if
        #          | p_id is already in use in p_store.
        # ----------------------------------------------------------------------
        # If p_raiseError is True, if the object or ID exists, the method raises
        # an error. Else, it returns a boolean value.
        # ----------------------------------------------------------------------

        if id is None:
            id = o.id
            store = self.getStore(o)
        # Check the existence of the ID in the store
        r = id in store if store else None
        # Return the result or raise an error when appropriate
        if r and raiseError:
            raise self.Error(OBJECT_EXISTS % id)
        return r

    def new(self, handler, className, id=None, temp=False, secure=True,
            initialComment=None, initialState=None):
        '''Creates, in the database, a new object as an instance of p_className.
           p_handler is the current request handler. If p_id is not None, it is
           a string identifier that will be set in addition to an integer ID
           that will always be computed.'''

        # * Preamble * Read appy.database.Config::init for more info about the
        #              database structure.
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # If p_temp is ...
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # True            | A temp object is created in the "temp" dict. Later,
        #                 | if its creation is confirmed, he will be moved to a
        #                 | "final" part of the database;
        # False (default) | A "final" object is added in the database, in the
        #                 | "objects" and/or "iobjects" dict, depending on its
        #                 | identifier.
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # If p_secure is ...
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # True (default) | Appy will raise an error if the currently logged
        #                | user is not allowed to perform such creation;
        # False          | the security check will be bypassed.
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # When the object is created, an initial entry is created in its
        # history. p_initialComment, if given, will be set as comment for this
        # initial entry. p_initialState (str) can be used to force the object to
        # get this particular state instead of its workflow's initial state.
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        # Ensure p_id's validity
        custom = id is not None
        if custom and not isinstance(id, str):
            raise self.Error(CUSTOM_ID_NOT_STR)
        # Find the class corresponding to p_className
        class_ = handler.server.model.classes.get(className)
        if not class_: raise self.Error(CLASS_NOT_FOUND % className)
        # Security check
        guard = handler.guard
        if secure: guard.mayInstantiate(class_, raiseOnError=True)
        # The root database object
        root = handler.connection.root
        # Define the object IDs: "id" and "iid"
        if custom and temp: raise self.Error(NEW_TEMP_WITH_ID)
        iid = self.newId(root, temp=temp)
        # Determine the place to store the object
        store = self.getStore(id=iid, root=root, create=True)
        # Prevent object creation if "iid" or "id" refer to an existing object
        self.exists(id=iid, store=store, raiseError=True)
        if custom: self.exists(id=id, store=root.objects, raiseError=True)
        # Create the object
        id = id or iid
        o = class_.new(iid, id, guard.userLogin, initialComment, initialState)
        # Store the newly created object in the database
        store[iid] = o
        if custom:
            root.objects[id] = o
        return o

    def move(self, o):
        '''Move the temp object p_o from the "temp" store to one of the final
           stores, "objects" or "iobjects".'''
        # The root database object
        root = o.H().connection.root
        # A method named "generateId" may exist on p_o's class, for producing a
        # database ID for the object. If such method is found, it must return a
        # string ID and the object will be added to store "objects" in addition
        # to store "iobjects".
        iid = self.newId(root, temp=False)
        id = o.class_.generateId(o) or iid
        custom = id != iid
        # Determine the store where to move the object. Create the ad-hoc
        # sub-store in store "iobjects" if it does not exist yet.
        store = self.getStore(id=iid, root=root, create=True)
        # Prevent object creation if "iid" or "id" refer to an existing object
        self.exists(id=iid, store=store, raiseError=True)
        if custom: self.exists(id=id, store=root.objects, raiseError=True)
        # Perform the move
        del(root.temp[o.iid])
        o.iid = iid
        o.id = id
        store[iid] = o
        if custom:
            root.objects[id] = o

    def update(self, o, validator, initiator=None):
        '''Update object p_o from data collected from the UI via a p_validator.
           The possible p_initiator object may be given. Returns a message to
           return to the UI, or None if p_o has already been deleted.'''
        o.H().commit = True
        # Additionally, if p_o is a temp object, the operation has the effect of
        # "converting" it to a "final" object, by changing its ID and moving it
        # from the "temp" store to a final store: "objects" or "iobjects".
        isTemp = o.isTemp()
        # If p_o is not temp, as a preamble, remember the previous values of
        # fields, for potential historization.
        currentValues = None if isTemp \
                             else o.history.getCurrentValues(o,validator.fields)
        # Store, on p_o, new values for fields as collected on p_validator
        for field in validator.fields:
            field.store(o, validator.values[field.name])
        # Keep in history potential changes on historized fields
        if currentValues:
            o.history.historize(currentValues)
        # In the remaining of this method, at various places, we will check if
        # p_o has already been deleted or not. Indeed, p_o may just have been a
        # transient object whose only use was to collect data from the UI.
        # ---
        # Call the custom "onEditEarly" if available. This method is called
        # *before* potentially linking p_o to its initiator.
        if isTemp and hasattr(o, 'onEditEarly'):
            o.onEditEarly()
            if not self.exists(o=o): return
        # Manage the relationship between the initiator and the new object
        if isTemp and initiator:
            initiator.manage(o)
            if not self.exists(o=o): return
        # Store the "cid" if the object is not temp
        if not isTemp: o.cid = o.computeCid()
        # Prepare the method result: a potential translated message
        r = None
        # Call the custom "onEdit" if available
        if hasattr(o, 'onEdit'):
            r = o.onEdit(isTemp)
            if not self.exists(o=o): return
        # Update last modification date
        if not isTemp: o.history.modified = DateTime()
        # If p_o is temp, convert it to a "final" object by moving it from dict
        # "temp" to "objects" or "iobjects".
        if isTemp: self.move(o)
        # Unlock the currently saved page on the object
        Lock.remove(o, o.req.page)
        # Reindex the object when appropriate
        if o.class_.isIndexable():
            o.reindex()
        return r or o.translate('object_saved')

    def delete(self, o, historize=False, executeMethods=True, root=None):
        '''Delete object p_o from the database. When unlinking it from other
           objects, if the concerned Ref fields are historized and p_historize
           is True, this deletion is noted in tied object's histories.'''        
        handler = o.H()
        handler.commit = True
        # Call a custom "onDelete" if it exists
        if executeMethods and hasattr(o, 'onDelete'): o.onDelete()
        # Remove any link to any other object
        title = o.getShownValue()
        for field in o.class_.fields.values():
            if field.type != 'Ref': continue
            for tied in field.getValue(o, single=False):
                field.back.unlinkObject(tied, o, back=True)
                # Historize this unlinking when relevant
                if historize and field.back.getAttribute(tied, 'historized'):
                    className = o.translate(tied.class_.name)
                    tied.history.add('Unlink',
                                     comments='%s: %s' % (className, title))
        # Unindex p_o if it was indexed
        if o.class_.isIndexable() and not o.isTemp(): o.reindex(unindex=True)
        # Delete the filesystem folder corresponding to this object
        folder = self.getFolder(o, create=False)
        if folder.exists():
            # Try to move it to the OS temp folder; if it fails, delete it
            putils.FolderDeleter.delete(folder, move=True)
        # Get the store containing p_o
        root = root or o.H().connection.root
        iid = o.iid
        store = self.getStore(id=iid, root=root)
        # Remove p_o from this store, and potentially from root.objects, too
        del(store[iid])
        if o.id != iid:
            del(root.objects[o.id])

    def getObject(self, handler, id):
        '''Gets an object given its p_id'''
        # Convert p_id to an int if it is an integer coded in a string
        id = int(id) if (isinstance(id, str) and id.isdigit()) else id
        store = self.getStore(id=id, root=handler.connection.root)
        if store: return store.get(id)

    def getFolder(self, o, create=True):
        '''Gets, as a pathlib.Path instance, the folder where binary files
           related to p_o are (or will be) stored on the database-controlled
           filesystem. If p_create is True and the folder does not exist, it is
           created (together with potentially missing parent folders).'''
        # Start with the root folder storing site binaries
        r = o.config.database.binariesFolder
        # Add the object-specific path, depending on its ID
        id = o.iid
        r = r / str(self.getIkey(id=id)) / str(abs(id))
        # Create this folder if p_create is True and it does not exist yet
        if create and not r.exists():
            r.mkdir(parents=True)
        return r
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
