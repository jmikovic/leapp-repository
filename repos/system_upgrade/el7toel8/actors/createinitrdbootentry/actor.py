from leapp.actors import Actor
from leapp.libraries.common.check_calls import check_cmd_call
from leapp.tags import IPUWorkflowTag, InterimPreparationPhaseTag


class CreateInitRdBootEntry(Actor):
    name = 'create_init_rd_boot_entry'
    description = 'No description has been provided for the create_init_rd_boot_entry actor.'
    consumes = ()
    produces = ()
    tags = (IPUWorkflowTag, InterimPreparationPhaseTag)

    def process(self):
        vmlinuz_fpath = self.get_file_path('vmlinuz-upgrade.x86_64')
        initram_fpath = self.get_file_path('initramfs-upgrade.x86_64.img')

        if vmlinuz_fpath is None or initram_fpath is None:
            self.report_error('Could not find vmlinuz-upgrade.x86_64 and/or initramfs-upgrade.x86_64.img '
                              'in the following paths: {}'.format(' '.join(self.files_paths)),
                               details='You may want to try to reinstall "leapp-repository" package')
            return

        check_cmd_call(['/bin/cp', vmlinuz_fpath, initram_fpath, '/boot'])
        check_cmd_call([
            '/usr/sbin/grubby',
            '--add-kernel=/boot/vmlinuz-upgrade.x86_64',
            '--initrd=/boot/initramfs-upgrade.x86_64.img',
            '--title=RHEL Upgrade RAMDISK',
            '--copy-default',
            '--make-default',
            '--args="debug enforcing=0 rd.plymouth=0 plymouth.enable=0"'
        ])
