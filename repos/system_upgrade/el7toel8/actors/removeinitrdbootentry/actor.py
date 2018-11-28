from leapp.actors import Actor
from leapp.libraries.common.check_calls import check_cmd_call
from leapp.tags import IPUWorkflowTag, InitRamStartPhaseTag


class RemoveInitRdBootEntry(Actor):
    name = 'remove_init_rd_boot_entry'
    description = 'No description has been provided for the remove_init_rd_boot_entry actor.'
    consumes = ()
    produces = ()
    tags = (IPUWorkflowTag, InitRamStartPhaseTag)

    def process(self):
        check_cmd_call([
            '/bin/mount', '-a'
        ])
        check_cmd_call([
            '/usr/sbin/grubby',
            '--remove-kernel=/boot/vmlinuz-upgrade.x86_64'
        ])
