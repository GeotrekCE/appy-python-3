# ------------------------------------------------------------------------------
from appy.pod.xhtml import tags, visitors
from appy.xml import XmlEnvironment, XmlParser, Escape

# ------------------------------------------------------------------------------
class XhtmlEnvironment(XmlEnvironment):
    def __init__(self):
        # Call the base constructor
        XmlEnvironment.__init__(self)
        # The parsing result will store a root Tag instance
        self.r = None
        # The currently walked tag (a tags.Tag or sub-class' instance)
        self.current = None
        # The current content (a tags.Content instance)
        self.content = None
        # Tags encountered so far, by type
        self.tags = {}
        # The main parser (see below)
        self.parser = None

    def addTag(self, tag):
        '''A new p_tag has been encountered. Add it in the environment's local
           data structures.'''
        # Store it as the current tag
        if not self.r:
            # It is the root tag
            self.r = tag
            isRoot = True
        else:
            isRoot = False
        self.current = tag
        # Store it in self.tags if walkable. Do not store the root tag: it is a
        # tag that was artificially added to ensure there is a single root tag.
        class_ = tag.__class__
        if not isRoot and class_.walkable:
            name = class_.__name__
            if name in self.tags:
                self.tags[name].append(tag)
            else:
                self.tags[name] = [tag]

# ------------------------------------------------------------------------------
class XhtmlParser(XmlParser):
    '''Creates a tree of Tag elements from a chunk of XHTML code as a string'''

    def __init__(self, env, caller, keepWithNext=0):
        XmlParser.__init__(self, env, caller)
        # Define the visitors that will walk the tree of tags we will build
        self.visitors = [visitors.TablesNormalizer()]
        if keepWithNext:
            self.visitors.append(visitors.KeepWithNext(keepWithNext))

    def startElement(self, elem, attrs):
        '''Manages the start of a tag'''
        env = self.env
        # Clean current content
        env.content = None
        # Create the corresponding Tag instance
        tag = tags.get(elem)(elem, attrs, parent=env.current)
        env.addTag(tag)

    def endElement(self, elem):
        '''Manages the end of a tag'''
        env = self.env
        # Clean current content
        env.content = None
        # We are back to p_elem's parent
        env.current = env.current.parent

    def characters(self, text):
        '''Manages text encountered within the current tag'''
        env = self.env
        # Ignore p_text if directly contained in a tag that is not supposed to
        # directly contain content. In that case, p_text is probably ignorable
        # whitespace.
        if env.current.structural: return
        # Xhtml-escape p_text and store it on the environment
        text = Escape.xml(text)
        if env.content:
            env.content.text += text
        else:
            # Create a Content instance to store p_text
            content = env.content = tags.Content(text)
            # Add content as child of the current tag
            tag = env.current
            if tag.children:
                tag.children.append(content)
            else:
                tag.children = [content]

    def endDocument(self):
        '''Converts p_self.env.r into a chunk of ODF code and store it in
           p_self.res.'''
        env = self.env
        # Accept the visitors
        for visitor in self.visitors:
            visitor.visit(env)
        self.res = env.r.asXhtml()
# ------------------------------------------------------------------------------
