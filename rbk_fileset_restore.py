#!/usr/bin/python

import rubrik_cdm
import sys
import getopt
import getpass
import urllib3
urllib3.disable_warnings()
import datetime
import pytz
import time

# A Class to hold a Rubrik Backup (snapshot)
#
class RubrikBackup:
    def __init__(self, id, date, cloud):
        self.id = id
        self.date = date
        self.cloud = cloud

    def get_id(self):
        return (str(self.id))

    def get_date(self):
        return (str(self.date))

    def is_archived(self):
        return(self.cloud)


def usage():
    sys.stderr.write("Usage: rbk_fileset_restore.py [-hlDy] [-c creds] [-r path] [-p path[,path,] backup rubrk\n")
    sys.stderr.write("-h | --help : Prints this message\n")
    sys.stderr.write("-l | --latest : Restore the latest backup\n")
    sys.stderr.write("-D | --debug : Debug mode.  Print diagnostic info\n")
    sys.stderr.write("-y | --yes : Don't confirm before running the restore job\n")
    sys.stderr.write("-c | --creds= : Specify Rubrik creds [default: prompt user]\n")
    sys.stderr.write("-r | --restore_to= : Specify a restore path\n")
    sys.stderr.write("                     Default: Overwrite Original\n")
    sys.stderr.write("                     <path>: Specify a different folder on same host\n")
    sys.stderr.write("                     <host>;<path> : Export to a different host\n")
    sys.stderr.write("-p | --paths= : Specify a list of paths to restore on the source [Default: root of the host/drive\n")
    sys.stderr.write("backup : Specify the host/fileset of the backup.  Format: <host>:<fileset>\n")
    sys.stderr.write("rubrik : Hostname or IP of the Rubrik\n\n")
    exit(0)

def dprint(message):
    if debug:
        print message
    return()

#
# We can't use a Windows drive letter as a source.  This function finds all of the first files/directories and
# creates a source path list
#
def get_path_from_source(rubrik, id):
    path_list = []
    params = {"path": "/"}
    rbk_fs = rubrik.get('v1', '/fileset/snapshot/' + str(id) + "/browse", params=params)
    for dir in rbk_fs['data']:
        if dir['fileMode'] == "drive":
            params = {"path": dir['filename']}
            rbk_path = rubrik.get('v1', '/fileset/snapshot/' + str(id) + "/browse", params=params)
            for p in rbk_path['data']:
                path_list.append(dir['filename'] + "\\" + p['filename'])
        else:
            path_list.append(dir['filename'])
    return(path_list)

#
# Make sure a host for export is registered with the Rubrik.  Also make sure the name given is unique since the
# API call will match substrings
#
def validate_host(rubrik, restore_host):
    restore_host_id = ""
    rbk_host = rubrik.get('v1', '/host?name=' + restore_host)
    if rbk_host['total'] == 1:
        return (rbk_host['data'][0]['id'])
    elif rbk_host['total'] == 0:
        print "Restore host not found"
    else:
        print "Multiple restore hosts found"
    return (restore_host_id)


if __name__ == "__main__":
    debug = False
    user = ""
    password = ""
    fileset = ""
    host = ""
    do_latest = False
    fs_id = ""
    snap_list = []
    src_path = []
    restore_location = ""
    do_confirm = True
#
# Process CLI arguments
#
    optlist, args = getopt.getopt(sys.argv[1:], 'hc:lDr:yp:', ["help", "creds=", "latest", "debug", "restore_to=", "yes", "paths="])
    for opt, a in optlist:
        if opt in ("-h", "--help"):
            usage()
        if opt in ("-c" , "--creds"):
            (user, password) = a.split(':')
        if opt in ('-l', "--latest"):
            do_latest = True
        if opt in ('-D', "--debug"):
            debug = True
        if opt in ('-r', '--restore_to'):
            restore_location = a
        if opt in ('-y', '--yes'):
            do_confirm = False
        if opt in ('-p', '--paths'):
            src_path = a.split(',')

    if args[0] == "?":
        usage()
    (backup, rubrik_node) = args
    (host, fileset) = backup.split(':')
#
# Get credentials and make initial connection to Rubrik.  Pull the timezone on the Rubrik for conversion.
# Find the fileset ID
    if not user:
        user = raw_input("User: ")
    if not password:
        password = getpass.getpass("Password: ")
    rubrik = rubrik_cdm.Connect(rubrik_node, user, password)
    rubrik_config = rubrik.get('v1', '/cluster/me')
    rubrik_tz = rubrik_config['timezone']['timezone']
    local_zone = pytz.timezone(rubrik_tz)
    utc_zone = pytz.timezone('utc')
    rubrik_fs = rubrik.get('v1', '/fileset')
    for fs in rubrik_fs['data']:
        if fs['hostName'] == host and fs['name'] == fileset:
            fs_id = fs['id']
            os_type = fs['operatingSystemType']
            break
    if not fs_id:
        sys.stderr.write("Can't find fileset\n")
        exit(1)
    dprint ("FS: " + fs_id)
#
# Grab all of the snaps and create a list of Backups using the Backup Class
#
    rubrik_snaps = rubrik.get('v1', '/fileset/' + str(fs_id))
    for snap in rubrik_snaps['snapshots']:
        s_id = snap['id']
        s_time = snap['date']
        s_time = s_time[:-5]
        snap_dt = datetime.datetime.strptime(s_time, '%Y-%m-%dT%H:%M:%S')
        snap_dt = pytz.utc.localize(snap_dt).astimezone(local_zone)
        snap_dt_s = snap_dt.strftime('%Y-%m-%d %H:%M:%S')
        if snap['cloudState'] == 0:
            s_archive = False
        else:
            s_archive = True
        snap_list.append(RubrikBackup(s_id, snap_dt, s_archive))
    index = 0
#
# Choose the correct backup
#
    if not do_latest:
        for i, snap in enumerate(snap_list):
            if snap.is_archived():
                print str(i) + ": " + snap.get_date() + " [ARCHIVED]"
            else:
                print str(i) + ": " + snap.get_date()
        valid = False
        while not valid:
            index = raw_input("Select Backup to Restore: ")
            try:
                rest_id = snap_list[int(index)].get_id()
            except (IndexError, TypeError, ValueError) as e:
                print "Invalid Index: " + str(e)
                continue
            valid = True
    else:
        i = 0
        rest_id = snap_list[0].get_id()
#
# Set the correct restore location.  Prompt user if not given on CLI with -r
#
    if not restore_location:
        valid = False
        while not valid:
            restore_location = raw_input("Restore Location [Default: Original Location]: ")
            if not restore_location:
                restore_host = host
                restore_path = ""
                valid = True
            elif ';' in restore_location:
                (restore_host, restore_path) = restore_location.split(';')
                restore_id = validate_host(rubrik, restore_host)
                if restore_id:
                    valid = True
            else:
                restore_host = host
                restore_path = restore_location
                valid = True
    else:
        if ';' in restore_location:
            (restore_host, restore_path) = restore_location.split(';')
            restore_id = validate_host(rubrik, restore_host)
            if not restore_id:
                exit(1)
#
# Set the source path if not given on the CLI with -p.  Default is root.  If default and Windows,
# get the top level files/directories.
#
    if not src_path:
        if os_type == "Windows":
            src_path = get_path_from_source(rubrik,rest_id)
        else:
            src_path = ["/"]
    dprint("SRC_PATH=" + str(src_path))
#
# Summarize the job and get user confirmation (unless -y specified)
#
    print "Restore Request:"
    print "Source: " + host + ":" + fileset + " at " + snap_list[i].get_date()
    print "Source Path: " + str(src_path)
    if restore_host == host and not restore_path:
        print "Destination: Overwrite Original"
    elif restore_host == host and restore_path:
        print "Destination: " + restore_path
    else:
        print "Destination: Export to " + restore_host + " : " + restore_path
    if do_confirm:
        confirm = raw_input("Proceed? (y/n): ")
        if not confirm.startswith('y') and not confirm.startswith('Y'):
            exit(0)
#
# Generate payload for restore job, then call restore_files or export_files
#

    if restore_host == host and not restore_path:
        payload_list = []
        if os_type == "Windows":
            for p in src_path:
                pf = p.split('\\')
                pf.pop()
                restore_path = '\\'.join(pf)
                restore_path = restore_path + "\\"
                payload_list.append({"path": p, "restorePath": restore_path})
        else:
            if not restore_path:
                restore_path = "/"
            for p in src_path:
                payload_list = [{"path": p, "restorePath": restore_path}]

        payload = {"restoreConfig": payload_list, "ignoreErrors": False}
        dprint("Restore Payload: " + str(payload))
        print "Restore job started"
        rubrik_restore = rubrik.post('internal', '/fileset/snapshot/' + snap_list[i].get_id() + '/restore_files', payload)
    elif restore_host == host and restore_path:
        payload_list = []
        for p in src_path:
            payload_list.append({"path": p, "restorePath": restore_path})
        payload = {"restoreConfig": payload_list, "ignoreErrors": False}
        dprint("Restore Payload:" + str(payload))
        print "Restore job started"
        rubrik_restore = rubrik.post('internal', '/fileset/snapshot/' + snap_list[i].get_id() + '/restore_files', payload)
    else:
        payload_list = []
        for p in src_path:
            payload_list.append({"srcPath": p, "dstPath": restore_path})
        payload = {"exportPathPairs": payload_list, "hostId": restore_id, "ignoreErrors": False}
        dprint("Restore Payload: " + str(payload))
        print "Restore job started"
        rubrik_restore = rubrik.post('internal', "/fileset/snapshot/" + snap_list[i].get_id() + "/export_files", payload)
#
# Monitor the job.  Give progress every 5 seconds.  Show success or failure
#
    job_status_url = str(rubrik_restore['links'][0]['href']).split('/')
    job_status_path = "/" + "/".join(job_status_url[5:])
    done = False
    while not done:
        restore_job_status = rubrik.get('v1', job_status_path)
        job_status = restore_job_status['status']
        if job_status in ['RUNNING', 'QUEUED', 'ACQUIRING', 'FINISHING']:
            print "Progress: " + str(restore_job_status['progress']) + "%"
            time.sleep(5)
        elif job_status == "SUCCEEDED":
            print "Done"
            done = True
        elif job_status == "TO_CANCEL" or 'endTime' in job_status:
            sys.stderr.write("Job ended with status: " + job_status + "\n")
            exit(1)
        else:
            print "Status: " + job_status










