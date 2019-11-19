'''Operators for object searches'''

# ~license~

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from BTrees.IIBTree import multiunion, intersection

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Searching objects in the database is done via method
# appy.model.base.Base::search and variants. This method accepts keyword
# arguments to define such searches. These arguments mention indexed fields.
# Workflow state is one example of default indexed field. For example, searching
# all users being active can be done via any object, like this:
#
#               activeUsers = o.search('User', state='active')
#
# On this example, keyword argument named "state" takes the value "active".
# Instead of specifying such a single value, one may use operators to define a
# set or range of values. Such operators are defined in this module. For
# example, the "or" operator could be used as value for keyword argument "state"
# to retrieve users being in states "active" or "inactive", like this:
#
#         moreUsers = o.search('User', state=or_('active', 'inactive'))
#
# As PEP8 recommands it, the operator, also being a Python reserved keyword, is
# suffixed with an underscore. The search hereabove retrieves all users being
# active or inactive.
#
# For multivalued fields, operator "and" can also be used. In the following
# example, we suppose the existence of an indexed field named "attributes" on
# class User, that can hold one or more values among
#
#                      ["married", "employed", "faithful"]
# 
# Getting all users being married as well as employed, being active or not, is
# done via:
#
# someUsers = o.search('User', state=or_('active', 'inactive'),
#                              attributes=and_('married', 'employed'))
#
# The "in" operator allow to defined ranges. Getting all users having a QI
# between 130 and 155 is expressed like this:
#
#                 smartUsers = o.search('User', qi=in_(130, 155))
#
# The "not" operator allows to define all users not statisfying some condition
# based on some indexed field. Suppose the user workflow defines these states:
# active, inactive and registered (=requires validation from a Manager).
# Getting all users not being inactive can be done via:
#
#           awareUsers = o.search('User', state=not_('inactive')
# 
# The "search" method can accept any number of keyword arguments; values for
# these latters can be simple values or operator values.
#
# Every such operator corresponds to a class in this module. All these classes
# inherit from an abstract base class named Operator. Using operators like in
# the previous examples creates instances of the concrete classes from this
# module. These classes are made available in the appy.all module, so are
# available in any module from your app where you have used the standard import
# statement:
#                           from appy.all import *

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
RANGE_KO = 'Exactly 2 values must be provided: the lower and upper bounds.'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Operator:
    '''Abstract base class for any operator'''

    # An operator being "negative" produces a set of objects that must be
    # excluded from the result.
    negative = False

    def __init__(self, *values):
        # The list of p_values onto which to operator is applied
        self.values = values

    def apply(self, index, rs):
        '''Apply the operator on p_index and return the result. The global
           result set computed so far can be available in p_rs.'''
        # More precisely, the method must return a tuple (result, rsUpdated):
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        #  result   | Is the set of matching object IDs after having applied the
        #           | operator instance.
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # rsUpdated | Is True if the operator has already updated the global
        #           | resultset p_rs. It can be the case for some optimizations.
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def __repr__(self):
        '''Returns p_self's string representation'''
        stringValues = [str(v) for v in self.values]
        return '<"%s" operator on %s>' % (self.__class__.__name__[:-1],
                                          ', '.join(stringValues))

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class or_(Operator):

    # Result sets having a size lower than this size are considered "small"
    RS_LIMIT = 200

    def apply(self, index, rs):
        '''Apply this "or" operator instance on values stored in p_index'''
        r = []
        for value in self.values:
            ids = index.byValue.get(value, None)
            if ids:
                r.append(ids)
        # If the global resultset p_rs is small, starting with intersecting
        # every set of ids with it and doing the union later is faster than
        # creating a multiunion first.
        if (rs is not None) and (len(rs) < or_.RS_LIMIT):
            sets = []
            for ids in r:
                sets.append(intersection(rs, ids))
            r = multiunion(sets)
            rsUpdated = True
        else:
            r = multiunion(r)
            rsUpdated = False
        return r, rsUpdated

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class and_(Operator):
    def apply(self, index, rs):
        '''Apply this "and" operator instance on values stored in p_index'''
        r = []
        for value in self.values:
            ids = index.byValue.get(value, None)
            if ids is None:
                # There is no match at all
                return None, True
            r.append(ids)
        # Set smaller sets first
        if len(r) > 2:
            r.sort(key=len)
        # Intersect every set of ids with the global resultset p_rs
        for ids in r:
            rs = intersection(rs, ids)
            if not rs:
                return None, True
        return rs, True

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class in_(Operator):
    '''Defines a range of values by specifying lower and upper bounds'''
    # ~~~
    # If you want to specify a range whose upper bound is defined, but with no
    # lower bound, use value None as lower bound, as in: qi=in_(None, 155).
    # ~~~
    # If you want to specify a range whose lower bound is defined, but with no
    # upper bound, use value None as upper bound, as in: qi=in_(100, None).
    # ~~~

    def __init__(self, *values):
        if len(values) != 2:
            raise Exception(RANGE_KO)
        Operator.__init__(self, *values)

    def apply(self, index, rs):
        '''Apply this "in" operator instance on values stored in p_index'''
        # Unwrap the bounds from p_self.values
        lo, hi = self.values
        if hi:
            sets = index.byValue.values(lo, hi)
        else:
            sets = index.byValue.values(lo)
        if len(sets) == 1:
            r = sets[0]
        else:
            r = multiunion(sets)
        return r, False

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class not_(Operator):

    # The "not" operator is "negative"
    negative = True

    def apply(self, index, rs):
        '''Apply this "not" operator instance on values stored in p_index, in
           the same way as a "or". Afterwards, the result of this "not" operator
           will be substracted from the global resultset.'''
        r = []
        for value in self.values:
            ids = index.byValue.get(value, None)
            if ids:
                r.append(ids)
        return multiunion(r), False
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
