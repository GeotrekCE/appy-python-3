'''Meta-class for a Appy workflow'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import collections

from appy.px import Px
from appy.model import Model
from appy.model.meta import Meta
from appy.model.workflow.state import State
from appy.model.workflow.transition import Transition
from appy.model.fields.phase import Page as FieldPage

# Errors - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
MULTIPLE_INITIAL_STATES = 'In workflow "%s", states "%s" and "%s" are both ' \
  'defined as being initial.'
NO_INITIAL_STATE = 'Workflow "%s" does not define any initial state.'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Workflow(Meta):
    '''Represents a Appy worflow'''

    # Attributes added on Appy workflows
    attributes = {'states': State, 'transitions': Transition}

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Model-construction-time methods
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # The following set of methods allow to build the model when making an app
    # or when starting the server.
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def __init__(self, class_, isBase=False, appOnly=False):
        Meta.__init__(self, class_, appOnly)
        # p_class_, representing a workflow, may be of 2 types:
        # ----------------------------------------------------------------------
        # "base" | A standard workflow from package appy.model.workflow.standard
        # ----------------------------------------------------------------------
        # "app"  | An original workflow defined in the app.
        # ----------------------------------------------------------------------
        # Unlike classes, standard workflows can't be overridden
        self.type = 'base' if isBase else 'app'
        # The concrete class for a workflow is p_class_ directly. Indeed,
        # workflows are never instantiated: we don't need to create a specific
        # concrete class like for classes.
        self.concrete = class_
        # Read states and transitions defined on this workflow
        self.readStatesAndTransitions()
        # At run-time, we need a single instance of this workflow, in order to
        # execute workflow-related methods defined as conditions and actions.
        # We create here this "prototypical" instance.
        if not appOnly: self.proto = class_()

    def readStatesAndTransitions(self):
        '''Create attributes related to states and transitions for this
           worflow.'''
        # ----------------------------------------------------------------------
        # The following attributes will be created.
        # "OD" is a shorthand for "OrderedDict".
        # ----------------------------------------------------------------------
        # Name              | Type       | Description
        # ----------------------------------------------------------------------
        # states            | OD         | The ordered dict of workflow states
        #                   |            | as appy.model.workflow.state.State
        #                   |            | instances.
        # ----------------------------------------------------------------------
        # transitions       | OD         | The ordered dict of workflow
        #                   |            | transitions as appy.model.workflow.\
        #                   |            | transition.Transition instances.
        # ----------------------------------------------------------------------
        # initialState      | State      | The workflow's initial state, that
        #                   |            | is aslo present among "states".
        # ----------------------------------------------------------------------
        # initialTransition | Transition | A virtual transition, named "_init_",
        #                   |            | added while loading the model, not
        #                   |            | present among "transitions" and that
        #                   |            | is triggered when the object is
        #                   |            | created, adding an initial entry in
        #                   |            | the object's history.
        # ----------------------------------------------------------------------
        states = collections.OrderedDict()
        transitions = collections.OrderedDict()
        initial = None
        Err = Model.Error
        for name, value in self.concrete.__dict__.items():
            if name.startswith('__'): continue
            if isinstance(value, State):
                # A state was found. Ensure its name is acceptable.
                self.checkAttributeName(name)
                # Late-initialize it
                value.init(self, name)
                # Store it
                states[name] = value
                if value.initial:
                    # There can be at most one initial state
                    if initial:
                        raise Err(MULTIPLE_INITIAL_STATES % \
                                  (self.name, initial.name, name))
                    initial = value
            elif isinstance(value, Transition):
                # A transition was found. Ensure its name is acceptable.
                self.checkAttributeName(name)
                # Late-initialize it
                value.init(self, name)
                # Store it
                transitions[name] = value
        # At least one initial state is required
        if not initial: raise Err(NO_INITIAL_STATE % self.name)
        self.states = states
        self.transitions = transitions
        self.initialState = initial
        # Create a Transition instance representing the initial transition
        self.initialTransition = tr = Transition((initial, initial))
        tr.init(self, '_init_')

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Run-time methods
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # The following set of methods allow to compute, at run-time,
    # workflow-dependent elements.
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def getRolesFor(self, o, permission):
        '''Gets the roles that are currently granted p_permission on this
           p_o(bject). r_ is a list of role names.'''
        state = self.states[o.state]
        return state.getRolesFor(permission)

    def getTransitions(self, o, includeFake=True, includeNotShowable=False,
                       grouped=True):
        '''Return transitions that the current user can trigger from the user
           interface, as a list of UiTransition instances.'''
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        #    includeFake     | If True, it retrieves transitions that the user
        #                    | can't trigger, but for which he needs to know for
        #                    | what reason he can't trigger it.
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # includeNotShowable | If True, it includes transitions for which
        #                    | show=False. Indeed, because "showability" is only
        #                    | a UI concern, and not a security concern, in some
        #                    | cases it has sense to set this parameter to True,
        #                    | because those transitions are triggerable from a
        #                    | security point of view.
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        #      grouped       | If True, transitions are grouped according to
        #                    | their "group" attribute, in a similar way to
        #                    | fields or searches.
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        r = []
        groups = {} # The already encountered groups of transitions
        page = FieldPage('workflow')
        currentState = o.state
        # Walk workflow transitions
        for transition in self.transitions.values():
            # Filter transitions that do not have currentState as start state
            if not transition.hasState(currentState, True): continue
            # Check if the transition can be triggered
            mayTrigger = transition.isTriggerable(o)
            # Compute the condition that will lead to including or not this
            # transition.
            includeIt = mayTrigger if not includeFake \
                        else mayTrigger or isinstance(mayTrigger, No) 
            if not includeNotShowable:
                includeIt = includeIt and transition.isShowable(o)
            if not includeIt: continue
            # Create the UiTransition instance
            ui = transition.ui(o, mayTrigger)
            # Add the transition into the result
            if not transition.group or not grouped:
                r.append(ui)
            else:
                # Insert the UiGroup instance corresponding to transition.group
                uiGroup = transition.group.insertInto(r, groups, page,
                                           o.class_.name, content='transitions')
                uiGroup.addElement(ui)
        return r

    def listStates(self, o):
        '''Returns the list of (not-isolated) translated names for states in
           this workflow.'''
        return [(state.name, o.translate(state.labelId)) \
                for state in self.states.values() if not state.isIsolated()]

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # PXs
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    # Displays transitions as icons or buttons for an object (variable "o")
    pxTransitions = Px('''
     <form var="transitions=workflow.getTransitions(o)" if="transitions"
           var2="formId='trigger_%s' % target.id; o=target;
                 backHook=backHook|None;"
           id=":formId" action=":'%s/onTrigger' % o.url"
           style="display: inline" method="post">
      <input type="hidden" name="transition"/>
      <input type="hidden" name="popup" value=":popup"/>
      <input type="hidden" name="nav" value=":req.nav or 'no'"/>
      <input type="hidden" name="page" value=":req.page or 'main')"/>
      <!-- Input field for storing the comment coming from the popup -->
      <textarea id="popupComment" name="popupComment" cols="30" rows="3"
                style="display:none"></textarea>
      <x for="transition in transitions">
       <!-- Render a transition or a group of transitions -->
       <x if="transition.type == 'transition'">:transition.pxView</x>
       <x if="transition.type == 'group'"
          var2="uiGroup=transition">:uiGroup.px</x>
      </x></form>''')
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
