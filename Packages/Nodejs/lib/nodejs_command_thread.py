import os
import codecs
import functools
import threading
import subprocess
import signal

import sublime

import shellenv
import psutil

from .nodejs_debug import debug
from .nodejs_constants import PLUGIN_PATH


def main_thread(callback, *args, **kwargs):
    # sublime.set_timeout gets used to send things onto the main thread
    # most sublime.[something] calls need to be on the main thread
    sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)


def _make_text_safeish(text, fallback_encoding):
    # DEPRECATED
    #
    # The unicode decode here is because sublime converts to unicode inside
    # insert in such a way that unknown characters will cause errors, which is
    # distinctly non-ideal... and there's no way to tell what's coming out of
    # git in output. So...
    return text


def run_os_command(cmd):
    shell = os.name == 'nt'

    try:
    
        options = {
            'shell': shell, 
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
            'universal_newlines': False,
        }
        
        if not shell:
            options['env'] = {}
            options['env'].update({'PATH': shellenv.get_env()[1]['PATH']})
    
        proc = subprocess.Popen(cmd, **options)
        output = proc.communicate()[0].decode()
        
        debug('run_os_command: output', output)

        return output

    except Exception as e:
        debug('run_os_command: exception', str(e))
        return "ERROR: run_os_command: {0}".format(e)


class CommandThread(threading.Thread):

    def __init__(self, command, on_done, working_dir="", 
                        fallback_encoding="", env={}, shell=False):

        threading.Thread.__init__(self)
        self.command = command
        self.on_done = on_done
        self.working_dir = working_dir
        self.fallback_encoding = fallback_encoding
        self.env = os.environ.copy()
        self.env.update(env)
        self.shell = shell

        self.pid_file_name = '.debugger.pid'

        pid_file_path = os.path.join(PLUGIN_PATH, self.pid_file_name)
        if not os.path.exists(pid_file_path):
            with open(pid_file_path, "x") as f:
                pass

    def _write_pid(self):
        with open(os.path.join(PLUGIN_PATH, self.pid_file_name), 'w') as f:
            f.write(str(self.proc.pid))
        debug("_write_pid: debugger pid:", str(self.proc.pid))

    def _read_pid(self):
        with open(os.path.join(PLUGIN_PATH, self.pid_file_name), 'r') as f:
            return f.read()

    def _kill_debugger(self):
        debugger_pid = self._read_pid()
        debug("_kill_debugger: debugger_pid", debugger_pid)
        if debugger_pid == "":
            return

        try:
            p = psutil.Process(int(debugger_pid))
            debug("_kill_debugger: process:", p)
            p.kill()
        except psutil.NoSuchProcess as e:
            debug("_kill_debugger: NoSuchProcess exception is occurred", e)
            return

    def run(self):
        try:
            # kill previously started debugger
            self._kill_debugger()

            # Per http://bugs.python.org/issue8557 shell=True is required to
            # get $PATH on Windows. Yay portable code.
            debug("CommandThread: run: self.shell", self.shell)
            if self.working_dir != "":
                os.chdir(self.working_dir)
          
            self.proc = subprocess.Popen(self.command, 
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.STDOUT, 
                                                shell=self.shell, 
                                                universal_newlines=False,
                                                env=self.env)
            debug("CommandThread: run: self.proc.pid", self.proc.pid)

            try:
                output = self.proc.communicate(timeout=5)[0].decode()
            except subprocess.TimeoutExpired:
                message = """Debugger is successfully started at localhost:60123.
1. Now you can open Google Chrome and navigate to chrome://inspect.
2. Then click Open dedicated DevTools for Node. 
3. After click Add connection and add connection to localhost:60123"""
                self._write_pid()
                return main_thread(self.on_done, message)

            main_thread(self.on_done, output)
        except subprocess.CalledProcessError as e:
            main_thread(self.on_done, e.returncode)
        except OSError as e:
            if e.errno == 2:
                main_thread(
                    sublime.error_message, """Node binary could not be found in PATH

                    Consider using the node_command setting for the Node plugin

                    PATH is: %s""" % os.environ['PATH'])
            else:
                raise e


class OsThread(CommandThread):

    def __init__(self, command, on_done, shell=False, working_dir="", fallback_encoding="", env={}):
        super().__init__(command, on_done, working_dir, fallback_encoding, env)
        self.shell = shell

    def run(self):
        try:
            if not self.shell:
                self.shell = os.name == 'nt'

            if self.working_dir != "":
                os.chdir(self.working_dir)

            proc = subprocess.Popen(self.command, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, shell=self.shell, env=self.env)
            output = codecs.decode(proc.communicate()[0])
            self.on_done(output)
        except subprocess.CalledProcessError as e:
            self.on_done(e.returncode, error=True)
        except OSError as e:
            self.on_done(e.message, error=True)
