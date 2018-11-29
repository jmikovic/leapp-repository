import sys

from leapp.actors import Actor
from leapp.tags import FinalizationPhaseTag, IPUWorkflowTag
from leapp.models import SelinuxPermissiveDecision, FinalReport
from leapp.libraries.common.check_calls import check_cmd_call


class SetPermissiveSelinux(Actor):
    name = 'set_permissive_se_linux'
    description = 'Set SElinux into permissive mode if it was in enforcing mode'
    consumes = (SelinuxPermissiveDecision,)
    produces = (FinalReport,)
    tags = (FinalizationPhaseTag, IPUWorkflowTag)

    def process(self):
        for decision in self.consume(SelinuxPermissiveDecision):
            if decision.set_permissive:
                cmd = ['/bin/sed', '-i', 's/^SELINUX=enforcing/SELINUX=permissive/g', '/etc/selinux/config']
                err = check_cmd_call(cmd)
                if err:
                    self.produce(FinalReport(
                        severity='Error',
                        result='Fail',
                        summary='Could not set SElinux into permissive mode',
                        details=err.details,))
                    self.log.critical('Could not set SElinux into permissive mode: %s' % err_msg)
