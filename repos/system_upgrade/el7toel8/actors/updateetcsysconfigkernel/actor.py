from leapp.actors import Actor
from leapp.libraries.common import check_cmd_call
from leapp.tags import PreparationPhaseTag, IPUWorkflowTag


class UpdateEtcSysconfigKernel(Actor):
    name = 'update_etc_sysconfig_kernel'
    description = 'Updates /etc/sysconfig/kernel DEFAULTKERNEL entry from kernel to kernel-core.'
    consumes = ()
    produces = ()
    tags = (PreparationPhaseTag, IPUWorkflowTag)

    def process(self):
        check_cmd_call(['/bin/sed', '-i', 's/^DEFAULTKERNEL=kernel$/DEFAULTKERNEL=kernel-core/g', '/etc/sysconfig/kernel'])
