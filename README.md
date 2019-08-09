# rbk_fileset_restore
A script to restore physical fileset from Rubrik

The purpose of this script is to execute restores of physical filesets (Windows/Linux/UNIX) from outside of the Rubrik UI.

Usage: rbk_fileset_restore.py [-hlDy] [-c creds] [-r path] [-p path[,path,] backup rubrk
-h | --help : Prints this message
-l | --latest : Restore the latest backup
-D | --debug : Debug mode.  Print diagnostic info
-y | --yes : Don't confirm before running the restore job
-c | --creds= : Specify Rubrik creds [default: prompt user]
-r | --restore_to= : Specify a restore path
                     Default: Overwrite Original
                     <path>: Specify a different folder on same host
                     <host>;<path> : Export to a different host
-p | --paths= : Specify a list of paths to restore on the source [Default: root of the host/drive
backup : Specify the host/fileset of the backup.  Format: <host>:<fileset>
rubrik : Hostname or IP of the Rubrik

Notes:
If the -l flag is not specified, the system will display a list of available backups and allow the user to choose one.
Use of -c is not particulary secure as the credentials will be on the command line.  The default is to prompt the user.
In order to export to another host, that host must be registered with the Rubrik and be a compatible type (Windows, Linux, etc)
This script works for filesets, it has not expected to work for volume backups.

Feel free to reach out with any questions
