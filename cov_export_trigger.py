
import time
import os.path
from os import path
from ats import aetest
import lib.commons.commons as ftltest
from lib.common_modules.cli_connection import get_cli_connection
from tests.feature.fmc.policies.access_control.access_control.time_based_acl.time_based_acl_utils import *
import argparse
import enum

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

timeout = 900


class Device(enum.Enum):
    device_list = ['76', '77', '78', '79', '80', '75']
    fmc_list = ['66']


def execute_linux_command(ssh_connection, script_file_path):
    return ssh_connection.execute('if [ -f {0} ] ; then echo "Yes..! File Exist..! Its Coverage build.!" ; '
                                  'else echo "No such file or directory" ; fi'.format(script_file_path),
                                  timeout=10)

def check_cov_export_file_in_device(connection, script_path):
    result = True
    connection.go_to('sudo_state')
    for i in range(0, 10):
        response = execute_linux_command(connection, script_path)
        log.info("Try {} - response : {}".format(str(i), response))
        if response != '':
            log.info("response content is not empty, so breaking the loop")
            break
    if 'No such file or directory'.lower() in response.lower():
        result = False
    return result


class CommonSetup(ftltest.CommonSetup):
    pass

    def __enter__(self):
        output = super().__enter__()
        parser = argparse.ArgumentParser()
        # Destination Server Details
        parser.add_argument("--destination_server", dest='destination_server',
                            help='destination_server server in to which archive files will be uploaded', default='None')
        parser.add_argument("--destination_server_user", dest='destination_server_user',
                            help='destination server user in to which archive files will be uploaded', default='None')
        parser.add_argument("--destination_server_pwd", dest='destination_server_pwd',
                            help='destination server pwd in to which archive files will be uploaded', default='None')
        parser.add_argument("--destination_server_loc", dest='destination_server_loc',
                            help='destination server location in to which archive files will be uploaded', default='None')

        parser.add_argument("--feature_name", dest='feature_name',
                            help='feature name', default='NOT_SET')

        args, unknown = parser.parse_known_args(self.cli_args)
        self.parameters.update(args=args)

        self.parent.parameters.update(destination_server=args.destination_server)
        self.parent.parameters.update(destination_server_user=args.destination_server_user)
        self.parent.parameters.update(destination_server_pwd=args.destination_server_pwd)
        self.parent.parameters.update(destination_server_loc=args.destination_server_loc)

        self.parent.parameters.update(feature_name=args.feature_name)

        log.info('destination_server is: ' + str(args.destination_server))
        log.info('destination_server_user is: ' + str(args.destination_server_user))
        log.info('destination_server_pwd is: ' + str(args.destination_server_pwd))
        log.info('destination_server_loc is: ' + str(args.destination_server_loc))

        log.info('feature_name is: ' + str(args.feature_name))
        return output

    @aetest.subsection
    def get_cli_conn_for_devices(self, testbed):
        cli_connection_dict = {}
        for each_device in testbed.devices:
            value_list = []
            if testbed.devices.get(each_device).custom.get('model_number', None):
                if str(testbed.devices.get(each_device).custom.model_number) in Device.device_list.value + Device.fmc_list.value:
                    cli_connection = get_cli_connection(testbed, device_label=each_device)
                    if str(testbed.devices.get(each_device).custom.model_number) in Device.fmc_list.value:
                        result = check_cov_export_file_in_device(cli_connection,"/var/sf/bin/cov-export.sh")
                        device_type = 'fmc'
                    elif str(testbed.devices.get(each_device).custom.model_number) in Device.device_list.value:
                        result = check_cov_export_file_in_device(cli_connection, "/ngfw/var/sf/bin/cov-export.sh")
                        device_type = 'ftd'
                    if result:
                        value_list.append(cli_connection)
                        value_list.append(device_type)
                        cli_connection_dict[each_device] = value_list
        self.parent.parameters.update(cli_connection_dict=cli_connection_dict)


class UploadFilesToServer(aetest.Testcase):

    """
        This Class will upload files from FMC and FTD to Server
    """

    @aetest.test
    def upload_files_to_server(self, cli_connection_dict, destination_server, destination_server_user,
                               destination_server_pwd, destination_server_loc, feature_name):
        each_identifier = ' -a -g -j -p -s -d -3'
        if len(cli_connection_dict.keys()) > 0:
            for each_device_connection in cli_connection_dict.keys():
                cli_connection_dict[each_device_connection][0].go_to('sudo_state')
                self.upload_files(feature_name, each_identifier, destination_server_user, destination_server, destination_server_loc,
                                  destination_server_pwd, cli_connection_dict[each_device_connection][0],
                                  each_device_connection, cli_connection_dict)
                # cli_connection_dict[each_device_connection][0]. \
                #     execute('/etc/rc.d/init.d/pm restart', timeout=timeout, exception_on_bad_command=True,
                #             prompt='Stopping pm:')
        else:
            self.passed("This pipeline is not triggered for Code Coverage Build. So, skipping Upload files section")

    def upload_files(self, feature_name, each_identifier, server_username, server, server_loc,
                     server_pwd, ssh_connection, each_device_connection, cli_connection_dict):
        script_fine_name = ""
        if cli_connection_dict[each_device_connection][1] == "fmc":
            script_fine_name = '/var/sf/bin/cov-export.sh'
        elif cli_connection_dict[each_device_connection][1] == "ftd":
            script_fine_name = '/ngfw/var/sf/bin/cov-export.sh'
        try:
            export_command = script_fine_name + ' -f  "' + feature_name + '" '+ str(each_identifier) + ' ' \
                             + str(server_username) + ' ' + str(server) + '  "' + str(server_loc) + '"'
            log.info('export command to execute : ' + str(export_command))
            response = ssh_connection. \
                execute(export_command, timeout=timeout, exception_on_bad_command=False,
                        prompt='[Pp]assword:|fingerprint\]\)\?\s+')
        except Exception as err:
            self.failed("Generation of files Failed with error {} ".format(err))

        log.info('response post executing export command : ' + str(response))

        time.sleep(5)

        try:
            if 'fingerprint' in response:
                response = ssh_connection. \
                    execute('yes', timeout=timeout, exception_on_bad_command=True,
                            prompt='[Pp]assword:|fingerprint|firepower:~#')
                log.info('response post sending -> yes : ' + str(response))
        except Exception as err:
            log.failed("Error occurred while trying to add host to list of know hosts {} ".format(err))

        try:
            log.info('response is ' + str(response))

            response = ssh_connection. \
                    execute(str(server_pwd), timeout=timeout, exception_on_bad_command=True,
                            prompt='[Pp]assword:|fingerprint|firepower:~#')
            if '100%' in response:
                log.info('Uploaded file from device ' + each_device_connection +
                         ' to cerebro server successfully!!!')

            ssh_connection. \
                execute('/etc/rc.d/init.d/pm restart', timeout=timeout, exception_on_bad_command=True,
                        prompt='Stopping pm:')

        except Exception as err:
            log.failed("Password provided looks incorrect or exception in restarting pm tool. "
                       "check this exception for more info \n {} ".format(err))


if __name__ == '__main__':
    aetest.main()
