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
import shlex

#Please adjust to fit your environment
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
BUILT = []
FAILED = []
SUCCEEDED = []
#LOGFILE = open(''.join([SCRIPTPATH, '/build.log']), 'a', 1)
LOGFILE = ''.join([SCRIPTPATH, '/build.log'])

class bcolors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    GREY = '\033[0;37m'
    YELLOW = '\033[33m'
    WARNING = '\033[93m'
    RED = '\033[31m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class SubprocessReturn(object):
    def __init__(self, call, output):
        self.call = call
        self.output = output

def parse_arguments(arguments):
    """Parse arguments from cli-invocation"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help="Show verbose output from subprocess commands.")
    parser.add_argument('-p', '--portage', dest='build_portage', action='store_true', help="Regenerate a container with synced portage contents.")
    parser.add_argument('-c', '--catalyst', dest='build_catalyst', action='store_true', help="Build contents of .stages/default/ with catalyst using specfiles.")
    parser.add_argument('-i', '--initial', dest='build_initial', action='store_true', help="Build all numbered buildah files in the root directory in order with buildah.")
    parser.add_argument('-b', '--build', dest='build_targets', nargs="+", help="Build selected contents matched by regex. Use 'all' to build all leaf containers.")
    args = parser.parse_args(arguments)
    return args

def sp_run(command, verbose=False):
    output_list = []
    with open(LOGFILE, 'a', 1) as log:
        subprocess_call = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        with io.TextIOWrapper(subprocess_call.stdout, encoding="ascii", errors='ignore', write_through=True) as wrapper:  
            for line in wrapper:
                if verbose == True:
                    colorizedline = (bcolors.GREY + line + bcolors.ENDC)
                    print(colorizedline, end="")
                log.write(line)
                log.flush()
                output_list.append(line)
            subprocess_call.wait()
    return SubprocessReturn(subprocess_call, output_list)

def portage_build(build_portage, verbose=False):
    """Build portage container from host snapshot"""
    if build_portage is True:
        log = open(LOGFILE, 'a', 1)
        print(bcolors.YELLOW + bcolors.BOLD + "Building portage" + bcolors.ENDC)
        log.write("Building portage\n")
        dated_uri = ''.join([REGISTRY, NAMESPACE, "portagedir:", DATE])
        latest_uri = ''.join([REGISTRY, NAMESPACE, "portagedir:latest"])
        sync_target_run = sp_run("sudo buildah from " + latest_uri, verbose)
        sync_target = sync_target_run.output[-1].rstrip()
        sync_target_mount_run = sp_run("sudo buildah mount " + sync_target, verbose)
        sync_target_mount = sync_target_mount_run.output[-1].rstrip()
        emaint = sp_run("env " + ''.join(["PORTDIR=", sync_target_mount]) + " emaint -a sync", verbose)
        commit = sp_run("sudo buildah commit --format oci --rm -q --squash " + sync_target + " " + dated_uri, verbose)
        add_latest = sp_run(" sudo buildah tag " + dated_uri + " " + latest_uri, verbose)
        if sync_target_run.call.returncode == 0 and commit.call.returncode == 0:
            BUILT.append(dated_uri)
            BUILT.append(latest_uri)
        else:
            FAILED.append(dated_uri)
        log.close()

def portage_overlay(args, verbose=False):
    """Create portage overlay container to be mounted on gentoo containers"""
    if args.build_catalyst is True or args.build_initial is True or args.build_targets:
        log = open(LOGFILE, 'a', 1)
        print(bcolors.YELLOW + bcolors.BOLD + "Spawning portage" + bcolors.ENDC)
        log.write("Spawning portage\n")
        portagedir_container_run = sp_run("sudo buildah from " + ''.join([REGISTRY, NAMESPACE, "portagedir:latest"]), verbose)
        portagedir_container = portagedir_container_run.output[-1].rstrip()
        portagedir_container_mount_run = sp_run("sudo buildah mount " + portagedir_container, verbose)
        portagedir_container_mount = portagedir_container_mount_run.output[-1].rstrip()
        log.close()
        return portagedir_container_mount

def catalyst_build(portagedir, verbose=False):
    """Build all stages from specfiles located in .stages/"""
    if args.build_catalyst is True:
        log = open(LOGFILE, 'a', 1)
        print(bcolors.YELLOW + bcolors.BOLD + "Building Catalyst" + bcolors.ENDC)
        log.write("Building Catalyst\n")
        latest_uri = ''.join([REGISTRY, NAMESPACE, "catalyst-cache:latest"])
        emaint = sp_run("emaint -a sync", verbose)
        catalyst_cache_run = sp_run("sudo buildah from " + latest_uri, verbose)
        catalyst_cache = catalyst_cache_run.output[-1].rstrip()
        catalyst_cache_mount_run = sp_run("sudo buildah mount " + catalyst_cache, verbose)
        catalyst_cache_mount = catalyst_cache_mount_run.output[-1].rstrip()
        os.system("sudo mkdir -p /var/tmp/catalyst/packages/")
        os.system("sudo mkdir -p /usr/portage/distfiles")
        catalyst_bind_mount = sp_run("sudo mount --bind " + catalyst_cache_mount + " /var/tmp/catalyst/packages/", verbose)
        build_bind_mount = sp_run("sudo mount --bind " + ''.join([SCRIPTPATH, "/.stages"]) + " /var/tmp/catalyst/builds/", verbose)
        if not os.path.isfile("/var/tmp/catalyst/builds/hardened/stage3-amd64-hardened-latest.tar.bz2"):
            print(bcolors.YELLOW + bcolors.BOLD + "Stage3 not found. Downloading from " + STAGE3URL + "\n" + bcolors.ENDC)
            log.write("Stage3 not found. Downloading from " + STAGE3URL + "\n")
            os.system("sudo mkdir -p /var/tmp/catalyst/builds/hardened/")
            curl = sp_run("sudo curl -s " + STAGE3URL + " -o /var/tmp/catalyst/builds/hardened/stage3-amd64-hardened-latest.tar.bz2", verbose)
        specfile_list = [entry for entry in os.listdir("/var/tmp/catalyst/builds/default/") if re.match(r'.*\.spec$', entry)]
        snapshot = sp_run("sudo catalyst -s latest", verbose)
        for specfile in specfile_list:
            print(bcolors.YELLOW + bcolors.BOLD + "Catalyst build using specfile: " + specfile + bcolors.ENDC)
            log.write("Catalyst build using specfile: " + specfile + "\n")
            build = sp_run("sudo catalyst -f " + ''.join(["/var/tmp/catalyst/builds/default/", specfile]), verbose)
        catalyst_bind_umount = sp_run("sudo umount /var/tmp/catalyst/packages/", verbose)
        build_bind_umount = sp_run("sudo umount /var/tmp/catalyst/builds/", verbose)
        commit = sp_run("sudo buildah commit --format oci --rm -q --squash " + catalyst_cache + " " + latest_uri, verbose)
        if catalyst_cache_run.call.returncode == 0 and commit.call.returncode == 0:
            print(bcolors.BLUE + bcolors.BOLD + "Build of " + latest_uri + " succeeded.\n" + bcolors.ENDC)
            log.write("Build of " + latest_uri + " succeeded.\n")
            BUILT.append(latest_uri)
        else:
            print(bcolors.RED + bcolors.BOLD + "Build of " + latest_uri + " failed.\n" + bcolors.ENDC)
            log.write("Build of " + latest_uri + " failed\n")
            FAILED.append(latest_uri)
        log.close()

def stage3_bootstrap(build_initial, verbose=False):
    """Unpack stage3 bootstrap image inside a blank container"""
    if build_initial is True:
        log = open(LOGFILE, 'a', 1)
        print(bcolors.YELLOW + bcolors.BOLD + "Bootstrapping stage3" + bcolors.ENDC)
        log.write("Bootstrapping stage3\n")
        dated_uri = ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened:", DATE])
        latest_uri = ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened:latest"])
        scratch_run = sp_run("sudo buildah from scratch", verbose)
        scratch = scratch_run.output[-1].rstrip()
        scratch_mount_run = sp_run("sudo buildah mount " + scratch, verbose)
        scratch_mount = scratch_mount_run.output[-1].rstrip()
        if not os.path.isfile(''.join([SCRIPTPATH, "/.stages/hardened/stage3-amd64-hardened-latest.tar.bz2"])):
            print(bcolors.YELLOW + bcolors.BOLD + "Stage3 not found. Downloading from " + STAGE3URL + bcolors.ENDC)
            log.write("Stage3 not found. Downloading from " + STAGE3URL + "\n")
            curllocation = ''.join(["sudo mkdir -p ", SCRIPTPATH, "/.stages/hardened"])
            print(curllocation)
            os.system(curllocation)
            curl = sp_run("sudo curl -s " + STAGE3URL + " -o " + ''.join([SCRIPTPATH, "/.stages/hardened/stage3-amd64-hardened-latest.tar.bz2"]), verbose)
        copy_stage3 = sp_run("sudo buildah add " + scratch + " " + ''.join([SCRIPTPATH, "/.stages/hardened/stage3-amd64-hardened-latest.tar.bz2"]), verbose)
        sp_run("sudo buildah run " + scratch + " -- sed -i -e 's/#rc_sys=\"\"/rc_sys=\"docker\"/g' /etc/rc.conf", verbose)
        timezonefile = open(''.join([scratch_mount, "/etc/timezone"]), "w+")
        timezonefile.write(TIMEZONE)
        timezonefile.flush()
        timezonefile.close()
        sp_run("sudo buildah run " + scratch + " mkdir -p /usr/portage", verbose)
        sp_run("sudo buildah config --cmd /bin/bash --label " + ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened"]) + " " + scratch, verbose)
        sp_run("sudo buildah umount " + scratch, verbose)
        commit = sp_run("sudo buildah commit --format oci --rm -q --squash " + scratch + " " + ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened:", DATE]), verbose)
        sp_run("sudo buildah tag " + ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened:", DATE]) + " " + latest_uri, verbose)
        if copy_stage3.call.returncode == 0 and commit.call.returncode == 0:
            BUILT.append(latest_uri)
            BUILT.append(dated_uri)
        else:
            FAILED.append(latest_uri)
        log.close()

def stage3_spawn(build_initial, verbose=False):
    """Spawn a stage3 container from image"""
    if build_initial is True:
        log = open(LOGFILE, 'a', 1)
        print(bcolors.YELLOW + bcolors.BOLD + "Spawning stage3" + bcolors.ENDC)
        log.write("Spawning stage3\n")
        stage3_run = sp_run("sudo buildah from " + ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened:latest"]), verbose)
        stage3 = stage3_run.output[-1].rstrip()
        log.close()
        return stage3
    return 0

def buildah_build(file, image_name, path, portagedir, verbose=False):
    """Build a buildah file"""
    log = open(LOGFILE, 'a', 1)
    tag_dated = ''.join([REGISTRY, NAMESPACE, image_name, ":", DATE])
    tag_latest = ''.join([REGISTRY, NAMESPACE, image_name, ":latest"])
    log.write("Python build script called with buildah for " + file + ", " + image_name + ", " + path + "\n")
    build = sp_run("sudo buildah bud --cap-add CAP_net_raw -v " + ''.join([portagedir, ":/usr/portage/"]) + " -f " + file + " -t " + tag_dated + " -t " + tag_latest + " --build-arg " + ''.join(["BDATE=", DATE]) + " --build-arg " + ''.join(["GHEAD=", GITVERSION.decode("ascii")]) + " " + path, verbose)
    if build.call.returncode == 0:
        BUILT.append(tag_dated)
        BUILT.append(tag_latest)
        print(bcolors.BLUE + bcolors.BOLD + "Build of " + image_name + " succeeded!\n" + bcolors.ENDC)
        log.write("Build of " + image_name + " succeeded!\n")
    else:
        FAILED.append(tag_dated)
        FAILED.append(tag_latest)
        print(bcolors.RED + bcolors.BOLD + "Build of " + image_name + " failed.\n" + bcolors.ENDC)
        log.write("Build failed.\n")
        log.close()
        return 1
    log.close()
    return 0

def initial_build(build_initial, portagedir, verbose=False):
    """Build all numbered images in the root directory of the repo"""
    if build_initial is True:
        log = open(LOGFILE, 'a', 1)
        print(bcolors.YELLOW + bcolors.BOLD + "Initial images" + bcolors.ENDC)
        log.write("Initial images\n")
        for filename in INITIAL_FILES:
            buildfile = os.path.join(SCRIPTPATH, filename)
            buildpath = os.path.dirname(os.path.realpath(buildfile))
            buildname = buildfile.split('.')[1]
            buildah_build(buildfile, buildname, buildpath, portagedir, verbose)
        log.close()

def project_build(build_targets, portagedir, verbose=False):
    """Call buildah_build for all buildah files matching the regex passed after -b"""
    if build_targets:
        log = open(LOGFILE, 'a', 1)
        print(bcolors.YELLOW + bcolors.BOLD + "Project images" + bcolors.ENDC)
        log.write("Project images\n")
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
            buildah_build(buildfile, buildname, buildpath, portagedir, verbose)
        log.close()

def cleanup(verbose=False):
    """Remove any remaining containers"""
    log = open(LOGFILE, 'a', 1)
    remove = sp_run("sudo buildah rm -a", verbose)
    for success in SUCCEEDED:
        print(bcolors.GREEN + bcolors.BOLD + "Succeeded: " + success + bcolors.ENDC)
        log.write("Succeeded: " + success + "\n")
    for failure in FAILED:
        print(bcolors.RED + bcolors.BOLD + "Failed: " + failure + bcolors.ENDC)
        log.write("Failed: " + failure + "\n")
    log.close()

def registry_push(images, verbose=False):
    """Push successfully built images to registry"""
    success = []
    failure = []
    log = open(LOGFILE, 'a', 1)
    for image in images:
        push_run = sp_run("sudo buildah push -q " + image + " " + ''.join(["docker://", image]), verbose)
        if push_run.call.returncode == 0:
            print(bcolors.GREEN + bcolors.BOLD + "Successfully pushed " + image + " to registry." + bcolors.ENDC)
            log.write("Successfully pushed " + image + " to registry.\n")
            SUCCEEDED.append(image)
        else:
            print(bcolors.RED + bcolors.BOLD + "Pushing " + image + " to registry has failed." + bcolors.ENDC)
            log.write("Pushing " + image + " to registry has failed.\n")
            FAILED.append(image)

##Main
if __name__ == "__main__":
    args = parse_arguments(sys.argv[1:])
    portage_build = portage_build(args.build_portage, args.verbose)
    portagedir = portage_overlay(args, args.verbose)
    catalyst_build(portagedir, args.verbose)
    stage3_bootstrap(args.build_initial, args.verbose)
    stage3 = stage3_spawn(args.build_initial, args.verbose)
    initial_build(args.build_initial, portagedir, args.verbose)
    project_build(args.build_targets, portagedir, args.verbose)
    registry_push(BUILT, args.verbose)
    cleanup(args.verbose)
