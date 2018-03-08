import datetime
import time
import requests
from netmiko.ssh_exception import NetMikoTimeoutException
from pyosupgrade.tasks import generic
from ios import IOSUpgrade
from pyntc import ntc_device as NTC
from ..views.diffview import binary_diff

class IOSManualUpgrade(IOSUpgrade):

    reload_command = "reload"

    @property
    # def steps(self):
    #     steps = [('Backup Running Config', self.backup_running_config_status, self.backup_running_config_log_url),
    #              ('Verify Boot Variable', self.verify_bootvar_status, self.verify_bootvar_status_log_url),
    #              ('State Snapshot', self.create_snapshot, self.creat_snapshot_log_url),
    #              ('Verify Upgrade', self.verify_upgrade, self.verify_upgrade_log_url, self.verify_upgrade_log_url)
    #              ]
    #     return steps
    def steps(self):
        steps = [('Pre Upgrade Running Config', self.get_running_config_status, self.running_config_url),
                 ('Post Upgrade Running Config', self.get_post_running_config_status, self.post_running_config_url),
                 ('Pre Upgrade Version', self.get_pre_version_status, self.pre_version_url),
                 ('Post Upgrade Version', self.get_post_version_status, self.post_version_url),
                 ('Pre Upgrade BOOTVAR', self.pre_bootvar_status, self.pre_bootvar_url),
                 ('Post Upgrade BOOTVAR', self.post_bootvar_status, self.post_bootvar_url)
                ]
        return steps

    @property
    def get_running_config_status(self):
        return self._attributes.get('get_running_config_status', "default")

    @get_running_config_status.setter
    def get_running_config_status(self, status):
        self._attributes['get_running_config_status'] = status
        self._update_job()

    @property
    def running_config_url(self):
        return self._attributes.get('running_config_url', "default")

    @running_config_url.setter
    def running_config_url(self, url):
        self._attributes['running_config_url'] = url
        self._update_job()

    @property
    def get_post_running_config_status(self):
        return self._attributes.get('get_post_running_config_status', "default")

    @get_post_running_config_status.setter
    def get_post_running_config_status(self, status):
        self._attributes['get_post_running_config_status'] = status
        self._update_job()

    @property
    def post_running_config_url(self):
        return self._attributes.get('post_running_config_url', "default")

    @post_running_config_url.setter
    def post_running_config_url(self, url):
        self._attributes['post_running_config_url'] = url
        self._update_job()

    @property
    def get_pre_version_status(self):
        return self._attributes.get('get_pre_version_status', "default")

    @get_pre_version_status.setter
    def get_pre_version_status(self, status):
        self._attributes['get_pre_version_status'] = status
        self._update_job()

    @property
    def pre_version_url(self):
        return self._attributes.get('pre_version_url', "default")

    @pre_version_url.setter
    def pre_version_url(self, url):
        self._attributes['pre_version_url'] = url
        self._update_job()

    @property
    def get_post_version_status(self):
        return self._attributes.get('get_post_version_status', "default")

    @get_post_version_status.setter
    def get_post_version_status(self, status):
        self._attributes['get_post_version_status'] = status
        self._update_job()

    @property
    def post_version_url(self):
        return self._attributes.get('post_version_url', "default")

    @post_version_url.setter
    def post_version_url(self, url):
        self._attributes['post_version_url'] = url
        self._update_job()

    @property
    def pre_bootvar_status(self):
        return self._attributes.get('pre_bootvar_status', "default")

    @pre_bootvar_status.setter
    def pre_bootvar_status(self, status):
        self._attributes['pre_bootvar_status'] = status
        self._update_job()

    @property
    def pre_bootvar_url(self):
        return self._attributes.get('pre_bootvar_url', "default")

    @pre_bootvar_url.setter
    def pre_bootvar_url(self, url):
        self._attributes['pre_bootvar_url'] = url
        self._update_job()

    @property
    def post_bootvar_status(self):
        return self._attributes.get('post_bootvar_status', "default")

    @post_bootvar_status.setter
    def post_bootvar_status(self, status):
        self._attributes['post_bootvar_status'] = status
        self._update_job()

    @property
    def post_bootvar_url(self):
        return self._attributes.get('post_bootvar_url', "default")

    @post_bootvar_url.setter
    def post_bootvar_url(self, url):
        self._attributes['post_bootvar_url'] = url
        self._update_job()






    #Use these commands as a verfication check pre and post upgrade
    @property
    def verification_commands(self):
        commands = [
            'show ver | i Cisco | i Version',
            'show bootvar | i BOOT variable',
            'show inventory',
            'show run',
            'show cdp neighbors',
            'show int stats',
            'show ip int brief',
            'show ip arp',
            'show spanning-tree',
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
        print('starting snapshot job')
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
        self.status = "Getting Configuration"
        output = device.native.send_command('show running-config')
        self.running_config_url = self.logbin(output)
        if len(output) > 0:
            self.get_running_config_status = "success"
            self.status = "SUCCESS"
        else:
            self.get_running_config_status = "warn"
            self.status = "WARNING"

        #Get Version
        self.status = "Getting Version"
        output = device.native.send_command('show ver | i Cisco | i Version')
        self.pre_version_url = self.logbin(output)
        if len(output) > 0:
            self.get_pre_version_status = "success"
            self.status = "SUCCESS"
        else:
            self.get_pre_version_status = "warn"
            self.status = "WARNING"

        #Get Bootvar
        self.status = "Getting Bootvar"
        output = device.native.send_command('show bootvar | i BOOT variable')
        self.pre_bootvar_url = self.logbin(output)
        if len(output) > 0:
            self.pre_bootvar_status = "success"
            self.status = "SUCCESS"
        else:
            self.pre_bootvar_status = "warn"
            self.status = "WARNING"

        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
        for key, value in self._attributes.iteritems():
            if "status" in key:
                if value.lower() == 'success':
                    print("Success")
                    print(key, value)
                    self.status = "{} Pre-Upgrade SNAPSHOT SUCCESSFUL".format(hostname)
                else:
                    print("Not")
                    print(key,value)
                    self.status = "{} Pre-Upgrade SNAPSHOT Detects a Problem".format(hostname)
                    break
            print("\n")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
        #self.status = "{} Pre-Upgrade SNAPSHOT SUCCESSFUL".format(hostname)

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
            device = connected
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

        self.status = "Getting Configuration"

        output = device.native.send_command('show running-config')
        self.post_running_config_url = self.logbin(output)
        if len(output) > 0:
            self.get_post_running_config_status = "success"
            self.status = "SUCCESS"
        else:
            self.get_post_running_config_status = "warn"
            self.status = "WARNING"


        #Get Version
        self.status = "Getting Version"
        output = device.native.send_command('show ver | i Cisco | i Version')
        self.post_version_url = self.logbin(output)
        if binary_diff(self.pre_version_url, self.post_version_url) == True:
            self.get_post_version_status = "success"
            self.status = "SUCCESS"
        else:
            self.get_post_version_status = "danger"
            self.status = "DANGER"


        #Validate Bootvar
        self.status = "Getting Bootvar"
        output = device.native.send_command('show bootvar | i BOOT variable')
        self.post_bootvar_url = self.logbin(output)
        if binary_diff(self.pre_bootvar_url, self.post_bootvar_url) == True:
            self.post_bootvar_status = "success"
            self.status = "SUCCESS"
        else:
            self.post_bootvar_status = "danger"
            self.status = "DANGER"


        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
        for key, value in self._attributes.iteritems():
            if "status" in key:
                if value.lower() == 'success':
                    print("Success")
                    print(key, value)
                    self.status = "{} Post Upgrade SNAPSHOT SUCCESSFUL".format(hostname)
                else:
                    print("Not")
                    print(key,value)
                    self.status = "{} Post Upgrade SNAPSHOT Detects a Problem".format(hostname)
                    break
            print("\n")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")

        # if all([online]):
        #     self.status = "{} Post Upgrade Snapshot Successful".format(hostname)
        #     print("Post Upgrade Snapshot Successful")
        # else:
        #     self.status = "Post Upgrade Snapshot Failed"
        #     print("Post Upgrade Snapshot Failed")

        end = datetime.datetime.now()
