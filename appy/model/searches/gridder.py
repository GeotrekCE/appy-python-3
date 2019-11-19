# ~license~

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Gridder:
    '''Specification about how to produce search results in grid mode. An
       instance of Gridder can be specified in static attribute
       SomeAppyClass.gridder.'''

    def __init__(self, width='350px', gap='20px', justifyContent='space-evenly',
                 alignContent='space-evenly'):
        # The minimum width of every grid element
        self.width = width
        # The gap between grid elements. Will be passed to CSS property
        # "grid-gap".
        self.gap = gap
        # Specify how to align the whole grid horizontally inside the container.
        # Will be passed to CSS property "justify-content".
        self.justifyContent = justifyContent
        # Specify how to align the whole grid vertically inside the container.
        # Will be passed to CSS property "align-content".
        self.alignContent = alignContent

    def getContainerStyle(self):
        '''Returns the CSS styles that must be applied to the grid container
           element.'''
        return 'display: grid; ' \
               'grid-template-columns: repeat(auto-fill, minmax(%s, 1fr)); ' \
               'grid-gap: %s; justify-content: %s; align-content: %s' % \
               (self.width, self.gap, self.justifyContent, self.alignContent)
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
