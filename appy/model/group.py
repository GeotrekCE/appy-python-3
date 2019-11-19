# ~license~

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy import Config
from appy.model.base import Base
from appy.model.user import User
from appy.all import Group as fieldGroup
from appy.model.workflow import standard as workflows
from appy.all import String, Select, Selection, Ref, Show, Layouts

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Group(Base):
    '''Base class representing a group'''
    workflows.Owner

    m = {'group': fieldGroup('main', style='grid', label='Group_group'),
         'width': 25, 'indexed': True, 'layouts': Layouts.g, 'label': 'Group'}

    title = String(multiplicity=(1,1), **m)

    def showLogin(self):
        '''When must we show the login field ?'''
        return 'edit' if self.isTemp() else Show.TR

    def showGroups(self):
        '''Only the admin can view or edit roles'''
        return self.user.hasRole('Manager')

    def validateLogin(self, login):
        '''Is this p_login valid ?'''
        return True

    def getGrantableRoles(self):
        '''Returns the list of global roles that can be granted to a user'''
        return [(role.name, self.translate('role_%s' % role.name)) \
                for role in self.H().server.model.grantableRoles]

    login = String(multiplicity=(1,1), show=showLogin, validator=validateLogin,
                   **m)

    # Field allowing to determine which roles are granted to this group
    roles = Select(validator=Selection('getGrantableRoles'),
                   multiplicity=(0,None), **m)

    users = Ref(User, multiplicity=(0,None), add=False, link='popup',
      height=15, back=Ref(attribute='groups', show=User.showRoles,
                          multiplicity=(0,None), label='User'),
      showHeaders=True, shownInfo=('title', 'login', 'state*100px|'),
      actionsDisplay='inline', label='Group')
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
