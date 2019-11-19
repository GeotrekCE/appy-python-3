'''Runs a site'''

# ------------------------------------------------------------------------------
import os, sys, subprocess, signal
from appy.bin import Program
from appy.server import Server

# ------------------------------------------------------------------------------
def start(config, action):
    '''Function that starts a HTTP server'''
    server = Server(config, action)
    
class Run(Program):
    # Help messages
    HELP_ACTION = 'Action can be "start" (start the site), "stop" (stop it), ' \
                  '"fg" (start it in the foreground), "clean" (clean ' \
                  'temporary objects and pack the database) or "run" ' \
                  '(execute a specific method).'
    HELP_METHOD = 'When action in "run", specify the name of the method to ' \
                  'execute on your app\'s tool.'

    # Error messages
    WRONG_ACTION = 'Unknown action "%s".'
    MISSING_METHOD = 'Please specify a method name via option "-m".'
    NOT_IMPLEMENTED = 'Action "%s" is not implemented yet.'
    PORT_USED = 'Port %d is already in use.'
    PID_EXISTS = 'Existing pid file removed (server not properly shut down).'
    PID_NOT_FOUND = "The server can't be stopped."

    # Other constants
    allowedActions = ('start', 'stop', 'fg', 'bg', 'clean', 'run')

    def defineArguments(self):
        '''Define the allowed arguments for this program'''
        parser = self.parser
        parser.add_argument('action', help=Run.HELP_ACTION)
        parser.add_argument('-m', '--method', type=str, help=Run.HELP_METHOD)

    def analyseArguments(self):
        '''Check arguments'''
        # Check that the specified action is valid
        action = self.args.action
        if action not in Run.allowedActions:
            self.exit(self.WRONG_ACTION % action)
        # Check that a method name is given when action is "run"
        method = None
        if action == 'run':
            method = self.args.method
            if method is None:
                self.exit(self.MISSING_METHOD)
        self.action = action
        self.method = method

    def getPid(self, config):
        '''Return a pathlib.Path instance to the "pid" file, which, when the
           server is started in "start" mode, stores its process ID, in order
           to be able to stop him afterwards.'''
        # We have chosen to create the "pid" besides the DB file
        return config.database.filePath.parent / 'pid'

    def checkStart(self, config):
        '''Checks that the server can be started in "start" mode'''
        # Check if the port is already in use or not
        if config.server.inUse():
            print(self.PORT_USED % config.server.port)
            sys.exit(1)
        # If a "pid" file is found, it means that the server was not properly
        # stopped. Remove the file and issue a warning.
        pid = self.getPid(config)
        if pid.exists():
            print(self.PID_EXISTS)
            pid.unlink()

    def checkStop(self, pidFile):
        '''Checks that the server can be stopped and returns the process ID
           (pid) of the running server.'''
        # Check that the pid file exists
        if not pidFile.exists():
            print(self.PID_NOT_FOUND)
            sys.exit(1)
        f = open(str(pidFile))
        r = f.read().strip()
        f.close()
        return int(r)

    def run(self, site, app):
        '''Runs the web server'''
        # Get the configuration
        exec('from %s import Config' % app.name)
        config = eval('Config')
        # Execute the appropriate action
        if self.action in ('fg', 'bg', 'clean', 'run'):
            # ------------------------------------------------------------------
            #  "fg"     | The user executed command "./site fg" : we continue
            #           | and run the server in this (parent, unique) process.
            # ------------------------------------------------------------------
            #  "bg"     | The user executed command "./site start", the runner
            #           | in the parent process spawned a child process with
            #           | command "./site bg". We continue and run the server in
            #           | this (child) process.
            # ------------------------------------------------------------------
            #  "clean", | Theses cases are similar to the "fg" mode hereabove;
            #  "run"    | they misuse the server to execute a single command and
            #           | return, without actually running the server.
            # ------------------------------------------------------------------
            classic = self.action in ('fg', 'bg')
            if self.action == 'fg':
                # For "bg", the check has already been performed
                self.checkStart(config)
            # Create a Server instance
            server = Server(config, self.action, self.method)
            # In classic modes "fg" or "bg", run the server
            if self.action in ('fg', 'bg'):
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    server.shutdown()
                    server.server_close()
                    sys.exit(0)
            else:
                # Everything has been done during server initialisation
                server.shutdown()
                sys.exit(0)
        elif self.action == 'start':
            self.checkStart(config)
            # Spawn a child process and run the server in it, in "bg" mode 
            args = list(sys.argv)
            args[-1] = 'bg'
            # Start the server in the background, in another process
            pid = subprocess.Popen(args).pid
            # Create a file storing the process ID, besides the DB file
            path = self.getPid(config)
            f = open(str(path), 'w')
            f.write(str(pid))
            f.close()
            print('Started as process %s.' % pid)
            sys.exit(0)
        elif self.action == 'stop':
            pidFile = self.getPid(config)
            pid = self.checkStop(pidFile)
            os.kill(pid, signal.SIGINT)
            pidFile.unlink()
            print('Server stopped.')
# ------------------------------------------------------------------------------
