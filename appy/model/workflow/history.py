'''This module defines classes allowing to store an object's history'''

# ~license~

# Most of an object's history is related to its workflow. This is why this
# module lies within appy.model.workflow. That being said, object history also
# stores not-workflow-based events like data changes.

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import persistent
from DateTime import DateTime
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping

from appy.px import Px

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class EventIterator:
    '''Iterator for history events'''

    def __init__(self, history, eventType=None, condition=None,
                 context=None, chronological=False):
        # The history containing the events to walk
        self.history = history
        # The types of events to walk. None means that all types are walked.
        # When specified, p_eventType must be the name of a concrete Event
        # class, or a list/tuple of such class names.
        self.eventType = (eventType,) if isinstance(eventType, str) \
                                      else eventType
        # An additional condition, as a Python expression (getting "event" in
        # its context) that will dismiss the event if evaluated to False.
        self.condition = condition
        # A context that will be given to the condition
        self.context = context
        # If chronological is True, events are walked in chronological order.
        # Else, they are walked in their standard, anti-chronological order.
        self.chronological = chronological
        # The index of the currently walked event
        self.i = len(history) - 1 if chronological else 0

    def increment(self):
        '''Increment p_self.i, or decrement it if we walk events in
           chronological order.'''
        if self.chronological:
            self.i -= 1
        else:
            self.i += 1

    def typeMatches(self, event):
        '''Has p_event the correct type according to p_self.eventType ?'''
        # If no event type is defined, p_event matches
        if self.eventType is None: return True
        return event.__class__.__name__ in self.eventType

    def conditionMatches(self, event):
        '''Does p_event matches p_self.condition ?'''
        # If no condition is defined, p_event matches
        if self.condition is None: return True
        # Update the evaluation context when appropriate
        if self.context:
            locals().update(context)
        return eval(self.condition)

    def __iter__(self): return self
    def __next__(self):
        '''Return the next matching event'''
        try:
            event = self.history[self.i]
        except IndexError:
            # There are no more events, we have walked them all
            raise StopIteration
        # Does this event match ?
        if event.show and \
           self.typeMatches(event) and self.conditionMatches(event):
            # Yes
            self.increment()
            return event
        else:
            # Try to return the next element
            self.increment()
            return self.__next__()

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Event(persistent.Persistent):
    '''An object's history is made of events'''
    # A format for representing dates at various (non ui) places
    dateFormat = '%Y/%m/%d %H:%M'

    def __init__(self, login, state, date, show=True, comment=None):
        # The login of the user that has triggered the event
        self.login = login
        # The name of the state into which the object is after the event
        # occurred. It means that an object's current state is stored in this
        # attribute, on the most recent event in its history.
        self.state = state
        # When did this event occur ?
        self.date = date
        # Some events may be hidden
        self.show = show
        # A textual optional comment for the event
        self.comment = comment

    def completeComment(self, comment):
        '''Appends p_comment to the existing p_self.comment'''
        if not self.comment:
            self.comment = comment
        else:
            self.comment =  '%s<br/><br/>%s' % (self.comment, comment)

    def getTypeName(self):
        '''Return the class name, possibly completed with sub-class-specific
           information.'''
        return self.__class__.__name__

    def __repr__(self):
        '''String representation'''
        date = self.date.strftime(Event.dateFormat)
        return '<%s by %s on %s, state %s>' % \
               (self.getTypeName(), self.login, date, self.state)

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Trigger(Event):
    '''This event represents a transition being triggered'''

    def __init__(self, login, state, date, **params):
        # Extract the name of the transition from p_params
        self.transition = params.pop('transition')
        Event.__init__(self, login, state, date, **params)

    def getTypeName(self):
        '''Return the class name and the transition name'''
        return 'Trigger %s' % self.transition

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Action(Event):
    '''This event represents an action being performed'''

    def __init__(self, login, state, date, action, **params):
        # Extract the name of the action from p_params
        self.action = params.pop('action')
        Event.__init__(self, login, state, date, **params)

    def getTypeName(self):
        '''Return the class name and the transition name.'''
        return 'Action %s' % self.action

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Change(Event):
    '''This event represents a data change'''

    def __init__(self, login, state, date, **params):
        # Extract changed fields from p_params. Attribute "changes" stores, in a
        # dict, the previous values of fields whose values have changed. If the
        # dict's key is of type...
        # ----------------------------------------------------------------------
        # str   | it corresponds to the name of the field;
        # tuple | it corresponds to a tuple (s_name, s_language) and stores the
        #       | part of a multilingual field corresponding to s_language.
        # ----------------------------------------------------------------------
        self.changes = PersistentMapping(params.pop('changes'))
        Event.__init__(self, login, state, date, **params)

    def hasField(self, name):
        '''Is there, within p_self's changes, a change related to a field whose
           name is p_name ?'''
        if name in self.changes: return True
        # Search for a key of the form (name, x)
        for key in self.changes.keys():
            if isinstance(key, tuple) and (key[0] == name):
                return True

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Link(Event):
    '''Represents a link, via a Ref field, between 2 objects. The event is
       stored in the source object's history.'''
    # Although it may seem similar to a Change, it does not inherit from it.
    # Indeed, the complete list of previously linked objects is not stored:
    # instead, the title of the newly linked object is set as comment in this
    # Link event.

class Unlink(Event):
    '''Represents an object being unlinked from another one via a Ref field'''

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class History(PersistentList):
    '''Object history is implemented as a list, sorted in antichronological
       order, of history events.'''

    view = Px('''
     <div if="not o.isTemp()"
       var2="history=o.history;
             hasHistory=not history.isEmpty();
             collapsible=collapsible|True;
             collapse=ui.Collapsible('objectHistory', req) \
                      if collapsible else None">
      <table width="100%" class="header" cellpadding="0" cellspacing="0">
       <tr>
        <td colspan="2" class="by">
         <!-- Plus/minus icon for accessing history -->
         <x if="hasHistory and collapsible"><x>:collapse.px</x>
          <x>:_('object_history')</x> &mdash; 
         </x>

         <!-- Creator and last modification date -->
         <x>:_('Base_creator')</x> 
          <x>:user.getTitleFromLogin(o.creator)</x> 

         <!-- Creation and last modification dates -->
         <x>:_('Base_created')</x> 
         <x var="created=o.created; modified=o.modified">
          <x>:tool.Date.format(tool, created, withHour=True)</x>
          <x if="modified != created">&mdash;
           <x>:_('Base_modified')</x>
           <x>:tool.Date.format(tool, modified, withHour=True)</x>
          </x>
         </x>

         <!-- State -->
         <x> &mdash; <x>:_('Base_state')</x> : 
            <b>:_(o.getLabel(o.state, field=False))</b></x>
        </td>
       </tr>

       <!-- History entries -->
       <tr if="hasHistory">
        <td colspan="2">
         <span id=":collapse.id"
          style=":collapsible and collapse.style or ''">:history.pxEvents</span>
        </td>
       </tr>
      </table>
     </div>''')

    def __init__(self, o):
        PersistentList.__init__(self)
        # A reference to the object for which p_self is the history
        self.o = o
        # The last time the object has been modified
        self.modified = None

    def show(self):
        '''May the user view history ?'''
        # Method "showHistory" can be defined on the objet
        class_ = self.o.class_.python
        show = getattr(class_, 'showHistory', None)
        return show(self.o) if show and callable(show) else show

    def add(self, type, state=None, **params):
        ''''Adds a new event of p_type ("Trigger", "Action" or "Change") into
            the history.'''
        # Get the login of the user performing the action
        login = self.o.user.login
        # For a trigger event, p_state is the new object state after the
        # transition has been triggered. p_state is a name (string) and not a
        # State instance. The name of the triggering transition must be in
        # p_params, at key "transition".
        # For a change event, no state is given, because there is no state
        # change, but we will copy, on the change event, the state from the
        # previous event. That way, the last event in the history will always
        # store the object's current state.
        state = state or self[0].state
        # Create the event
        event = eval(type)(login, state, DateTime(), **params)
        # Insert it at the first place within the anti-chronological list
        self.insert(0, event)
        # Initialise self.modified if still None
        if self.modified is None: self.modified = event.date
        return event

    def iter(self, **kwargs):
        '''Returns an iterator for browsing p_self's events'''
        return EventIterator(self, **kwargs)

    def isEmpty(self, name=None):
        '''Is this history empty ? If p_name is not None, the question becomes:
           has p_self.o an history for field named p_name ?'''
        # An history containing a single entry is considered empty: this is the
        # special _init_ virtual transition representing the object creation.
        if len(self) == 1: return True
        # Return False if the user can't consult the history
        if not self.show(): return
        # At this point, the complete history can be considered not empty
        if name is None: return True
        # Check if history is available for field named p_name
        empty = True
        for event in self.iter(eventType='Change', \
                               condition="event.hasField('%s')" % name):
            # If we are here, at least one change concerns the field
            empty = False
            break
        return empty

    def getCurrentValues(self, o, fields):
        '''Called before updating p_o, this method remembers, for every
           historized field from p_fields, its current value.'''
        r = {} # ~{s_fieldName: currentValue}~
        # p_fields can be a list of fields or a single field
        fields = fields if isinstance(fields, list) else [fields]
        # Browse fields
        for field in fields:
            if not field.getAttribute(o, 'historized'): continue
            r[field.name] = field.getValue(o)
        return r

    def historize(self, previousValues):
        '''Records, in self.o's history, potential changes on historized fields.
           p_previousValues contains the values, before an update, of the
           historized fields, while p_self.o already contains the (potentially)
           modified values.'''
        o = self.o
        # Remove, from previousValues, any value that was not changed
        for name, prev in previousValues.items():
            field = o.getField(name)
            curr = field.getValue(o)
            try:
                if (prev == curr) or ((prev is None) and (curr == '')) or \
                   ((prev == '') and (curr is None)):
                    del(previousValues[name])
                    continue
            except UnicodeDecodeError:
                # The string comparisons above may imply silent encoding-related
                # conversions that may produce this exception.
                continue
            # The previous value may need to be formatted
            if field.type == 'Ref':
                previousValues[name] = [tied.getShownValue('title') \
                                        for tied in previousValues[name]]
            elif field.type == 'String':
                languages = field.getAttribute(o, 'languages')
                if len(languages) > 1:
                    # Consider every language-specific value as a first-class
                    # value.
                    del(previousValues[name])
                    for lg in languages:
                        lgPrev = prev.get(lg)
                        lgCurr = curr.get(lg)
                        if lgPrev == lgCurr: continue
                        previousValues['%s-%s' % (name, lg)] = lgPrev
        # Add the entry in the history (if not empty)
        if previousValues:
            self.add('Change', changes=previousValues)

    def getEvents(self, type, notBefore=None):
        '''Gets a subset of history events of some p_type. If specified, p_type
           must be the name of a concrete Event class or a list/tuple of such
           names.'''
        cond = 'not notBefore or (event.date >= notBefore)'
        return [event for event in self.iter(eventType=type, condition=cond, \
                                             context={'notBefore':notBefore})]
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
