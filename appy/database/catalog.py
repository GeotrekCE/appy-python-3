'''A catalog is a dict of database indexes storing information about instances
   of a given class from an Appy app's model.'''

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from BTrees.IIBTree import IITreeSet, difference
from persistent.mapping import PersistentMapping

from appy.database.indexes import Index
from appy.model.utils import Object as O
from appy.database.operators import Operator

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
CATALOG_CREATED = 'Catalog created for class "%s".'
CATALOG_REMOVED = 'Catalog removed for class "%s".'
INDEXES_POPULATED = '%d/%d object(s) reindexed during population of ' \
  'index(es) %s.'
INDEX_NOT_FOUND = 'There is no indexed field named "%s" on class "%s".'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Changes:
    '''This class represents a set of changes within a catalog's indexes'''

    # Types of changes
    types = ('created', # Indexes having been created
             'updated', # Indexes whose type has been changed
             'deleted') # Indexes having been deleted because there is no more
                        # corresponding indexed field on the related class.

    def __init__(self, handler, class_):
        self.handler = handler
        self.class_ = class_
        for type in Changes.types:
            setattr(self, type, [])

    def log(self):
        '''Dump an info in the log if at least one change has occurred'''
        r = []
        for type in Changes.types:
            names = getattr(self, type)
            # Ignore this type of change if no change of this type has occurred
            if not names: continue
            prefix = 'index' if len(names) == 1 else 'indexes'
            names = ', '.join(['"%s"' % name for name in names])
            r.append('%s %s %s' % (prefix, names, type))
        for info in r:
            self.handler.log('app', 'info', 'Class %s: %s.' % \
                             (self.class_.name, info))

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Catalog(PersistentMapping):
    '''Catalog of database indexes for a given class'''

    # Catalog-specific exception class
    class Error(Exception): pass

    # A catalog is a dict of the form ~{s_name: Index_index}~
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # name    | The name of an indexed field on the class corresponding to this
    #         | catalog.
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # index   | An instance of one of the Index sub-classes as defined in
    #         | package appy/database/indexes.
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def __init__(self, handler, class_):
        PersistentMapping.__init__(self)
        # The name of the corresponding Appy class
        self.name = class_.name
        # A set containing all instances (stored as iids) of p_class
        self.all = IITreeSet()

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Class methods
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    @classmethod
    def populate(class_, root, handler, populate):
        '''Called by the framework, this method populates new indexes or indexes
           whose type has changed. The list of indexes to populate is given in
           p_populate, as produced by m_manageAll.'''
        counts = O(total=0, updated=0)
        # Browse indexes to populate
        database = handler.server.database
        for className, indexes in populate.items():
            # Browse all instances of the class corresponding to this catalog
            # and reindex those being concerned by "indexes".
            catalog = root.catalogs[className]
            for iid in catalog.all:
                o = database.getObject(handler, iid)
                # Count this object
                counts.total += 1
                # Submit the object to every index to populate
                updated = o.reindex(indexes=indexes)
                if updated:
                    counts.updated += 1
        # At the time the database is created, there is a single object in it:
        # the tool.
        if counts.total > 1:
            # Log details about the operation
            names = [] # The names of the populated indexes
            for className, indexes in populate.items():
                for index in indexes:
                    names.append('%s::%s' % (className, index.name))
            message = INDEXES_POPULATED % (counts.updated, counts.total, names)
            handler.log('app', 'info', message)

    @classmethod
    def manageAll(class_, root, handler):
        '''Called by the framework, this method creates or updates, at system
           startu, catalogs required by the app's model .'''
        # Ensure a catalog exists for every indexable class
        model = handler.server.model
        catalogs = root.catalogs
        # Maintain a dict of indexable classes ~{s_name: None}~. It will allow,
        # at the end of the process, to remove every index that do not
        # correspond to any indexable class anymore.
        indexable = {}
        names = list(catalogs.keys())
        # Maintain a dict, keyed by class name, of the indexes to populate, from
        # all catalogs. Indeed, populating any index requires to scan all
        # database objects. This scanning will be done only once, at the end of
        # this method, after having created, updated or deleted all indexes from
        # all catalogs.
        populate = {} #~{s_className: [Index]}~
        # Browse all model classes, looking for catalogs and indexes to manage
        for modelClass in model.classes.values():
            name = modelClass.name
            # Ignore non-indexable classes
            if not modelClass.isIndexable(): continue
            indexable[name] = None
            if name not in catalogs:
                catalog = catalogs[name] = Catalog(handler, modelClass)
                handler.log('app', 'info', CATALOG_CREATED % name)
            else:
                catalog = catalogs[name]
            # Potentially update indexes in this catalog
            toPopulate = catalog.updateIndexes(handler, modelClass)
            if toPopulate:
                populate[name] = toPopulate
        # Remove catalogs for which no indexable class has been found
        for name in names:
            if name not in indexable:
                del(catalogs[name])
                handler.log('app', 'info', CATALOG_REMOVED % name)
        # Populate indexes requiring it
        if populate:
            class_.populate(root, handler, populate)

    def updateIndexes(self, handler, class_):
        '''Create or update indexes for p_class_. Returns the list of indexes
           that must be populated.'''
        changes = Changes(handler, class_)
        r = [] # The indexes that must be populated
        all = [] # Remember the names of all indexes
        # Browse fields
        for field in class_.fields.values():
            # Ignore fields requiring no index
            if not field.indexed: continue
            name = field.name
            all.append(name)
            # Do nothing if the index already exists
            if name in self: continue
            # Create the index: it does not exist yet
            index = self[name] = Index(name, self)
            changes.created.append(name)
            r.append(index)
        # Browse indexes, looking for indexes to delete
        for name in self.keys():
            if name not in all:
                changes.deleted.append(name)
        # Delete indexes for which there is no more corresponding indexed field
        for name in changes.deleted:
            del(self[name])
        # Log info if changes have been performed
        changes.log()
        # Return the list of indexes to populate
        return r

    def getIndex(self, name):
        '''Get the index named p_name or raise an exception if no such index
           exists in this catalog.'''
        r = self.get(name)
        if not r: raise self.Error(INDEX_NOT_FOUND % (name, self.name))
        return r

    def search(self, handler, secure=True, sortBy=None, sortOrder='asc',
               **fields):
        '''Performs a search in this catalog. Returns a IITreeSet object if
           results are found, None else.'''
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # Param      | Description
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # secure     | If not True, security checks depending on user
        #            | permissions are bypassed.
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # sortBy     | If specified, it must be the name of an indexed field on
        #            | p_className.
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # sortOrder  | Can be "asc" (ascending, the defaut) or "desc"
        #            | (descending).
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # fields     | Keyword args must correspond to valid indexed field names
        #            | on p_className. For every such arg, the specified value
        #            | must be a valid value according to the field definition.
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # Add the security-related search parameter if p_secure is True
        if secure: fields['allowed'] = handler.guard.userAllowed
        # The result set, as a IITreeSet instance (or None)
        r = None
        # p_fields items can be of 2 kinds.
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # If...    | It determines...
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # positive | a set of matching objects. A single value or an operator
        #          | like "and" or "or" is positive;
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # negative | a set of objects that must be excluded from the result. The
        #          | "not" operator is negative.
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        positive = False # True if at least one positive arg is met
        negative = None # The list of negative args encountered
        # Browse search values from p_fields. Those values are implicitly
        # AND-ed: as soon as one value does not match, there is no match at all.
        for name, value in fields.items():
            if isinstance(value, Operator) and value.negative:
                # A negative operator. Do not manage it now, store it for later.
                neg = (name, value)
                if negative is None:
                    negative = [neg]
                else:
                    negative.append(neg)
            else:
                # A positive operator or a value
                positive = True
                # Get the corresponding index
                index = self.getIndex(name)
                # Update "r" with the objects matching "value" in index
                # named "name".
                r = index.search(value, r)
                if not r: return # There is no match at all
        # If there was no positive arg at all, take, as basis for the search,
        # all instances from this class' catalog.
        r = self.all if not positive else r
        if not r or not negative: return r
        # Apply negative args
        for name, value in negative:
            ids = self.getIndex(name).search(value, r)
            if ids:
                r = difference(r, ids)
                if not r: return
        return r

    def reindexObject(self, o, fields=None, indexes=None, unindex=False,
                      exclude=False):
        '''(Re-/un-)indexes this p_o(bject). In most cases, you, app developer,
           don't have to reindex objects "manually" with this method. When an
           object is modified after some user action has been performed, Appy
           reindexes it automatically. But if your code modifies other objects,
           Appy may not know that they must be reindexed, too. So use this
           method in those cases.'''
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # The method returns False if it has produced no effect, True else.
        # "Producing an effect" means: object-related data as stored in indexes
        # has been modified (addition, change or removal) for at least one
        # index.
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # Method parameters are described hereafter.
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        #  unindex | If True, the object is unindexed instead of being
        #          | (re)indexed.
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        #  fields  | p_fields may hold a list of indexed field names. In that
        #          | case, only these fields will be reindexed. If None (the
        #          | default), all indexable fields defined on p_o's class (via
        #          | attribute "indexed") are (re)indexed.
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        #  indexes | As an alternative to p_fields, you may, instead, specify,
        #          | in p_indexes, a list of appy.database.indexes.Index
        #          | instances. Appy uses this; the app developer should use
        #          | p_fields instead.
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        #  exclude | If p_exclude is True, p_fields is interpreted as containing
        #          | the list of indexes NOT TO recompute: all the indexes not
        #          | being in this list will be recomputed. p_exclude has sense
        #          | only if p_unindex is False and p_fields is not None.
        #  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        r = False
        # Manage unindexing
        if unindex:
            for index in self.values():
                changed = index.unindexObject(o)
                if changed: r = True
            # Remove it from p_self.all
            self.all.remove(o.iid)
            return r
        # Manage (re)indexing
        if indexes:
            # The list of indexes to update is given
            for index in indexes:
                changed = index.indexObject(o)
                if changed: r = True
        elif fields:
            # The list of field names is given
            if not exclude:
                # Index only fields as listed in p_fields
                for name in fields:
                    # Get the corresponding index
                    if name not in self:
                        raise self.Error(INDEX_NOT_FOUND % (name, self.name))
                    changed = self[name].indexObject(o)
                    if changed: r = True
            else:
                # Index only fields not being listed in p_fields
                for name, index in self.items():
                    if name in fields: continue
                    changed = index.indexObject(o)
                    if changed: r = True
        else:
            # Reindex all available indexes
            for index in self.values():
                changed = index.indexObject(o)
                if changed: r = True
            # Ensure the object is in p_self.all
            if r: self.all.insert(o.iid)
        return r
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
