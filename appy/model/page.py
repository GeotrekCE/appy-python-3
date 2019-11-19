# ~license~

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.px import Px
from appy.model.base import Base
from appy.all import String, Rich, Ref, autoref, Layouts, Show

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
EXPRESSION_ERROR = 'error while evaluating page expression: %s'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Page(Base):
    '''Base class representing a web page'''
    pa = {'label': 'Page'}
    # Pages are not indexed by default
    indexable = False

    # The page title
    title = String(show='edit', multiplicity=(1,1), indexed=True, **pa)

    # The page content
    content = Rich(layouts='f')

    # A page can contain sub-pages
    def showSubPages(self):
        '''Show the field allowing to edit sub-pages'''
        if self.user.hasRole('Manager'): return 'view'

    pages = Ref(None, multiplicity=(0,None), add=True, link=False,
      composite=True, back=Ref(attribute='parent', show=False, **pa),
      show=showSubPages, navigable=True, **pa)

    # If this Python expression returns False, the page can't be viewed
    def showExpression(self):
        '''Show the expression to managers only'''
        # Do not show it on "view" if empty
        if self.isEmpty('expression'): return Show.V_
        return self.user.hasRole('Manager')

    expression = String(layouts=Layouts.d, show=showExpression, **pa)

    def showPortlet(self):
        '''Never show the portlet for a page'''
        return

    def mayView(self):
        '''In addition to the workflow, evaluating p_self.expression, if
           defined, determines p_self's visibility.'''
        expression = self.expression
        if not expression: return True
        user = self.user
        try:
            return eval(expression)
        except Exception as err:
            self.log(EXPRESSION_ERROR % str(err), type='error')
            return

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
    #  PXs
    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    # This selector allows to choose one root page among tool.pages
    pxSelector = Px('''
      <select onchange="gotoURL(this)">
       <option value="">:_('goto_link')</option>
       <option for="page in tool.pages" if="guard.mayView(page)"
               value=":page.url">:page.title</option>
      </select>''',

     js='''
       function gotoURL(select) {
         var url = select.value
         if (url) goto(url);
       }''')

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
autoref(Page, Page.pages)
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
