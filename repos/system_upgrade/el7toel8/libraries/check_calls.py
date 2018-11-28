import subprocess
from collections import namedtuple

ErrorData = namedtuple('ErrorData', ['summary', 'details', 'stdout', 'stderr', 'cmd', 'rc', 'errno'])

'''
Temporary solution until refactor
'''


def produce_error(actor, error):
    actor.report_error('Error: %s: %s' % (error.summary, error.details),
                       details={'output': error.stdout, 'error': error.stderr, 'command': error.cmd,
                                'return_code': error.rc, 'errno': error.errno})


def check_cmd_call(cmd):
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        return ErrorData(
            summary='Error while trying to execute command',
            details=str(e),
            stdout=e.stdout,
            stderr=e.stderr,
            cmd=cmd,
            rc=e.returncode,
            errno=0)
    except OSError as e:
        return ErrorData(
            summary='Could not execute command',
            details=str(e),
            stdout=None,
            stderr=None,
            cmd=cmd,
            rc=None,
            errno=e.errno)
    return None
