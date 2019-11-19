# ~license~

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import inspect
from appy.px import Px
from appy.ui.js import Quote
from appy.model.base import Base
from appy.model.fields import Field
from appy.server.request import Request

# Errors - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
UNTRAVERSABLE = 'Untraversable element "%s" while traversing %s.'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class NotFound(Exception):
    '''Exception raised when an URL path does not correspond to an existing (or
       visible) object.'''

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Traversal:
    '''Traverses the path of an URL and executes the corresponding code'''
    Error = NotFound

    # Let's define an URL as
    #               <protocol>://<domain name><path>
    # "Traversing" is the process of splitting <path> into parts and finding a
    # correpondance between these parts and database objects, their attributes
    # and methods. Here are some examples.
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # <path> content | Description
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # /              | The root URL
    # /tool/view     | Attribute "view" on object having id "tool"
    # /a/b/c/d?var=1 | Evaluating attribute or method "b" on object "a" produces
    #                | a partial result "r". Then, evaluating "c" on "r"
    #                | produces "r2". Evaluating "d" or "r2" produces the final
    #                | result. While traversing all these parts, request
    #                | variable named "var" holding value "1", is available.
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # "Traversing" thus finally produces a result as a page that is returned to
    # the browser.
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __init__(self, handler=None, other=None):
        # A traversal can be initialised from another one
        if other:
            self.init(other)
            return
        # Perform standard initialisation
        self.handler = handler
        self.req = handler.req
        # The currently logged user
        self.user = handler.guard.user
        # The current result of traversing
        self.r = None
        # The last encountered object
        self.o = None
        # The last encountered field
        self.field = None
        # The PX context
        self.context = None

    def init(self, other):
        for name, value in other.__dict__.items():
            setattr(self, name, value)

    def createContext(self, layout='view'):
        '''Create and return a PX context for rendering p_o on p_layout'''
        return Px.createContext(self, layout, Quote)

    def asObjectId(self, part):
        '''Interpret p_part as an object ID and return this ID as
           * a positive integer (for a definitive object having a standard ID);
           * a negative integer (for a temporary object);
           * p_part itself if it does not represent a (positive or negative)
             integer: it is assumed to represent a custom string ID for a
             definitive object.
        '''
        if part.isdigit() or (part.startswith('-') and part[1:].isdigit()):
            return int(part)
        return part

    def getObject(self, part):
        '''Tries to get an object from "part" which is a part of the URL path'''
        if part:
            id = self.asObjectId(part)
            r = self.handler.server.database.getObject(self.handler, id)
            if not r: raise NotFound(self.handler.path)
        else:
            # If "part" is empty, (path is "/"), use the tool as default object
            r = self.handler.tool
        # Check if the user is allowed to consult this object
        self.handler.guard.allows(r, raiseError=True)
        return r

    def getLayout(self, pxName):
        '''Determine the layout type from the currently traversed PX'''
        return pxName

    def allowTraversal(self, info, o, name, raiseError=True):
        '''Raise an exception if the user is not allowed to traverse this
           p_o(bject). Traversal info is given in p_info.'''
        if isinstance(info, bool):
            r = info
        elif isinstance(info, str):
            if ':' not in info:
                # This is a role: the user must have it
                r = self.user.hasRole(info)
            else:
                type, info = info.split(':', maxsplit=1)
                if type == 'perm':
                    # The user must have this permission on p_o
                    r = o.allows(permission=info)
                elif type == 'user':
                    # The user must be the one whose login is in "info"
                    r = self.user.login == info
        else:
            # A tuple or list of logically OR'ed infos. Having at least one of
            # the listed prerogatives allows the user to traverse.
            r = False
            for inf in info:
                if self.allowTraversal(inf, o, name, raiseError=False):
                    r = True
                    break
        # Return the result or raise an Unauthorized exception if p_raiseError
        # is True and the object can't be traversed.
        if raiseError and not r:
            message = UNTRAVERSABLE % (name, '/'.join(self.handler.parts))
            raise self.handler.guard.Error(message)
        return r

    def getTraversalInfo(self, previous, name, current):
        '''Get traversal info about p_previous.<p_name> = p_current'''

        # Do we have traversal information ? p_previous can be an object, a
        # field, a module...
        traverse = getattr(previous, 'traverse', None)
        # Is p_name mentioned in the traversal info ?
        if traverse and (name in traverse):
            # Yes: retrieve "traverse info" from it
            r = traverse[name]
        else:
            # No: determine default "traverse info" based on p_current's type
            if isinstance(current, Field):
                # One may traverse it if he has the read permission on the
                # related object
                r = 'perm:%s' % current.readPermission
            elif isinstance(current, Px):
                # A PX is traversable by default
                r = True
            else:
                # Any other element (method, attribute, property...) is not
                # traversable by default.
                r = False
        return r

    def executeMethod(self, method):
        '''Execute m_method and return the result. The args potentially given to
           the method may vary.'''
        # Is that a method on a field ?
        if hasattr(method, '__self__') and isinstance(method.__self__, Field):
            # Call the method with the current object as unique arg
            r = method(self.o)
        else:
            # Execute it without arg or with the handler as unique arg
            try:
                r = method()
            except TypeError as te:
                # Try to call it with the handler as arg. Indeed, some
                # callable objects do not have any context (ie, class or
                # static methods) and require the handler as arg.
                r = method(self.handler)
        return r

    def executePx(self, name, px):
        '''Renders this p_px, whose p_name is given'''
        # Firstly, create or update the PX context
        layout = self.getLayout(name)
        if not self.context:
            self.context = self.createContext(layout)
        else:
            # Update the existing context
            self.context.o = self.o
            self.context.field = self.field
            self.context.layout = layout
        # Secondly, execute the tied action if defined
        actionName = self.req.action
        if actionName:
            # Execute this action by performing a sub-traversal
            handler = self.handler
            sub = Traversal(other=self)
            sub.r = sub.field or sub.o
            # A database commit will probably be required
            handler.commit = True
            # Run the sub-traversal
            msg = sub.run(actionName.split('*'))
            if msg:
                # Set a special header in the response for displaying this
                # message.
                handler.resp.setHeader('Appy-Message', msg)
        # Finally, call the PX
        return px(self.context)

    def managePart(self, previous, name, current):
        '''Manage the currently traversed element p_current, named p_name, after
           p_previous has already been traversed.

                       p_previous.<p_name> = p_current
        '''
        # Compute information allowing to determine if the user is allowed to
        # perform such traversal.
        info = self.getTraversalInfo(previous, name, current)
        # Raise an Unauthorized exception if the user is not allowed to do it
        self.allowTraversal(info, self.o, name)
        # "Execute" the p_current object
        if isinstance(current, Px):
            # p_current is a PX: render it in p_self.r
            self.r = self.executePx(name, current)
        elif callable(current) and not inspect.isclass(current):
            # Execute method "current"
            self.r = self.executeMethod(current)
        else:
            # Ensure p_current is already in p_self.r. This may not be the case
            # at the end of the traversal, if we add a default value.
            self.r = current

    def getPart(self, part):
        '''Get the attribute or method corresponding to p_part on the current
           result in p_self.r.'''
        # If p_self.r is an object and p_part corresponds to a field on this
        # object, return this field.
        if isinstance(self.r, Base):
            field = self.r.getField(part)
            if field:
                self.field = field
                return field
        # Try to get an attribute or method on p_self.r named p_part
        r = getattr(self.r, part, None)
        if r is None:
            raise NotFound(self.handler.path)
        if isinstance(r, Base):
            self.o = r
            self.field = None
        return r

    def run(self, parts=None):
        '''Traverses p_self.handler.path, splitted into p_self.handler.parts'''
        parts = parts or self.handler.parts
        if not parts:
            # There is nothing to traverse. Define the tool as the default
            # object to traverse.
            self.r = self.o = self.getObject(None)
        else:
            # Traverse URL parts
            length = len(parts)
            i = 0
            # Define the previously traversed part. It is None for a main
            # traversal, or an already filled self.r in the case of a
            # sub-traversal.
            previous = self.r
            while i < length:
                # Get and manage the next part
                part = parts[i]
                # If we are at the start of the traversal, and "r" is still
                # None, "part" must correspond to an object ID.
                if self.r is None:
                    self.r = self.o = self.getObject(part)
                # Manage any not-empty part
                elif part:
                    # Try to get the attribute or method named "part" on self.r
                    self.r = self.getPart(part)
                    # Manage this part
                    self.managePart(previous, part, self.r)
                i += 1
                previous = self.r
        # If self.r is an object, call the default PX on it
        if isinstance(self.r, Base):
            self.managePart(self.r, 'view', self.r.default)
        return self.r
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
