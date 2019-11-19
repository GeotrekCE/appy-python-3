# ~license~
# ------------------------------------------------------------------------------
import zipfile, shutil, xml.sax, os, os.path, re, mimetypes, time
from collections import UserDict
from appy import utils
import appy.pod
from appy.pod import PodError
from appy.xml import XmlElement
from appy.utils.zip import unzip, zip
from appy.utils.path import FolderDeleter
from appy.pod.pod_parser import PodParser, PodEnvironment, OdInsert
from appy.pod.converter import FILE_TYPES
from appy.pod.buffers import FileBuffer
from appy.pod.xhtml2odt import Xhtml2OdtConverter
from appy.pod.doc_importers import getUuid, \
     OdtImporter, ImageImporter, PdfImporter, ConvertImporter, PodImporter
from appy.pod.styles_manager import \
     StylesManager, TableProperties, NumberedProperties, BulletedProperties

# ------------------------------------------------------------------------------
BAD_CONTEXT = 'Context must be either a dict, a UserDict or an instance.'
RESULT_IS_FOLDER = 'Result file "%s" is a folder, please remove this.'
RESULT_FILE_EXISTS = 'Result file "%s" exists.'
CANT_WRITE_TEMP_FOLDER = 'I cannot create temp folder "%s". %s'
NO_PY_PATH = 'Extension of result file is "%s". In order to perform ' \
  'conversion from ODT to this format we need to call LibreOffice. But the ' \
  'Python interpreter which runs the current script does not know UNO, the ' \
  'library that allows to connect to LibreOffice in server mode. If you ' \
  'can\'t install UNO in this Python interpreter, you can specify, in ' \
  'parameter "pythonWithUnoPath", the path to a UNO-enabled Python ' \
  'interpreter. One such interpreter may be found in ' \
  '<open_office_path>/program.'
PY_PATH_NOT_FILE = '"%s" is not a file. You must here specify the absolute ' \
  'path of a Python interpreter (.../python, .../python.sh, .../python.exe, ' \
  '.../python.bat...).'
BAD_RESULT_TYPE = 'Result "%s" has a wrong extension. Allowed extensions ' \
  'are: "%s".'
CONVERT_ERROR = 'An error occurred during the conversion. %s'
BAD_OO_PORT = 'Bad LibreOffice port "%s". Make sure it is an integer.'
XHTML_ERROR = 'An error occurred while rendering XHTML content.'
WARNING_INCOMPLETE_OD = 'Warning: your OpenDocument file may not be complete ' \
  '(ie imported documents may not be present). This is because we could not ' \
  'connect to LibreOffice in server mode: %s'
DOC_NOT_SPECIFIED = 'Please specify a document to import, either with a ' \
  'stream (parameter "content") or with a path (parameter "at").'
DOC_FORMAT_ERROR = 'POD was unable to deduce the document format. Please ' \
  'specify it through parameter named "format" (=odt, gif, png, ...).'
DOC_WRONG_FORMAT = 'Format "%s" is not supported.'
WARNING_FINALIZE_ERROR = 'Warning: error while calling finalize function. %s'

# Default styles added by pod in content.xml and styles.xml
POD_STYLES = {}
podFolder = os.path.dirname(appy.pod.__file__)
for name in ('content', 'styles'):
    f = open('%s/%s.xmlt' % (podFolder, name))
    POD_STYLES[name] = f.read()
    f.close()

# ------------------------------------------------------------------------------
class Renderer:
    templateTypes = ('odt', 'ods') # Types of POD templates
    # Regular expression for finding the title within metadata
    metaRex = re.compile('<dc:title>.*?</dc:title>', re.S)
    metaHook = '</office:meta>'

    # ODF tags that may hold POD expressions
    allExpressionsHolders = (
      'if',      # Conditional fields
      'change',  # Track-changed text
      'input',   # Text input fields
      'db'       # Database fields
    )
    defaultExpressionsHolders = ('if', 'change', 'input')

    def __init__(self, template, context, result, pythonWithUnoPath=None,
      ooServer='localhost', ooPort=2002, stream='auto', stylesMapping={},
      html=False, forceOoCall=False, forceLoad=False, finalizeFunction=None,
      overwriteExisting=False, raiseOnError=False, imageResolver=None,
      stylesTemplate=None, optimalColumnWidths=False, distributeColumns=False,
      script=None, managePageStyles=None, resolveFields=False,
      expressionsHolders=defaultExpressionsHolders, metadata=True,
      pdfOptions='ExportNotes=True', deleteTempFolder=True, protection=False,
      pageStart=1):
        '''Base on a document template (whose path is in p_template), which is
           an ODT or ODS file containing special expressions and statements
           written in Python, this renderer generates an ODT file (whose path is
           in p_result), that is a copy of the template whose expressions and
           statements have been replaced with the objects defined in the
           p_context.'''

        # If p_result does not end with .odt or .ods, the Renderer will call
        # LibreOffice (LO) to perform a conversion. If p_forceOoCall is True,
        # even if p_result ends with .odt, LO will be called, not for performing
        # a conversion, but for updating some elements like indexes (table of
        # contents, etc) and sections containing links to external files (which
        # is the case, for example, if you use the default function "document").

        # If the Python interpreter which runs the current script is not
        # UNO-enabled, this script will run, in another process, a UNO-enabled
        # Python interpreter (whose path is p_pythonWithUnoPath) which will call
        # LO. In both cases, we will try to connect to LO in server mode on
        # p_ooServer:p_ooPort.

        # p_stream dictates the communication between the renderer and LO.
        # ----------------------------------------------------------------------
        # p_stream can hold the following values.
        # ----------------------------------------------------------------------
        # "auto"     | if p_ooServer is "localhost", exchanging the ODT result
        # (default)  | produced by the renderer (=the input) and the converted
        #            | file produced by LO (=the output) will be made via files
        #            | on disk. Else, the renderer will consider that LO runs on
        #            | another machine and the exchange will be made via streams
        #            | over the network.
        # ----------------------------------------------------------------------
        # True       | If you want to force communication of the input and
        #            | output files as streams, use stream=True.
        # ----------------------------------------------------------------------
        # False      | If you want to force communication of the input and
        #            | output files via the disk, use stream=False.
        # ----------------------------------------------------------------------
        # "in"       | The input is streamed and the output is written on disk.
        # ----------------------------------------------------------------------
        # "out"      | The input is read from disk and the output is streamed.
        # ----------------------------------------------------------------------

        # LibreOffice, in server mode (similarly to what happens via its UI) may
        # take some time to load a (large) document in its entirety. If you set
        # attribute p_forceLoad to True, Appy will send him commands like "jump
        # to the last page" to force him to load the document in it entirety,
        # before doing other things like updating the table of contents.

        # If you plan to make "XHTML to OpenDocument" conversions (via the POD
        # function "xhtml"), you may specify a "styles mapping" in
        # p_stylesMapping. Moreover, if the input(s) to this function is valid
        # HTML but not valid XHTML, specify p_html being True.

        # If you specify a function in p_finalizeFunction (or a list/tuple of
        # functions), it will be called by the renderer before re-zipping the
        # ODT/S result. This way, you can still perform some actions on the
        # content of the ODT/S file before it is zipped and potentially
        # converted. Every such function must accept 2 args:
        #  *  the absolute path to the temporary folder, containing the
        #     un-zipped content of the ODT/S result;
        #  *  the Renderer instance.

        # If you set p_overwriteExisting to True, the renderer will overwrite
        # the result file. Else, an exception will be thrown if the result file
        # already exists.

        # If p_raiseOnError is False (the default value), any error encountered
        # during the generation of the result file will be dumped into it, as a
        # Python traceback within a note. Else, the error will be raised.

        # p_imageResolver allows POD to retrieve images, from "img" tags within
        # XHTML content. Indeed, POD may not be able (ie, may not have the
        # permission to) perform a HTTP GET on those images. Currently, the
        # resolver can only be a Zope application object.

        # p_stylesTemplate can be the path to a LibreOffice file (ie, a .ott
        # file) whose styles will be imported within the result.

        # p_optimalColumnWidths corresponds to the homonym option to
        # converter.py, excepted that values "True" or "False" must be boolean
        # values. Note that the POD function "xhtml" requires this parameter to
        # be "OCW_.*" to be fully operational. When p_optimalColumnWidths is not
        # False, forceOoCall is forced to True.

        # p_distributeColumns corresponds to the homonym option to converter.py,
        # excepted that values "True" or "False" must be boolean values. Note
        # that the POD function "xhtml" requires this parameter to be "DC_.*" to
        # be fully operational. When p_distributeColumns is not False,
        # forceOoCall is forced to True.

        # p_script is the absolute path to a Python script containing functions
        # that the converter will call in order to customize the process of
        # manipulating the document via the LibreOffice UNO interface. For more
        # information, see appy/pod/converter.py, option "-s". Note that when
        # such p_script is specified, p_forceOoCall is forced to True.

        # If this document is a sub-document to be included in a master one, it
        # has sense to set a specific value for parameter p_managePageStyles:
        # ----------------------------------------------------------------------
        #  "rename" | will rename all page styles with unique names. This way,
        #           | when imported into a master document, no name clash will
        #           | occur and elements tied to page styles (like headers and
        #           | footers) will be correctly imported for all included
        #           | sub-documents. The "do... pod" statement automatically
        #           | sets this parameter to "rename";
        # ----------------------------------------------------------------------
        #   <int>   | will rename page styles similarly to "rename" and will
        #           | also restart, in the sub-document, page numbering at this
        #           | integer value. It will only work if page styles are
        #           | explicitly applied to pages in the sub-pod template. In
        #           | order to achieve this with LibreOffice, open your
        #           | template, set the cursor somewhere in the first page,
        #           | open the pane with page styles, and double-clic on the
        #           | "default style". To check if it has worked, click inside
        #           | the first paragraph in the page, open its properties and
        #           | check that a page break has been defined on it.
        # ----------------------------------------------------------------------

        # If you want to replace (some) fields with their "hard-coded" values,
        # use p_resolveFields. It can be useful, for instance, if the POD result
        # must be included in a master document (via statement "do ... from
        # pod"), but the total number of pages must be kept as is. If
        # p_resolveFields is True, all fields will be resolved, excepted special
        # ones like PageNumber. Indeed, its value is different from one page to
        # another, so resolving it to a single, hard-coded value has no sense.
        # You can also specify "PageCount" as value for p_resolveField. In this
        # case, only the field(s) containing the total number of pages will be
        # resolved. Use it if it is the only field you need to resolve, it will
        # be more performant. Note that when p_resolveFields is set,
        # p_forceOoCall is forced to True.

        # POD expressions may be defined at various places within a document
        # template. Possible places are listed in static variable
        # "allExpressionsHolders" hereabove. Default places are listed in static
        # variable "defaultExpressionsHolders" hereabove.

        # If p_metadata is True, the result will get a metadata property "title"
        # (in meta.xml) being the result file name, without its extension. If
        # p_metadata is a string, it will be used as title.

        # If the result must be produced in PDF, options which are specific to
        # this format can be given in p_pdfOptions, as a comma-separated string
        # of key=value pairs, as in

        #            ExportNotes=False,PageRange=1-20,Watermark=Sample

        # More info in appy/pod/converter.py.

        # If this renderer is called by another one (its "parent"), it may
        # receive an additional parameter, p_deleteTempFolder. If False, the
        # temp folder may be reused by other children of the parent renderer, so
        # we do not delete it (the parent will do it at the end of the whole
        # process).

        # if "protection" is True, you can define variables "cellProtected"
        # and/or "sectionProtected" to determine, respectively, if a cell or a
        # section must be write-protected. It is not enabled by default because
        # it has a little impact on performance and on the size of the p_result
        # (especially large ods results).

        # If p_pageStart is different from 1, the produced document will start
        # page numbering at this number. In that case, p_forceOoCall will be
        # forced to True.

        self.template = template
        self.result = result
        self.resultType = os.path.splitext(result)[1].strip('.')
        self.contentXml = None # Content (string) of content.xml
        self.stylesXml = None # Content (string) of styles.xml
        self.manifestXml = None # Content (string) of manifest.xml
        self.metaXml = None # Content (string) of meta.xml
        # Manages the styles defined into the ODT template
        self.tempFolder = None
        self.env = None
        self.pythonWithUnoPath = pythonWithUnoPath
        self.ooServer = ooServer
        self.ooPort = ooPort
        self.stream = stream
        # p_forceOoCall may be forced to True
        self.forceOoCall = forceOoCall or bool(optimalColumnWidths) or \
          bool(distributeColumns) or bool(script) or bool(resolveFields) or \
          (pageStart > 1)
        self.forceLoad = forceLoad
        # Must the POD post-processor (ppp) be enabled ?
        self.ppp = False
        self.finalizeFunction = self.formatFinalizeFunction(finalizeFunction)
        self.overwriteExisting = overwriteExisting
        self.raiseOnError = raiseOnError
        self.imageResolver = imageResolver
        self.stylesTemplate = stylesTemplate
        self.optimalColumnWidths = optimalColumnWidths
        self.distributeColumns = distributeColumns
        self.script = script
        self.managePageStyles = managePageStyles
        self.resolveFields = resolveFields
        self.expressionsHolders = expressionsHolders
        self.metadata = metadata
        self.pdfOptions = pdfOptions
        self.deleteTempFolder = deleteTempFolder
        self.protection = protection
        self.pageStart = pageStart
        # If sub-renderers are called, keep a trace of them
        self.children = {} # ~{s_templatePath: Renderer}~
        # Keep trace of the original context given to the renderer
        self.originalContext = context
        # Remember potential files or images that will be included through
        # "do ... from document" statements: we will need to declare them in
        # META-INF/manifest.xml. Keys are file names as they appear within the
        # ODT file (to dump in manifest.xml); values are original paths of
        # included images (used for avoiding to create multiple copies of a file
        # which is imported several times).
        self.fileNames = {}
        self.prepareFolders()
        # Unzip the p_template
        info = unzip(template, self.unzipFolder, odf=True)
        self.contentXml = info['content.xml']
        self.stylesXml = info['styles.xml']
        # Manage the styles defined into the ODT template
        self.stylesManager = StylesManager(self)
        # From LibreOffice 3.5, it is not possible anymore to dump errors into
        # the resulting ods as annotations. Indeed, annotations can't reside
        # anymore within paragraphs. ODS files generated with pod and containing
        # error messages in annotations cause LibreOffice 3.5 and 4.0 to crash.
        # LibreOffice >= 4.1 simply does not show the annotation.
        if info['mimetype'] == utils.mimeTypes['ods']: self.raiseOnError = True
        # Create the parsers for content.xml and styles.xml
        self.createParsers(context)
        # Store the styles mapping
        self.setStylesMapping(stylesMapping)
        # Store the p_html parameter
        self.html = html
        # While working, POD may identify "dynamic styles" to insert either in
        # the "automatic-styles" section of content.xml (ie, the column styles
        # of tables generated from XHTML tables via xhtml2odt.py), or in the
        # "styles" section of styles.xml (ie, bullet styles).
        self.dynamicStyles = {'content': [], 'styles': []}

    def reinit(self, result, context):
        '''Re-initialise this renderer (p_self) for recycling him and produce
           another p_result with another p_context.'''
        self.result = result
        self.originalContext = context
        # Re-create POD parsers
        self.createParsers(context)
        # Reinitialise attributes being specific to a given result
        self.dynamicStyles = {'content': [], 'styles': []}
        sm = self.stylesManager.stylesMapping
        self.stylesManager = StylesManager(self)
        self.stylesManager.stylesMapping = sm

    # Attributes to clone to a sub-renderer when using m_clone hereafter
    cloneAttributes = ('pythonWithUnoPath', 'ooServer', 'ooPort', 'html',
      'forceLoad', 'raiseOnError', 'imageResolver', 'stylesTemplate',
      'optimalColumnWidths', 'distributeColumns', 'expressionsHolders',
      'protection')

    def clone(self, template, context, result, **params):
        '''Creates another Renderer instance, similar to p_self, but for
           rendering a different p_result based on another p_context and
           p_template, with possibly different other p_params. Any parameter not
           being in p_params but listed in Renderer.cloneAttributes will be
           copied from p_self to the clone.'''
        # Complete p_params with attributes listed in Renderer.cloneAttributes
        for name in Renderer.cloneAttributes:
            if name not in params:
                params[name] = getattr(self, name)
        # Create and return the clone
        return Renderer(template, context, result, **params)

    def formatFinalizeFunction(self, fun):
        '''Standardize "finalize function" p_fun as a list of functions'''
        if not fun: return
        elif isinstance(fun, list): return fun
        elif isinstance(fun, tuple): return list(fun)
        else: return [fun]

    def enablePpp(self):
        '''Activate the POD post-processor, which is implemented as a series of
           UNO commands.'''
        self.forceOoCall = True
        self.ppp = True

    def getCompleteContext(self, context):
        '''Create and return a complete context, from the one given by the pod
           developer (p_context).'''
        r = {}
        if hasattr(context, '__dict__'):
            r.update(context.__dict__)
        elif isinstance(context, dict) or isinstance(context, UserDict):
            r.update(context)
        else:
            raise PodError(BAD_CONTEXT)
        # Incorporate the default, unalterable, context
        r.update({'xhtml': self.renderXhtml, 'test': self.evalIfExpression,
          'document': self.importDocument, 'image': self.importImage,
          'pod': self.importPod,
          'TableProperties': TableProperties,
          'BulletedProperties': BulletedProperties,
          'NumberedProperties': NumberedProperties,
          'pageBreak': self.insertPageBreak,
          'columnBreak': self.insertColumnBreak,
          # Variables to use for representing pod-reserved chars
          'PIPE': '|', 'SEMICOLON': ';'})
        # Developer, forget the following line
        if '_ctx_' not in r: r['_ctx_'] = r
        return r

    def createPodParser(self, odtFile, context, inserts=None):
        '''Creates the parser with its environment for parsing the given
           p_odtFile (content.xml or styles.xml). p_context is given by the pod
           user, while p_inserts depends on the ODT file we must parse.'''
        context = self.getCompleteContext(context)
        env = PodEnvironment(context, inserts, self.expressionsHolders)
        fileBuffer = FileBuffer(env, os.path.join(self.tempFolder, odtFile))
        env.currentBuffer = fileBuffer
        return PodParser(env, self)

    def createParsers(self, context):
        '''Creates parsers for content.xml and styles.xml and store them,
           respectively, in p_self.contentParser and p_self.stylesParser.'''
        nso = PodEnvironment.NS_OFFICE
        for name in ('content', 'styles'):
            styleTag = (name == 'content') and 'automatic-styles' or 'styles'
            inserts = (
              OdInsert(POD_STYLES[name], XmlElement(styleTag, nsUri=nso)),)
            parser = self.createPodParser('%s.xml' % name, context, inserts)
            setattr(self, '%sParser' % name, parser)

    def renderXhtml(self, s, encoding='utf-8', stylesMapping={}, keepWithNext=0,
                    keepImagesRatio=False, imagesMaxWidth='page', html=None,
                    unwrap=False):
        '''Method that can be used (under the name 'xhtml') into a pod template
           for converting a chunk of XHTML content (p_s) into a chunk of ODT
           content.

           For this conversion, beyond the global styles mapping defined at the
           renderer level, a specific p_stylesMapping can be given: any key in
           it overrides its homonym in the global mapping.

           If p_html is not None, it overrides renderer's homonym parameter.
        '''
        stylesMapping = self.stylesManager.checkStylesMapping(stylesMapping)
        if html == None: html = self.html
        return Xhtml2OdtConverter(s, encoding, self.stylesManager,
                                  stylesMapping, keepWithNext, keepImagesRatio,
                                  imagesMaxWidth, self, html, unwrap).run()

    def evalIfExpression(self, condition, ifTrue, ifFalse):
        '''This method implements the method 'test' which is proposed in the
           default pod context. It represents an 'if' expression (as opposed to
           the 'if' statement): depending on p_condition, expression result is
           p_ifTrue or p_ifFalse.'''
        if condition: return ifTrue
        return ifFalse

    # Supported image formats. "image" represents any format
    imageFormats = ('png', 'jpeg', 'jpg', 'gif', 'svg', 'image')
    ooFormats = ('odt',)
    convertibleFormats = FILE_TYPES.keys()

    def importDocument(self, content=None, at=None, format=None,
      anchor='as-char', wrapInPara=True, size=None, sizeUnit='cm',
      maxWidth='page', style=None, keepRatio=True, pageBreakBefore=False,
      pageBreakAfter=False, convertOptions=None):
        '''If p_at is not None, it represents a path or url allowing to find
           the document. If p_at is None, the content of the document is
           supposed to be in binary format in p_content. The document
           p_format may be: odt or any format in imageFormats.

           p_anchor, p_wrapInPara, p_size, p_sizeUnit, p_style and p_keepRatio
           are only relevant for images:
           * p_anchor defines the way the image is anchored into the document;
                      Valid values are 'page','paragraph', 'char' and 'as-char';
           * p_wrapInPara, if true, wraps the resulting 'image' tag into a 'p'
                           tag;
           * p_size, if specified, is a tuple of float or integers
                     (width, height) expressing size in p_sizeUnit (see below).
                     If not specified, size will be computed from image info;
           * p_sizeUnit is the unit for p_size elements, it can be "cm"
             (centimeters), "px" (pixels) or "pc" (percentage). Percentages, in
             p_size, must be expressed as integers from 1 to 100.
           * if p_maxWidth is specified (as a float value representing cm),
             image's width will not be greater than it. If p_maxWidth is "page"
             (the default), p_maxWidth will be computed as the width of the
             main document's page style, margins excluded.
           * if p_style is given, it is a appy.shared.css.CssStyles instance,
             containing CSS attributes. If "width" and "heigth" attributes are
             found there, they will override p_size and p_sizeUnit.
           * If p_keepRatio is True, the image width/height ratio will be kept
             when p_size is specified.

           p_pageBreakBefore and p_pageBreakAfter are only relevant for
           importing external odt documents, and allows to insert a page break
           before/after the inserted document. More precisely, each of these
           parameters can have values:
           * True     insert a page break;
           * False    do no insert a page break;

           moreover, p_pageBreakAfter can have this additional parameter:
           * 'duplex' insert 2 page breaks if the sub-document has an odd number
                      of pages, 1 else (useful for duplex printing).

           If p_convertOptions are given (for images only), imagemagick will be
           called with these options to perform some transformation on the
           image. For example, if you specify
                             convertOptions="-rotate 90"

           pod will perform this command before importing the file into the
           result:
                       convert your.image -rotate 90 your.image

           You can also specify a function in convertOptions. This function will
           receive a single arg, "image", an instance of
           appy.pod.doc_importers.Image giving some characteristics of the image
           to convert, like image.width and image.height in pixels (integers).
           If your function does not return a string containing the convert
           options, no conversion will occur.
        '''
        importer = None
        # Is there someting to import ?
        if not content and not at: raise PodError(DOC_NOT_SPECIFIED)
        # Convert Zope files into Appy wrappers
        if content.__class__.__name__ in ('File', 'Image'):
            content = utils.FileWrapper(content)
        # Guess document format
        if isinstance(content, utils.FileWrapper):
            format = content.mimeType
        if not format:
            # It should be deduced from p_at
            if not at:
                raise PodError(DOC_FORMAT_ERROR)
            format = os.path.splitext(at)[1][1:]
        else:
            # If format is a mimeType, convert it to an extension
            if format in utils.mimeTypesExts:
                format = utils.mimeTypesExts[format]
        isImage = False
        isOdt = False
        if format in self.ooFormats:
            importer = OdtImporter
            self.forceOoCall = True
            isOdt = True
        elif (format in self.imageFormats) or not format:
            # If the format can't be guessed, we suppose it is an image
            importer = ImageImporter
            isImage = True
        elif format == 'pdf':
            importer = PdfImporter
        elif format in self.convertibleFormats:
            importer = ConvertImporter
        else:
            raise PodError(DOC_WRONG_FORMAT % format)
        imp = importer(content, at, format, self)
        # Initialise image-specific parameters
        if isImage:
            imp.init(anchor, wrapInPara, size, sizeUnit, maxWidth, style,
                     keepRatio, convertOptions)
        elif isOdt: imp.init(pageBreakBefore, pageBreakAfter)
        return imp.run()

    def importImage(self, content=None, at=None, format=None, size=None,
                    sizeUnit='cm', maxWidth='page', style=None, keepRatio=True,
                    convertOptions=None):
        '''While p_importDocument allows to import a document or image via a
           "do ... from document" statement, method p_importImage allows to
           import an image anchored as a char via a pod expression
           "image(...)", having almost the same parameters.'''
        # 2 parameters are missing (1) "anchor" is forced to be "as-char" and
        # (2) "wrapInPara" is forced to False.
        return self.importDocument(content=content, at=at, format=format,
          wrapInPara=False, size=size, sizeUnit=sizeUnit, maxWidth=maxWidth,
          style=style, keepRatio=keepRatio, convertOptions=convertOptions)

    def getResolvedNamespaces(self):
        '''Gets a context where mainly used namespaces have been resolved'''
        env = self.stylesParser.env
        return {'text': env.ns(env.NS_TEXT), 'style': env.ns(env.NS_STYLE)}

    def importPod(self, content=None, at=None, format='odt', context=None,
          pageBreakBefore=False, pageBreakAfter=False,
          managePageStyles='rename', resolveFields=False):
        '''Similar to m_importDocument, but allows to import the result of
           executing the POD template specified in p_content or p_at, and
           include it in the POD result.

           Renaming page styles for the sub-pod (p_managePageStyles being
           "rename") ensures there is no name clash between page styles (and
           tied elements such as headers and footers) coming from several
           sub-pods or with styles defined at the master document level. This
           takes some processing, so you can set it to None if you are sure you
           do not need it.

           p_resolveFields has the same meaning as the homonym parameter on the
           Renderer.
        '''
        # Is there a pod template defined ?
        if not content and not at:
            raise PodError(DOC_NOT_SPECIFIED)
        # If the POD template is specified as a Zope file, convert it into a
        # Appy FileWrapper.
        if content.__class__.__name__ == 'File':
            content = utils.FileWrapper(content)
        imp = PodImporter(content, at, format, self)
        self.forceOoCall = True
        # Define the context to use: either the current context of the current
        # POD renderer, or p_context if given.
        if context:
            ctx = context
        else:
            ctx = self.contentParser.env.context
        imp.init(ctx, pageBreakBefore, pageBreakAfter,
                 managePageStyles, resolveFields)
        return imp.run()

    def _insertBreak(self, type):
        '''Inserts a page or column break into the result'''
        name = (type == 'page') and 'podPageBreakAfter' or 'podColumnBreak'
        return '<text:p text:style-name="%s"></text:p>' % name
    def insertPageBreak(self): return self._insertBreak('page')
    def insertColumnBreak(self): return self._insertBreak('column')

    def prepareFolders(self):
        '''Ensure p_self.result is correct and create, when relevant, the temp
           folder for preparing it.'''
        # Ensure p_self.result is an absolute path
        self.result = os.path.abspath(self.result)
        # Raise an error if the result already exists and we can't overwrite it
        if os.path.isdir(self.result):
            raise PodError(RESULT_IS_FOLDER % self.result)
        exists = os.path.isfile(self.result)
        if not self.overwriteExisting and exists:
            raise PodError(RESULT_FILE_EXISTS % self.result)
        # Remove the result if it exists
        if exists: os.remove(self.result)
        # Create a temp folder for storing temporary files
        self.tempFolder = '%s.%f' % (self.result, time.time())
        try:
            os.mkdir(self.tempFolder)
        except OSError as oe:
            raise PodError(CANT_WRITE_TEMP_FOLDER % (self.result, oe))
        # The "unzip" folder is a sub-folder, within self.tempFolder, where
        # p_self.template will be unzipped.
        self.unzipFolder = os.path.join(self.tempFolder, 'unzip')
        os.mkdir(self.unzipFolder)

    def patchMetadata(self):
        '''Declares, in META-INF/manifest.xml, images or files included via the
           "do... from document" statements if any, and patch meta.xml (field
           "title").'''
        # Patch META-INF/manifest.xml
        j = os.path.join
        if self.fileNames:
            toInsert = ''
            for fileName in self.fileNames.keys():
                if fileName.endswith('.svg'):
                    fileName = os.path.splitext(fileName)[0] + '.png'
                mimeType = mimetypes.guess_type(fileName)[0]
                toInsert += ' <manifest:file-entry manifest:media-type="%s" ' \
                            'manifest:full-path="%s"/>\n' % (mimeType, fileName)
            manifestName = j(self.unzipFolder, 'META-INF', 'manifest.xml')
            # Read the the content of this file, if not already in
            # self.manifestXml.
            if not self.manifestXml:
                f = open(manifestName)
                self.manifestXml = f.read()
                f.close()
            hook = '</manifest:manifest>'
            content = self.manifestXml.replace(hook, toInsert + hook)
            # Write the new manifest content
            f = open(manifestName, 'w')
            f.write(content)
            f.close()
        # Patch meta.xml
        metadata = self.metadata
        if metadata:
            metaName = j(self.unzipFolder, 'meta.xml')
            # Read the content of this file, if not already in self.metaXml
            if not self.metaXml:
                f = open(metaName)
                self.metaXml = f.read()
                f.close()
            # Remove the existing title, if it exists
            content = self.metaRex.sub('', self.metaXml)
            # Add a new title, based on the result name
            if isinstance(metadata, str):
                title = metadata
            else:
                title = os.path.splitext(os.path.basename(self.result))[0]
            hook = self.metaHook
            title = '<dc:title>%s</dc:title>%s' % (title, hook)
            content = content.replace(hook, title)
            f = open(metaName, 'w')
            f.write(content)
            f.close()

    # Public interface
    def run(self):
        '''Renders the result'''
        try:
            # Remember which parser is running
            self.currentParser = self.contentParser
            # Create the resulting content.xml
            self.currentParser.parse(self.contentXml)
            self.currentParser = self.stylesParser
            # Create the resulting styles.xml
            self.currentParser.parse(self.stylesXml)
            # Patch metadata
            self.patchMetadata()
            # Re-zip the result
            self.finalize()
        finally:
            if self.deleteTempFolder:
                FolderDeleter.delete(self.tempFolder)

    def getStyles(self):
        '''Returns a dict of the styles that are defined into the template'''
        return self.stylesManager.styles

    def setStylesMapping(self, stylesMapping):
        '''Establishes a correspondence between, on one hand, CSS styles or
           XHTML tags that will be found inside XHTML content given to POD,
           and, on the other hand, ODT styles found into the template.'''
        try:
            manager = self.stylesManager
            # Initialise the styles mapping when relevant
            ocw = self.optimalColumnWidths
            dis = self.distributeColumns
            if ocw or dis:
                TableProperties.initStylesMapping(stylesMapping, ocw, dis)
            manager.stylesMapping = manager.checkStylesMapping(stylesMapping)
        except PodError as po:
            self.contentParser.env.currentBuffer.content.close()
            self.stylesParser.env.currentBuffer.content.close()
            if os.path.exists(self.tempFolder):
                FolderDeleter.delete(self.tempFolder)
            raise po

    def callLibreOffice(self, resultName, outputName=None, format=None):
        '''Call LibreOffice in server mode to convert or update the result'''
        # Here are the valid combinations for parameter's values.
        # ----------------------------------------------------------------------
        # no outputName | The converter will produce a result whose name is
        #   no format   | p_resultName whose file extension has been replaced
        #               | with the one specified in self.resultType.
        # ----------------------------------------------------------------------
        # no outputName | Idem, but the output format is forced to p_format
        #    format     | instead of using self.resultType.
        # ----------------------------------------------------------------------
        #  outputName   | The converter will produce a result whose name is
        #  no format    | p_outputName. The output format will depend on
        #               | p_outputName's file extension.
        # ----------------------------------------------------------------------
        loOutput = ''
        # Determine the "result" to ask to LibreOffice
        if outputName:
            result = outputName
            resultType = os.path.splitext(result)[-1][1:]
        else:
            result = format or self.resultType
            resultType = result
        try:
            if (not isinstance(self.ooPort, int)) and \
               (not isinstance(self.ooPort, long)):
                raise PodError(BAD_OO_PORT % str(self.ooPort))
            try:
                from appy.pod.converter import Converter, ConverterError
                try:
                    Converter(resultName, result, self.ooServer, self.ooPort,
                      self.stylesTemplate, self.optimalColumnWidths,
                      self.distributeColumns, self.script, self.resolveFields,
                      self.pdfOptions, self.ppp, self.stream,
                      self.forceLoad, self.pageStart).run()
                except ConverterError as ce:
                    raise PodError(CONVERT_ERROR % str(ce))
            except ImportError:
                # I do not have UNO. So try to launch a UNO-enabled Python
                # interpreter which should be in self.pythonWithUnoPath.
                pyPath = self.pythonWithUnoPath
                if not pyPath:
                    raise PodError(NO_PY_PATH % resultType)
                if not os.path.isfile(pyPath):
                    raise PodError(PY_PATH_NOT_FILE % pyPath)
                convScript = '%s/converter.py' % \
                             os.path.dirname(appy.pod.__file__)
                cmd = [pyPath, convScript, resultName, result,
                       '-e', self.ooServer, '-p', str(self.ooPort)]
                add = cmd.append
                if self.stylesTemplate:
                    add('-t'); add(self.stylesTemplate)
                if self.optimalColumnWidths:
                    add('-o'); add('%s' % str(self.optimalColumnWidths))
                if self.distributeColumns:
                    add('-d'); add('%s' % str(self.distributeColumns))
                if self.script:
                    add('-s'); add('%s' % self.script)
                if self.resolveFields:
                    add('-r'); add('%s' % self.resolveFields)
                if self.pdfOptions:
                    add('-f'); add('%s' % self.pdfOptions)
                if self.ppp: add('-c')
                if self.stream != 'auto':
                    add('-a'); add(str(self.stream))
                if self.forceLoad: add('-l')
                if self.pageStart > 1:
                    add('-g'); add(str(self.pageStart))
                out, loOutput = utils.executeCommand(cmd)
        except PodError as pe:
            # When trying to call LO in server mode for producing ODT or ODS
            # (=forceOoCall=True), if an error occurs we have nevertheless
            # an ODT or ODS to return to the user. So we produce a warning
            # instead of raising an error.
            if (resultType in self.templateTypes) and self.forceOoCall:
                print(WARNING_INCOMPLETE_OD % str(pe))
            else:
                raise pe
        return loOutput

    def getTemplateType(self):
        '''Identifies the type of the pod template in self.template
           (ods or odt). If self.template is a string, it is a file name and we
           simply get its extension. Else, it is a binary file in a StringIO
           instance, and we seek the mime type from the first bytes.'''
        if isinstance(self.template, str):
            res = os.path.splitext(self.template)[1][1:]
        else:
            # A StringIO instance
            self.template.seek(0)
            firstBytes = self.template.read(90)
            firstBytes = firstBytes[firstBytes.index('mimetype')+8:]
            if firstBytes.startswith(utils.mimeTypes['ods']):
                res = 'ods'
            else:
                res = 'odt' # We suppose this is ODT
        return res

    def finalize(self):
        '''Re-zip the result and potentially call LibreOffice if target format
           is not among self.templateTypes or if forceOoCall is True.'''
        j = os.path.join
        # If an action regarding page styles must be performed, get and modify
        # them accordingly.
        pageStyles = None
        mps = self.managePageStyles
        if mps != None:
            pageStyles = self.stylesManager.pageStyles.init(mps)
        # Patch styles.xml and content.xml
        for name in ('styles', 'content'):
            # Copy the [content|styles].xml file from the temp to the zip folder
            fn = '%s.xml' % name
            shutil.copy(j(self.tempFolder, fn), j(self.unzipFolder, fn))
            # For styles.xml, complete dynamic styles with default styles for
            # bulleted and numbered lists.
            ds = self.dynamicStyles[name]
            if name == 'styles':
                env = self.stylesParser.env
                n = {'text': env.ns(env.NS_TEXT), 'style': env.ns(env.NS_STYLE)}
                ds.insert(0,NumberedProperties().dumpStyle('podNumberedList',n))
                ds.insert(0,BulletedProperties().dumpStyle('podBulletedList',n))
            # Get the file content and inject dynamic styles into it
            fn = os.path.join(self.unzipFolder, fn)
            f = open(fn)
            content = f.read().replace('<!DYNAMIC_STYLES!>',
                                       b''.join(ds).decode())
            # Rename the page styles
            if pageStyles:
                content = pageStyles.renameIn(name, content)
            f.close()
            # Write the updated content to the file
            f = open(fn, 'w')
            f.write(content)
            f.close()
        # Call the user-defined "finalize" function(s) when present
        if self.finalizeFunction:
            try:
                for fun in self.finalizeFunction: fun(self.unzipFolder, self)
            except Exception as e:
                print(WARNING_FINALIZE_ERROR % str(e))
        # Re-zip the result, first as an OpenDocument file of the same type as
        # the POD template (odt, ods...)
        resultExt = self.getTemplateType()
        resultName = os.path.join(self.tempFolder, 'result.%s' % resultExt)
        resultType = self.resultType
        zip(resultName, self.unzipFolder, odf=True)
        if (resultType in self.templateTypes) and not self.forceOoCall:
            # Simply move the ODT result to the result
            os.rename(resultName, self.result)
        else:
            if resultType not in FILE_TYPES:
                raise PodError(BAD_RESULT_TYPE % (
                    self.result, FILE_TYPES.keys()))
            # Call LibreOffice to perform the conversion or document update
            output = self.callLibreOffice(resultName, self.result)
            # I (should) have the result in self.result
            if not os.path.exists(self.result):
                if resultType in self.templateTypes:
                    # In this case LO in server mode could not be called (to
                    # update indexes, sections, etc) but I can still return the
                    # "raw" pod result that exists in "resultName".
                    os.rename(resultName, self.result)
                else:
                    raise PodError(CONVERT_ERROR % output)
# ------------------------------------------------------------------------------
