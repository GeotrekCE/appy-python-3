# ~license~
# ------------------------------------------------------------------------------
from appy.px import Px
from appy.model.workflow import emptyDict, Role
from appy.model.fields.group import Group
from appy.model.workflow.state import State

# Errors - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
UNTRIGGERABLE = 'Transition "%s" on %s can\'t be triggered.'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Transition:
    '''Represents a workflow transition'''
    class Error(Exception): pass

    def __init__(self, states, condition=True, action=None, show=True,
                 confirm=False, group=None, icon=None, redirect=None,
                 historizeActionMessage=False):
        # In its simpler form, "states" is a list of 2 states:
        # (fromState, toState). But it can also be a list of several
        # (fromState, toState) sub-lists. This way, you may define only 1
        # transition at several places in the state-transition diagram. It may
        # be useful for "undo" transitions, for example.
        self.states = self.standardiseStates(states)
        self.condition = condition
        if isinstance(condition, str):
            # The condition specifies the name of a role
            self.condition = Role(condition)
        self.action = action
        self.show = show # If False, the end user will not be able to trigger
        # the transition. It will only be possible by code.
        self.confirm = confirm # If True, a confirm popup will show up.
        self.group = Group.get(group)
        # The user may specify a specific icon to show for this transition.
        self.icon = icon or 'transition'
        # If redirect is None, once the transition will be triggered, Appy will
        # perform an automatic redirect:
        # (a) if you were on some "view" page, Appy will redirect you to this
        #     page (thus refreshing it entirely);
        # (b) if you were in a list of objects, Appy will Ajax-refresh the row
        #     containing the object from which you triggered the transition.
        # Case (b) can be problematic if the transition modifies the list of
        # objects, or if it modifies other elements shown outside this list.
        # If you specify  redirect='page', case (a) will always apply.
        self.redirect = redirect
        # When a transition is triggered, the corresponding event is added in
        # the object's history. If p_historizeActionMessage is True, the message
        # returned by self.action (if any) will be appended to this event's
        # comment.
        self.historizeActionMessage = historizeActionMessage

    def init(self, workflow, name):
        '''Lazy initialisation'''
        self.workflow = workflow
        self.name = name
        self.labelId = '%s_%s' % (workflow.name, name)

    def __repr__(self):
        return '<transition %s::%s>' % (self.workflow.name, self.name)

    def standardiseStates(self, states):
        '''Get p_states as a list or a list of lists. Indeed, the user may also
           specify p_states as a tuple or tuple of tuples. Having lists allows
           us to easily perform changes in states if required.'''
        if isinstance(states[0], State):
            if isinstance(states, tuple): return list(states)
            return states
        return [[start, end] for start, end in states]

    def getEndStateName(self, wf, startStateName=None):
        '''Returns the name of p_self's end state. If p_self is a
           multi-transition, the name of a specific p_startStateName can be
           given.'''
        if self.isSingle():
            return self.states[1].getName(wf)
        else:
            for start, end in self.states:
                if not startStateName:
                    return end.getName(wf)
                else:
                    if start.getName(wf) == startStateName:
                        return end.getName(wf)

    def getUsedRoles(self):
        '''self.condition can specify a role'''
        res = []
        if isinstance(self.condition, Role):
            res.append(self.condition)
        return res

    def isSingle(self):
        '''If this transition is only defined between 2 states, returns True.
           Else, returns False.'''
        return isinstance(self.states[0], State)

    def addAction(self, action):
        '''Adds an p_action in self.action'''
        actions = self.action
        if not actions:
            self.action = action
        elif isinstance(actions, list):
            actions.append(action)
        elif isinstance(actions, tuple):
            self.action = list(actions)
            self.action.append(action)
        else: # A single action is already defined
            self.action = [actions, action]

    def _replaceStateIn(self, oldState, newState, states):
        '''Replace p_oldState by p_newState in p_states.'''
        if oldState not in states: return
        i = states.index(oldState)
        del states[i]
        states.insert(i, newState)

    def replaceState(self, oldState, newState):
        '''Replace p_oldState by p_newState in self.states.'''
        if self.isSingle():
            self._replaceStateIn(oldState, newState, self.states)
        else:
            for i in range(len(self.states)):
                self._replaceStateIn(oldState, newState, self.states[i])

    def removeState(self, state):
        '''For a multi-state transition, this method removes every state pair
           containing p_state.'''
        if self.isSingle():
            raise WorkflowException('To use for multi-transitions only')
        i = len(self.states) - 1
        while i >= 0:
            if state in self.states[i]:
                del self.states[i]
            i -= 1
        # This transition may become a single-state-pair transition.
        if len(self.states) == 1:
            self.states = self.states[0]

    def setState(self, state):
        '''Configure this transition as being an auto-transition on p_state.
           This can be useful if, when changing a workflow, one wants to remove
           a state by isolating him from the rest of the state diagram and
           disable some transitions by making them auto-transitions of this
           disabled state.'''
        self.states = [state, state]

    def isShowable(self, o):
        '''Is this transition showable ?'''
        return self.show(self.workflow, o) if callable(self.show) else self.show

    def hasState(self, state, isFrom):
        '''If p_isFrom is True, this method returns True if p_state is a
           starting state for p_self. If p_isFrom is False, this method returns
           True if p_state is an ending state for p_self.'''
        stateIndex = 1
        if isFrom:
            stateIndex = 0
        if self.isSingle():
            r = state == self.states[stateIndex]
        else:
            r = False
            for states in self.states:
                if states[stateIndex] == state:
                    r = True
                    break
        return r

    def replaceRoleInCondition(self, old, new):
        '''When self.condition is a tuple or list, this method replaces role
           p_old by p_new. p_old and p_new can be strings or Role instances.'''
        condition = self.condition
        if isinstance(old, Role): old = old.name
        # Ensure we have a list
        if isinstance(condition, tuple): condition = list(condition)
        if not isinstance(condition, list):
            raise WorkflowException('m_replaceRoleInCondition can only be ' \
              'used if transition.condition is a sequence.')
        # Find the p_old role
        i = -1
        found = False
        for cond in condition:
            i += 1
            if isinstance(cond, Role): cond = cond.name
            if cond == old:
                found = True
                break
        if not found: return
        del condition[i]
        condition.insert(i, new)
        self.condition = tuple(condition)

    def isTriggerable(self, o, secure=True):
        '''Can this transition be triggered on p_o ?'''
        wf = wf.__instance__ # We need the prototypical instance here
        # Checks that the current state of the object is a start state for this
        # transition.
        objState = obj.State(name=False)
        if self.isSingle():
            if objState != self.states[0]: return False
        else:
            startFound = False
            for startState, stopState in self.states:
                if startState == objState:
                    startFound = True
                    break
            if not startFound: return False
        # Check that the condition is met, excepted if noSecurity is True
        if noSecurity: return True
        user = obj.getTool().getUser()
        if isinstance(self.condition, Role):
            # Condition is a role. Transition may be triggered if the user has
            # this role.
            return user.hasRole(self.condition.name, obj)
        elif callable(self.condition):
            return self.condition(wf, obj.appy())
        elif type(self.condition) in (tuple, list):
            # It is a list of roles and/or functions. Transition may be
            # triggered if user has at least one of those roles and if all
            # functions return True.
            hasRole = None
            for condition in self.condition:
                # "Unwrap" role names from Role instances
                if isinstance(condition, Role): condition = condition.name
                if isinstance(condition, str): # It is a role
                    if hasRole is None:
                        hasRole = False
                    if user.hasRole(condition, obj):
                        hasRole = True
                else: # It is a method
                    res = condition(wf, obj.appy())
                    if not res: return res # False or a No instance
            if hasRole != False:
                return True
        else:
            return bool(self.condition)

    def executeAction(self, o):
        '''Executes the action related to this transition'''
        msg = ''
        proto = self.workflow.proto
        if type(self.action) in (tuple, list):
            # We need to execute a list of actions
            for act in self.action:
                msgPart = act(proto, o)
                if msgPart: msg += msgPart
        else: # We execute a single action only
            msgPart = self.action(proto, o)
            if msgPart: msg += msgPart
        return msg

    def getTargetState(self, o):
        '''Gets the target state for this transition'''
        # For a single transition, a single possibility
        if self.isSingle(): return self.states[1]
        sourceName = o.state
        for source, target in self.states:
            if source.name == sourceName:
                return target

    def trigger(self, o, comment=None, doAction=True, doHistory=True,
                doSay=True, reindex=True, secure=True, data=None,
                forceTarget=None):
        '''This method triggers this transition on some p_o(bject). If
           p_doAction is False, the action that must normally be executed after
           the transition has been triggered will not be executed. If
           p_doHistory is False, there will be no trace from this transition
           triggering in p_o's history. If p_doSay is False, we consider the
           transition as being triggered programmatically, and no message is
           returned to the user. If p_reindex is False, object reindexing will
           be performed by the caller method. If p_data is specified, it is a
           dict containing custom data that will be integrated into the history
           event.'''
        # Is that the special _init_ transition ?
        isInit = self.name == '_init_'
        # "Triggerability" and security checks
        if not isInit and not self.isTriggerable(o, secure=secure):
            raise Transition.Error(UNTRIGGERABLE % (name, o.url))
        # Identify the target state for this transition
        target = forceTarget or self.getTargetState(o)
        # Add the event in the object history
        event = o.history.add('Trigger', target.name, transition=self.name,
                              comment=comment, show=False)
        # Remember the source state, it will be necessary for executing the
        # common action.
        fromState = o.state if not isInit else None
        # Execute the action that is common to all transitions, if defined. It
        # is named "onTrigger" on the workflow class by convention. This common
        # action is executed before the transition-specific action (if any).
        proto = self.workflow.proto
        if doAction and hasattr(proto, 'onTrigger'):
            proto.onTrigger(o, self.name, fromState)
        # Execute the transition-specific action
        msg = self.executeAction(o) if doAction and self.action else None
        # Append the action message to the history event when relevant
        if doHistory and msg and self.historizeActionMessage:
            event.completeComment(msg)
        # Reindex the object if required. Not only security-related indexes
        # (Allowed, State) need to be updated here.
        if reindex and not isInit and not o.isTemp(): o.reindex()
        # Return a message to the user if needed
        if not doSay: return
        return msg or o.translate('object_saved')

    def ui(self, o, mayTrigger):
        '''Return the UiTransition instance corresponding to p_self'''
        return UiTransition(self, o, mayTrigger)

    def onUiRequest(self, obj, wf, name, req):
        '''Executed when a user wants to trigger this transition from the UI'''
        tool = obj.getTool()
        # Trigger the transition
        msg = self.trigger(name, obj, wf, req.get('popupComment', ''),
                           reindex=False)
        # Reindex obj if required
        if not obj.isTemporary(): obj.reindex()
        # If we are called from an Ajax request, simply return msg
        if hasattr(req, 'pxContext') and req.pxContext['ajax']: return msg
        # If we are viewing the object and if the logged user looses the
        # permission to view it, redirect the user to its home page.
        if msg: obj.say(msg)
        # Return to obj/view, excepted if the object is not viewable anymore
        if obj.mayView():
            back = obj.getUrl(nav=req.nav or 'no',
                              page=req.page or 'main',
                              popup=req.popup == 'True')
        else:
            back = tool.computeHomePage()
        tool.goto(back)

    @staticmethod
    def getBack(workflow, transition):
        '''Returns the name of the transition (in p_workflow) that "cancels" the
           triggering of p_transition and allows to go back to p_transition's
           start state.'''
        # Get the end state(s) of p_transition
        transition = getattr(workflow, transition)
        # Browse all transitions and find the one starting at p_transition's end
        # state and coming back to p_transition's start state.
        for trName, tr in workflow.__dict__.items():
            if not isinstance(tr, Transition) or (tr == transition): continue
            if transition.isSingle():
                if tr.hasState(transition.states[1], True) and \
                   tr.hasState(transition.states[0], False): return trName
            else:
                startOk = False
                endOk = False
                for start, end in transition.states:
                    if (not startOk) and tr.hasState(end, True):
                        startOk = True
                    if (not endOk) and tr.hasState(start, False):
                        endOk = True
                    if startOk and endOk: return trName

# ------------------------------------------------------------------------------
class UiTransition:
    '''Represents a widget that displays a transition'''
    px = Px('''
     <x var="label=transition.title;
             inButtons=layout == 'buttons';
             css=ztool.getButtonCss(label, inButtons)">

      <!-- Real button -->
      <input if="transition.mayTrigger" type="button" class=":css"
             var="back=transition.getBackHook(zobj, inButtons, q, backHook)"
             id=":transition.name" style=":url(transition.icon, bg=True)"
             value=":label"
             onclick=":'triggerTransition(%s,this,%s,%s)' % \
                        (q(formId), q(transition.confirm), back)"/>

      <!-- Fake button, explaining why the transition can't be triggered -->
      <input if="not transition.mayTrigger" type="button"
             class=":'fake %s' % css" style=":url('fake', bg=True)"
             value=":label" title=":transition.reason"/></x>''')

    def __init__(self, transition, o, mayTrigger):
        self.name = transition.name
        self.transition = transition
        self.type = 'transition'
        self.icon = transition.icon
        self.title = o.getLabel(self.name, field=False)
        if transition.confirm:
            msg = o.translate('%s_confirm' % label, blankOnError=True) or \
                  o.translate('action_confirm')
            self.confirm = msg
        else:
            self.confirm = ''
        # May this transition be triggered via the UI?
        self.mayTrigger = True
        self.reason = ''
        if not mayTrigger:
            self.mayTrigger = False
            self.reason = mayTrigger.msg
        # Required by the UiGroup
        self.colspan = 1

    def getBackHook(self, o, inButtons, q, backHook=None):
        '''If, when the transition has been triggered, we must ajax-refresh some
           part of the page, this method will return the ID of the corresponding
           DOM node. Else (ie, the entire page needs to be refreshed), it
           returns None.'''
        return backHook or q(o.id) \
               if inButtons and (self.transition.redirect != 'page') else 'null'
# ------------------------------------------------------------------------------
