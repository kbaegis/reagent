#!/usr/bin/sudo /usr/bin/python3

"""
This python program can be leveraged to create a CI/CD pipeline for gentoo images.
"""

import argparse
import sys
import os
import subprocess
import io
import re
import time

#Variables used elsewhere
SCRIPTPATH = os.path.dirname(os.path.realpath(__file__))
DATE = time.strftime("%Y-%m-%d") #used for image tag
TIMEZONE = "America/Denver" #adjust as needed
GITVERSION = subprocess.check_output(["git", "-C", SCRIPTPATH, "rev-parse", "HEAD"]) #appended to image metadata
REGISTRY = "crucible.lab:4000" #point to your registry
NAMESPACE = "/oci/" #adjust as needed
STAGE3URL = "https://crucible.lab/distfiles/stage3-amd64-hardened-latest.tar.bz2" #point to any valid stage3
INITIAL_FILES = [entry for entry in os.listdir(SCRIPTPATH) if re.match(r'[0-9]+.*\.buildah$', entry)]
INITIAL_FILES.sort()
EXCLUDE_FILES = set(INITIAL_FILES)
BUILDAH_FILES = []
for root, dirnames, filenames in os.walk(SCRIPTPATH):
    for filename in filenames:
        if re.match(r'.*buildah$', filename) and filename not in EXCLUDE_FILES:
            BUILDAH_FILES.append(os.path.splitext(os.path.relpath(os.path.join(root, filename), SCRIPTPATH))[0])
PROJECT_FILES = set(BUILDAH_FILES)
PUSH = []
FAILED = []

def parse_arguments(argv):
    """Parse arguments from cli-invocation"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', dest='verbose', action='store_true')
    parser.add_argument('-p', '--portage', dest='build_portage', action='store_true', help="Regenerate a container with synced portage contents.")
    parser.add_argument('-c', '--catalyst', dest='build_catalyst', action='store_true', help="Build contents of .stages/default/ with catalyst using specfiles.")
    parser.add_argument('-i', '--initial', dest='build_initial', action='store_true', help="Build all numbered buildah files in the root directory in order with buildah.")
    parser.add_argument('-b', '--build', dest='build_targets', nargs="+", help="Build selected contents matched by regex. Use 'all' to build all leaf containers.")
    args = parser.parse_args()
    return args

def portage_build(args):
    """Build portage container from host snapshot"""
    if args.build_portage is True:
        print("Building portage")
        dated_uri = ''.join([REGISTRY, NAMESPACE, "portagedir:", DATE])
        latest_uri = ''.join([REGISTRY, NAMESPACE, "portagedir:latest"])
        sync_target_run = subprocess.run(["sudo", "buildah", "from", latest_uri], stdout=subprocess.PIPE, universal_newlines=True)
        sync_target = sync_target_run.stdout.rstrip()
        sync_target_mount_run = subprocess.run(["sudo", "buildah", "mount", sync_target], stdout=subprocess.PIPE, universal_newlines=True)
        sync_target_mount = sync_target_mount_run.stdout.rstrip()
        emaint = subprocess.run(["env", ''.join(["PORTDIR=", sync_target_mount]), "emaint", "-a", "sync"], stdout=subprocess.DEVNULL)
        commit = subprocess.run(["sudo", "buildah", "commit", "--format", "oci", "--rm", "--squash", sync_target, dated_uri])
        add_latest = subprocess.run(["sudo", "buildah", "tag", dated_uri, latest_uri])
        if sync_target_run.returncode == 0 and commit.returncode == 0:
            PUSH.append(dated_uri)
            PUSH.append(latest_uri)
        else:
            FAILED.append(dated_uri)
    return

def portage_overlay(args):
    """Create portage overlay container to be mounted on gentoo containers"""
    if args.build_catalyst is True or args.build_initial is True or args.build_targets:
        print("Spawning portage")
        portagedir_container_run = subprocess.run(["sudo", "buildah", "from", ''.join([REGISTRY, NAMESPACE, "portagedir:latest"])], stdout=subprocess.PIPE, universal_newlines=True)
        portagedir_container = portagedir_container_run.stdout.rstrip()
        portagedir_container_mount_run = subprocess.run(["sudo", "buildah", "mount", portagedir_container], stdout=subprocess.PIPE, universal_newlines=True)
        portagedir_container_mount = portagedir_container_mount_run.stdout.rstrip()
        return portagedir_container_mount
    return

def catalyst_build(args, portagedir):
    """Build all stages from specfiles located in .stages/"""
    if args.build_catalyst is True:
        print("Building Catalyst")
        latest_uri = ''.join([REGISTRY, NAMESPACE, "catalyst-cache:latest"])
        emaint = subprocess.run(["emaint", "-a", "sync"], stdout=subprocess.DEVNULL)
        catalyst_cache_run = subprocess.run(["sudo", "buildah", "from", latest_uri], stdout=subprocess.PIPE, universal_newlines=True)
        catalyst_cache = catalyst_cache_run.stdout.rstrip()
        catalyst_cache_mount_run = subprocess.run(["sudo", "buildah", "mount", catalyst_cache], stdout=subprocess.PIPE, universal_newlines=True)
        catalyst_cache_mount = catalyst_cache_mount_run.stdout.rstrip()
        os.system("sudo mkdir -p /var/tmp/catalyst/packages/")
        os.system("sudo mkdir -p /usr/portage/distfiles")
        catalyst_bind_mount = subprocess.run(["sudo", "mount", "--bind", catalyst_cache_mount, "/var/tmp/catalyst/packages/"], stdout=subprocess.PIPE, universal_newlines=True)
        build_bind_mount = subprocess.run(["sudo", "mount", "--bind", ''.join([SCRIPTPATH, "/.stages"]), "/var/tmp/catalyst/builds/"], stdout=subprocess.PIPE, universal_newlines=True)
        if not os.path.isfile("/var/tmp/catalyst/builds/hardened/stage3-amd64-hardened-latest.tar.bz2"):
            print("Stage3 not found. Downloading from", STAGE3URL)
            os.system("sudo mkdir -p /var/tmp/catalyst/builds/hardened/")
            curl = subprocess.Popen(["sudo", "curl", STAGE3URL, "-o", "/var/tmp/catalyst/builds/hardened/stage3-amd64-hardened-latest.tar.bz2"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in io.TextIOWrapper(curl.stdout, encoding="ascii", errors='ignore'):
                print(line, end='', flush=True)
        specfile_list = [entry for entry in os.listdir("/var/tmp/catalyst/builds/default/") if re.match(r'.*\.spec$', entry)]
        snapshot = subprocess.run(["sudo", "catalyst", "-s", "latest"], stdout=subprocess.PIPE, universal_newlines=True)
        for specfile in specfile_list:
            print("Catalyst build using specfile: ", specfile)
            build = subprocess.Popen(["sudo", "catalyst", "-f", ''.join(["/var/tmp/catalyst/builds/default/", specfile])], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in io.TextIOWrapper(build.stdout, encoding="ascii", errors='ignore'):
                print(line, end='', flush=True)
        catalyst_bind_umount = subprocess.run(["sudo", "umount", "/var/tmp/catalyst/packages/"], stdout=subprocess.PIPE, universal_newlines=True)
        build_bind_umount = subprocess.run(["sudo", "umount", "/var/tmp/catalyst/builds/"], stdout=subprocess.PIPE, universal_newlines=True)
        commit = subprocess.run(["sudo", "buildah", "commit", "--format", "oci", "--rm", "--squash", catalyst_cache, latest_uri])
        if catalyst_cache_run.returncode == 0 and commit.returncode == 0:
            PUSH.append(latest_uri)
        else:
            FAILED.append(latest_uri)
    return

def stage3_bootstrap(args):
    """Unpack stage3 bootstrap image inside a blank container"""
    if args.build_initial is True:
        print("Bootstrapping stage3")
        dated_uri = ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened:", DATE])
        latest_uri = ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened:latest"])
        scratch_run = subprocess.run(["sudo", "buildah", "from", "scratch"], stdout=subprocess.PIPE, universal_newlines=True)
        scratch = scratch_run.stdout.rstrip()
        scratch_mount_run = subprocess.run(["sudo", "buildah", "mount", scratch], stdout=subprocess.PIPE, universal_newlines=True)
        scratch_mount = scratch_mount_run.stdout.rstrip()
        if not os.path.isfile(''.join([SCRIPTPATH, "/.stages/hardened/stage3-amd64-hardened-latest.tar.bz2"])):
            print("Stage3 not found. Downloading from", STAGE3URL)
            curllocation = ''.join(["sudo mkdir -p ", SCRIPTPATH, "/.stages/hardened"])
            print(curllocation)
            os.system(curllocation)
            curl = subprocess.Popen(["sudo", "curl", STAGE3URL, "-o", ''.join([SCRIPTPATH, "/.stages/hardened/stage3-amd64-hardened-latest.tar.bz2"])], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in io.TextIOWrapper(curl.stdout, encoding="ascii", errors='ignore'):
                print(line, end='', flush=True)
        copy_stage3 = subprocess.run(["sudo", "buildah", "add", scratch, ''.join([SCRIPTPATH, "/.stages/hardened/stage3-amd64-hardened-latest.tar.bz2"])], stdout=subprocess.PIPE, universal_newlines=True)
        #[DEFECT] - Escape characters
        #dockerinitcmd = ''.join(["sudo buildah run ", scratch, " -- sed -i -e 's/#rc_sys=\"\"/rc_sys=\"docker\"/g' /etc/rc.conf"])
        #subprocess.run(dockerinitcmd)
        #outputs sudo buildah run working-container-6 -- sed -i -e \'s/#rc_sys=""/rc_sys="docker"/g\' /etc/rc.conf
        #timezonecmd = ''.join(["printf '", TIMEZONE, "'\n|sudo tee ", scratch_mount, "/etc/timezone"])
        #print("timezonecmd: ", timezonecmd)
        #subprocess.run(timezonecmd)
        subprocess.run(["sudo", "buildah", "run", scratch, "mkdir", "-p", "/usr/portage/"])
        subprocess.run(["sudo", "buildah", "config", "--cmd", "/bin/bash", "--label", ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened"]), scratch])
        subprocess.run(["sudo", "buildah", "umount", scratch])
        commit = subprocess.run(["sudo", "buildah", "commit", "--format", "oci", "--rm", "--squash", scratch, ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened:", DATE])])
        subprocess.run(["sudo", "buildah", "tag", ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened:", DATE]), latest_uri])
        if copy_stage3.returncode == 0 and commit.returncode == 0:
            PUSH.append(latest_uri)
            PUSH.append(dated_uri)
        else:
            FAILED.append(latest_uri)
        return

def stage3_spawn(args):
    """Spawn a stage3 container from image"""
    if args.build_initial is True:
        print("Spawning stage3")
        stage3_run = subprocess.run(["sudo", "buildah", "from", ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened:latest"])], stdout=subprocess.PIPE, universal_newlines=True)
        stage3 = stage3_run.stdout.rstrip()
        return stage3
    return 0

def buildah_build(file, image_name, path):
    """Build a buildah file"""
    tag_dated = ''.join([REGISTRY, NAMESPACE, image_name, ":", DATE])
    tag_latest = ''.join([REGISTRY, NAMESPACE, image_name, ":latest"])
    logfile = open(''.join([SCRIPTPATH, '/build.log']), 'a')
    logfile.write("Python build script called with buildah for " + file + ", " + image_name + ", " + path + "\n")
    #build = subprocess.Popen(["sudo", "buildah", "bud", "-v", ''.join([portagedir, ":/usr/portage/"]), "-f", file, "-t", tag_dated, "-t", tag_latest, path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    build = subprocess.Popen(["sudo", "buildah", "bud", "-v", ''.join([portagedir, ":/usr/portage/"]), "-f", file, "-t", tag_dated, "-t", tag_latest, "--build-arg", ''.join(["BDATE=", DATE]), "--build-arg", ''.join(["GHEAD=", GITVERSION.decode("ascii")]), path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in io.TextIOWrapper(build.stdout, encoding="ascii", errors='ignore'):
        logfile.write(line)
        #print(line, end='')
    build.wait()
    if build.returncode == 0:
        PUSH.append(tag_dated)
        PUSH.append(tag_latest)
        logfile.write("Build succeeded!\n")
    else:
        FAILED.append(tag_dated)
        FAILED.append(tag_latest)
        logfile.write("Build failed.\n")
    return
    logfile.close()

def initial_build(args):
    """Build all numbered images in the root directory of the repo"""
    if args.build_initial is True:
        print("Initial images")
        for filename in INITIAL_FILES:
            buildfile = os.path.join(SCRIPTPATH, filename)
            buildpath = os.path.dirname(os.path.realpath(buildfile))
            buildname = buildfile.split('.')[1]
            buildah_build(buildfile, buildname, buildpath)
    return

def project_build(args):
    """Call buildah_build for all buildah files matching the regex passed after -b"""
    if args.build_targets:
        print("Project images")
        build_list = []
        search_expressions = []
        if any("all" in i for i in args.build_targets) or any("*" in i for i in args.build_targets):
            args.build_targets = [".*"]
        for regex in args.build_targets:
            search_expressions.append(re.compile(regex))
        for filename in PROJECT_FILES:
            if any(expression.search(filename) for expression in search_expressions):
                build_list.append(SCRIPTPATH + "/" + filename + ".buildah")
        for buildfile in build_list:
            buildpath = os.path.dirname(os.path.realpath(buildfile))
            buildname = os.path.basename(os.path.splitext(buildfile)[0])
            buildah_build(buildfile, buildname, buildpath)
        return

def cleanup():
    """Remove any remaining containers"""
    remove = subprocess.run(["sudo", "buildah", "rm", "-a"])
    #remove_images = subprocess.run(["sudo", "buildah", "rmi", "-a"])
    return

def registry_push(images):
    """Push successfully built images to registry"""
    for image in images:
        logfile = open(''.join([SCRIPTPATH, '/build.log']), 'a')
        push_run = subprocess.run(["sudo", "buildah", "push", image, ''.join(["docker://", image])], stdout=subprocess.PIPE, universal_newlines=True)
        if push_run.returncode == 0:
            logfile.write("Successfully pushed " + image + " to registry.\n")
        else:
            logfile.write("Pushing " + image + " to registry has failed.\n")
    return

##Exec block
args = parse_arguments(sys.argv[1:])
portage_build = portage_build(args)
portagedir = portage_overlay(args)
catalyst_build(args, portagedir)
stage3_bootstrap(args)
stage3 = stage3_spawn(args)
initial_build(args)
project_build(args)
print("Push: ", PUSH)
print("Failed: ", FAILED)
registry_push(PUSH)
cleanup()

##Colors
#class bcolors:
#    HEADER = '\033[95m'
#    OKBLUE = '\033[94m'
#    OKGREEN = '\033[92m'
#    WARNING = '\033[93m'
#    FAIL = '\033[91m'
#    ENDC = '\033[0m'
#    BOLD = '\033[1m'
#    UNDERLINE = '\033[4m'
#
#print bcolors.WARNING + "Warning: No active frommets remain. Continue?"
#      + bcolors.ENDC
