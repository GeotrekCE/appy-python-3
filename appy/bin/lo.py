#!/usr/bin/python3
'''Contacts LibreOffice (LO) in server mode for test purposes'''

# ------------------------------------------------------------------------------
from pathlib import Path

from appy.pod import test
from appy.bin import Program
from appy.pod.renderer import Renderer

# ------------------------------------------------------------------------------
DEFAULT_SERVER = 'localhost'
DEFAULT_PORT = 2002
DEFAULT_TEST = 'convertToPdf'
TESTS = {
 DEFAULT_TEST: 'a simple test calling LO to convert an odt file into pdf',
 'subPods': 'renders a POD template incorporating sub-pods via a statement ' \
            'of the form "do ... from ..."'
}
HELP_SERVER = 'The hostname of the machine running LibreOffice. Defaults to ' \
  '"%s".' % DEFAULT_SERVER
HELP_PORT = 'The port where LibreOffice listens. Defaults to %d.' % DEFAULT_PORT
HELP_TEST = 'The test to execute. Available tests are %s.' % \
            ', '.join(['"%s" (%s)' % (k, v) for k, v in TESTS.items()])
TEST_NOT_FOUND = 'Test %s does not exist.'

# ------------------------------------------------------------------------------
class LO(Program):

    def defineArguments(self):
        '''Define the allowed arguments for this program'''
        parser = self.parser
        # Optional arguments: LO server and port
        parser.add_argument('-s', '--server', dest='server', help=HELP_SERVER,
                            default=DEFAULT_SERVER)
        parser.add_argument('-p', '--port', dest='port', type=int,
                            help=HELP_PORT, default=DEFAULT_PORT)
        parser.add_argument('-t', '--test', dest='test', help=HELP_TEST,
                            default=DEFAULT_TEST)

    def analyseArguments(self):
        '''Check and store arguments'''
        self.server = self.args.server
        self.port = self.args.port
        self.test = self.args.test

    def convertToPdf(self):
        '''Asks LO to convert to PDF one ODT file from the Appy test suite'''
        # Get the path to some ODT file to convert
        odtFile = self.filesPath / 'NoPython.odt'
        # Create and run a Converter instance
        from appy.pod.converter import Converter
        try:
            converter = Converter(str(odtFile), 'pdf', server=self.server,
                                  port=self.port, verbose=True)
            converter.run()
        except converter.Error as err:
            print(err)

    def subPods(self):
        '''Renders a POD template incorporating sub-pods (via a "do... from
           pod..." statement). Appy calls LO for doing this.'''
        # Create a Renderer for computing the POD...
        template = self.filesPath / 'FromPod.odt'
        context = {'files': self.filesPath}
        result = self.filesPath / 'FromPod.pdf'
        renderer = Renderer(str(template), context, str(result),
                            ooServer=self.server, ooPort=self.port, stream=True,
                            overwriteExisting=True, forceOoCall=True)
        print('Rendering %s...' % str(template))
        renderer.run()
        print('Result produced in %s.' % str(result))

    def run(self):
        '''Contacts LO'''
        print('Running test "%s" on LO %s:%s...' % \
              (self.test, self.server, self.port))
        # Abort if the specified test does not exist
        if not hasattr(self, self.test):
            print(TEST_NOT_FOUND % self.test)
            return
        method = getattr(self, self.test)
        if not callable(method):
            print(TEST_NOT_FOUND % self.test)
            return
        # Get the path to the POD test files
        self.filesPath = Path(test.__file__).parent / 'templates'
        # Execute the test
        return method()

# ------------------------------------------------------------------------------
if __name__ == '__main__': LO().run()
# ------------------------------------------------------------------------------
