# ~license~

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.data import rtlLanguages

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Languages:
    '''Manages user language-related elements'''

    @classmethod
    def getDirection(self, lang):
        '''Determines if p_lang is a LTR (left-to-right) or RTL (right-to-left)
           language.'''
        # It returns a 3-tuple  (dir, dleft, dright)
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # dir    | String "ltr" for a left-to-right language, "rtl" for a
        #        | right-to-left language;
        # dleft  | String "left" for a LTR and "right" for a RTL language
        # dright | String "right" for a LTR and "left" for a RTL language
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        isRtl = lang in rtlLanguages
        return ('rtl', 'right', 'left') if isRtl else ('ltr', 'left', 'right')
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
