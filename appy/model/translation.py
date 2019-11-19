# ~license~

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import tempfile
from pathlib import Path

from appy.tr import po
from appy.model.base import Base
from appy.all import String, Action, Page

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Translation(Base):
    '''Base class representing a group of translations in some language'''

    # Translations are not indexed by default
    indexable = False

    # Override field "title" to make it uneditable
    p = {'page': Page('main'), 'label': 'Translation'}
    title = String(show=False, **p)

    # The "source language", used as base for translating labels of this
    # translation, is defined in the RAM config (which is the default value),
    # but can be changed for a specific translation.
    sourceLanguage = String(width=4, multiplicity=(1,1), **p)

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Update from po files
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def updateFromFiles(self, appyFiles, appFiles):
        '''Loads labels on p_self from Appy and app's po files'''
        # Count the number of loaded messages
        count = 0
        appName = self.config.model.appName
        lg = self.id
        # Load messages from: (1) Appy, (2) automatic and (3) custom app labels
        for place in (appyFiles.get('%s.po' % lg), \
                      appFiles.get('%s-%s.po' % (appName, lg)), \
                      appFiles.get('Custom-%s.po' % lg)):
            for message in place.messages.values():
                setattr(self, message.id, message.get())
                count += 1
        self.log('Translation file for "%s" loaded - %d messages.' % (lg,count))

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Get a translated text
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def get(self, label, mapping=None):
        '''Gets the translated text stored on p_self for this i18n p_label'''
        # Gets the translated text
        r = getattr(self, label, '') or ''
        if not r or not mapping: return r
        # Apply p_mapping
        if mapping:
            for name, repl in mapping.items():
                repl = repl if isinstance(repl, str) else str(repl)
                r = r.replace('${%s}' % name, repl)        
        return r

    # Propose 2 buttons to produce the "po" files containing, respectively,
    # automatic and custom labels, reflecting any change performed by the user
    # on translation pages.
    p.update({'result': 'file', 'show': 'buttons'})
    poReplacements = ( ('\r\n', '<br/>'), ('\n', '<br/>'), ('"', '\\"') )

    def getPoFile(self, type):
        '''Generates the "po" file corresponding to this translation, updated
           with the potential changes performed by the user on translation
           pages.'''
        tool = self.tool
        baseName = type == 'main' and self.config.model.appName or 'Custom'
        displayName = '%s-%s.po' % (baseName, self.id)
        poFile = po.File(Path(displayName))
        count = 0
        for field in self.class_.fields.values():
            # Ignore irrelevant fields
            if (field.page.phase != type) or (field.page.name == 'main') or \
               (field.type != 'String'):
                continue
            # Adds the PO message corresponding to this field
            msg = field.getValue(self) or ''
            for old, new in self.poReplacements:
                msg = msg.replace(old, new)
            poFile.addMessage(po.Message(field.name, msg, ''), needsCopy=False)
            count += 1
        stringIo = poFile.generate(inFile=False)
        stringIo.name = displayName # To mimic a file
        stringIo.seek(0)
        return True, stringIo

    poAutomatic = Action(action=lambda tr: tr.getPoFile('main'), **p)
    poCustom = Action(action=lambda tr: tr.getPoFile('custom'), **p)

    def computeLabel(self, field):
        '''The label for a text to translate displays the text of the
           corresponding message in the source translation.'''
        tool = self.tool
        # Get the source language: either defined on the translation itself, or
        # from the config.
        sourceLanguage = self.sourceLanguage or self.config.ui.sourceLanguage
        sourceTranslation = self.getObject(sourceLanguage)
        # p_field is the Computed field. We need to get the name of the
        # corresponding field holding the translation message.
        fieldName = field.name[:-6]
        # If we are showing the source translation, we do not repeat the message
        # in the label.
        if self.id == sourceLanguage:
            sourceMsg = ''
        else:
            sourceMsg = getattr(sourceTranslation, fieldName)
            # When editing the value, we don't want HTML code to be interpreted.
            # This way, the translator sees the HTML tags and can reproduce them
            # in the translation.
            if self.H().getLayout() == 'edit':
                sourceMsg = sourceMsg.replace('<','&lt;').replace('>','&gt;')
            sourceMsg = sourceMsg.replace('\n', '<br/>')
        return '<div class="translationLabel"><abbr title="%s" ' \
               'style="margin-right: 5px"><img src="%s"/></abbr>' \
               '%s</div>' % (fieldName, self.buildUrl('help'), sourceMsg)

    def showField(self, field):
        '''Show a field (or its label) only if the corresponding source message
           is not empty.'''
        tool = self.tool
        name = field.name[:-6] if field.type == 'Computed' else field.name
        # Get the source message
        sourceLanguage = self.config.ui.sourceLanguage
        sourceTranslation = tool.getObject(sourceLanguage)
        sourceMsg = getattr(sourceTranslation, name)
        if field.isEmptyValue(self, sourceMsg): return
        return True
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
