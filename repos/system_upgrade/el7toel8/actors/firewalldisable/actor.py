from leapp.actors import Actor
from leapp.libraries.common.check_calls import check_cmd_call, check_cmd_output, produce_error
from leapp.models import FirewallDecisionM, CheckResult, SystemFacts
from leapp.tags import IPUWorkflowTag, ApplicationsPhaseTag


class FirewallDisable(Actor):
    name = 'firewalld_disable'
    description = ('Disables and stops FirewallD and IPTables, so the daemons'
                   'are not started after the boot into RHEL8 (stage Before).')
    consumes = (FirewallDecisionM, SystemFacts)
    produces = (CheckResult,)
    tags = (IPUWorkflowTag, ApplicationsPhaseTag,)

    def stop_firewalld(self):
        ''' Stops FirewallD '''
        err = check_cmd_call(['systemctl', 'stop', 'firewalld'])
        if err:
            produce_error(self, err)

    def disable_firewalld(self):
        ''' Disables FirewallD '''
        self.stop_firewalld()
        err = check_cmd_call(['systemctl', 'disable', 'firewalld'])
        if err:
            produce_error(self, err)

    def save_iptables(self):
        ''' Saves IPTables '''
        f = open('iptables_bck_workfile', 'w')
        ret, err = check_cmd_output(['iptables-save'])
        if err:
            produce_error(self, err)
        for line in ret:
            f.write(line+'\n')
        f.close()

    def stop_iptables(self):
        ''' Stops IPTables '''
        err = check_cmd_call(['systemctl', 'stop', 'iptables'])
        if err:
            produce_error(self, err)

    def flush_iptables(self):
        ''' Flushes rules '''
        err = check_cmd_call(['iptables', '-F'])
        if err:
            produce_error(self, err)

    def disable_iptables(self):
        ''' Saves, stops and disables IPTables '''
        self.save_iptables()
        self.flush_iptables()
        self.stop_iptables()
        err = check_cmd_call(['systemctl', 'disable', 'iptables'])
        if err:
            produce_error(self, err)

    def process(self):
        ''' based on a decision maker Actor, it disables firewall services '''
        self.log.info("Starting to get decision on FirewallD.")
        for decision in self.consume(FirewallDecisionM):
            if decision.disable_choice == 'Y':
                self.log.info("Disabling Firewall.")
                for facts in self.consume(SystemFacts):
                    if facts.firewalls.iptables.enabled:
                        self.log.info("- IPTables.")
                        self.disable_iptables()
                        break
                    elif facts.firewalls.firewalld.enabled:
                        self.log.info("- FirewallD.")
                        self.disable_firewalld()
                        break
                    else:
                        continue

                self.log.info("Firewalls are disabled.")
                self.produce(
                   CheckResult(
                       severity='Info',
                       result='Pass',
                       summary='Firewalls are disabled',
                       details='FirewallD and/or IPTables services are disabled.',
                       solutions=None
                       ))
                return
            elif decision.disable_choice == 'N':
                self.log.info("Interrupting the upgrade process due the current user choice to take care for Firewall manually.")
                return
            elif decision.disable_choice == 'S':
                self.log.info("Skipping - all should be disabled.")
                return
        else:
            self.log.info("Interrupting: There was nothing to consume regarding the Firewall decision.")
            self.produce(
                CheckResult(
                    severity='Error',
                    result='Fail',
                    summary='No message to consume',
                    details='No decision message to consume.',
                    solutions=None
                    ))
            return
