import contextlib
import os
import signal

import six
import subprocess
from collections import namedtuple

ErrorData = namedtuple('ErrorData', ['summary', 'details', 'stdout', 'stderr', 'cmd', 'rc', 'errno'])

'''
Temporary solution until refactor
'''

if six.PY2:
    class LeappCalledProcessError(subprocess.CalledProcessError):
        def __init__(self, returncode, cmd, output=None, stderr=None):
            super(LeappCalledProcessError, self).__init__(returncode=returncode, cmd=cmd, output=output)
            self.stderr = stderr

        def __str__(self):
            if self.returncode and self.returncode < 0:
                try:
                    return "Command '%s' died with %r." % (
                        self.cmd, signal.Signals(-self.returncode))
                except ValueError:
                    return "Command '%s' died with unknown signal %d." % (
                        self.cmd, -self.returncode)
            else:
                return "Command '%s' returned non-zero exit status %d." % (
                    self.cmd, self.returncode)

        @property
        def stdout(self):
            """Alias for output attribute, to match stderr"""
            return self.output

        @stdout.setter
        def stdout(self, value):
            # There's no obvious reason to set this, but allow it anyway so
            # .stdout is a transparent alias for .output
            self.output = value


    class CompletedProcess(object):
        """A process that has finished running.

        This is returned by run().

        Attributes:
          args: The list or str args passed to run().
          returncode: The exit code of the process, negative for signals.
          stdout: The standard output (None if not captured).
          stderr: The standard error (None if not captured).
        """
        def __init__(self, args, returncode, stdout=None, stderr=None):
            self.args = args
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

        def __repr__(self):
            args = ['args={!r}'.format(self.args), 'returncode={!r}'.format(self.returncode)]
            if self.stdout is not None:
                args.append('stdout={!r}'.format(self.stdout))
            if self.stderr is not None:
                args.append('stderr={!r}'.format(self.stderr))
            return "{}({})".format(type(self).__name__, ', '.join(args))

        def check_returncode(self):
            """Raise CalledProcessError if the exit code is non-zero."""
            if self.returncode:
                raise LeappCalledProcessError(self.returncode, self.args, self.stdout, self.stderr)
else:
    LeappCalledProcessError = subprocess.CalledProcessError
    CompletedProcess = subprocess.CompletedProcess


def produce_error(actor, error):
    actor.report_error('Error: %s: %s' % (error.summary, error.details),
                       details={'output': error.stdout, 'error': error.stderr, 'command': error.cmd,
                                'return_code': error.rc, 'errno': error.errno})


@contextlib.contextmanager
def _safe_popen(*args, **kwargs):
    def clean(process):
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()
        try:  # Flushing a BufferedWriter may raise an error
            if process.stdin:
                process.stdin.close()
        except:
            # If it does we swallow it because we might be inside another exception handling
            pass

    process = subprocess.Popen(*args, **kwargs)
    try:
        yield process
    except:
        clean(process)
        raise
    clean(process)


def _execute_cmd(cmd, input=None, check=False, **kwargs):
    with _safe_popen(cmd, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(input)
        except:
            process.kill()
            process.wait()
            raise
        retcode = process.poll()
        if check and retcode:
            raise LeappCalledProcessError(retcode, cmd, output=stdout, stderr=stderr)
        return CompletedProcess(cmd, retcode, stdout=stdout, stderr=stderr)


def _check_cmd(cmd):
    try:
        r = _execute_cmd(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, check=True)
    except LeappCalledProcessError as e:
        return None, ErrorData(
            summary='Error while trying to execute command',
            details=str(e),
            stdout=e.output,
            stderr=e.stderr,
            cmd=cmd,
            rc=e.returncode,
            errno=0)
    except OSError as e:
        return None, ErrorData(
            summary='Could not execute command',
            details=str(e),
            stdout=None,
            stderr=None,
            cmd=cmd,
            rc=None,
            errno=e.errno)
    return r, None


def check_cmd_call(cmd):
    unused, err = _check_cmd(cmd)
    return err


def check_cmd_output(cmd, split=True):
    ''' Call external processes with some additional sugar '''
    output, err = _check_cmd(cmd)
    if output:
        output = output.decode('utf-8')
    if output and split:
        output = output.splitlines()
    return output, err


if __name__ == '__main__':
    from pprint import pprint
    pprint(
        check_cmd_call(['ip', 'a'])
    )
