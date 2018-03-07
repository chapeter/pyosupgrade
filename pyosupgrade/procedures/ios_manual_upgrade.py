import datetime
import time
import requests
from netmiko.ssh_exception import NetMikoTimeoutException
from pyosupgrade.tasks import generic
from ios import IOSUpgrade
from pyntc import ntc_device as NTC


class IOSManualUpgrade(IOSUpgrade):

    reload_command = "reload"

    @property
    def steps(self):
        steps = [('Backup Running Config', self.backup_running_config_status, self.backup_running_config_log_url),
                 ('Verify Boot Variable', self.verify_bootvar_status, self.verify_bootvar_status_log_url),
                 ('Reload Device', self.reload_status, self.reload_status_log_url),
                 ('State Snapshot', self.create_snapshot, self.creat_snapshot_log_url),
                 ('Verify Upgrade', self.verify_upgrade, self.verify_upgrade_log_url, self.verify_upgrade_log_url)
                 #(self.custom_verification_1_name, self.custom_verification_1_status, self.custom_verification_1_status_log_url),
                 #(self.custom_verification_2_name, self.custom_verification_2_status, self.custom_verification_2_status_log_url)
                 ]
        return steps


    #Use these commands as a verfication check pre and post upgrade
    @property
    def verification_commands(self):
        commands = [
            'show version',
            'show bootvar',
            'show inventory',
            'show environment',
            'show run',
            'show cdp neighbors',
            'show int stats',
            'show ip int brief',
            'show ip arp',
            'show spanning-tree',
            'show buffers',
            'show ip ospf neighbor',
            'show ip route'
        ]
        return commands


    def identify_platform(self):
        """
        get's supervisor information from an ASR1000X this is used to
        identify the correct image to use

        :return: str Supervisor PID
        """

        ##Collect platform information
        output = self._pyntc.show('show platform')
        if "ASR1001-X" in output:
            return "ASR1001-X", output
        elif "ISR" in output:
            return "ISR", output
        else:
            return "UNKNOWN", output


    def staging_process(self):
        print('starting staging job')
        self._attributes = self.get_job_details()
        self.device = self._attributes['device']
        self.register_custom_tasks()
        self.log("Updated job details: {}".format(self._attributes))
        self.status = "CONNECTING"
        self._pyntc = None

        try:
            self._pyntc = NTC(host=self.device,
                              username=self.username,
                              password=self.password,
                              device_type="cisco_ios_ssh")
            device = self._pyntc
            connected = device
            hostname = connected.facts['hostname']
            self.hostname = hostname
        except Exception:
            self.status = "FAILED CONNECT"
            connected = self.status


        #self.status = "IDENTIFY PLATFORM"
        #try:
        #    sup_type, sup_output = self.identify_platform()
        #except:
    #        self.status = "FAILED COULD NOT IDENTIFY PLATFORM"

    #    print("Platform identified as {}".format(sup_type))


        # Capture pre verification commands
        if self.verification_commands:
            pre_output = generic.capture_commands(connected, self.verification_commands)
            if pre_output:
                self.pre_verification_commands_status = "success"
                self.pre_verification_commands_url = self.logbin(pre_output, description="upgrade pre-verification commands for {}".format(self.device))
            else:
                self.status = "FAILED - COULD NOT GATHER VERIFICATION COMMANDS"
                exit(1)

        # Backup Running Config
        self.status = "BACKING UP RUNNING CONFIG"
        output = connected.show('show running-config')
        if output:
            self.backup_running_config_status = "success"
            logbin_url = self.logbin(output, description="backup running config for {}".format(hostname))
            self.backup_running_config_log_url = logbin_url
        self.status = "{} SNAPSHOT SUCCESSFUL".format(hostname)

        print('staging thread for {} exiting...'.format(self.device))

    def upgrade_process(self):
        print('starting staging job')
        self._attributes = self.get_job_details()
        self.device = self._attributes['device']
        reloaded = False

        # Connect to device
        try:
            connected = NTC(host=self.device,
                            username=self.username,
                            password=self.password,
                            device_type="cisco_ios_ssh")

        except NetMikoTimeoutException:
            connected = None

        # Proceed with upgrade
        self.status = "CONNECTING"
        if connected:
            hostname = connected.facts['hostname']
        else:
            hostname = None



        # Verify upgrade
        self.status = "VERIFYING UPGRADE"
        online = NTC(host=self.device,
                     username=self.username,
                     password=self.password,
                     device_type="cisco_ios_ssh")



        #custom_1 = self.custom_verification_1()
        #custom_2 = self.custom_verification_2()

        # Capture post verification commands
        if self.verification_commands:
            post_output = generic.capture_commands(online, self.verification_commands)
            if post_output:
                self.post_verification_commands_status = "success"
                descr = "post upgrade verification commands for {}".format(self.device)
                self.post_verification_commands_url = self.logbin(post_output,
                                                                  description=descr)
            else:
                self.status = "FAILED - COULD NOT GATHER POST VERIFICATION COMMANDS"
                exit(1)

        if all([online]):
            self.status = "{} UPGRADE COMPLETE".format(hostname)
            print("Upgrade was successful")
        else:
            self.status = "UPGRADE FAILED"
            print("UPGRADE FAILED")

        end = datetime.datetime.now()

#    def custom_verification_1(self):
#        return True

#    def custom_verification_2(self):
#        return True
