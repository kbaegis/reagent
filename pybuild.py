#!/usr/bin/sudo /usr/bin/python3

"""
This python program can be leveraged to create a CI/CD pipeline for gentoo images.
"""

import argparse
import sys
import os
import io
import time
import subprocess
import re
import shlex
import signal

#Please adjust to fit your environment
SCRIPTPATH = os.path.dirname(os.path.realpath(__file__))
DATE = time.strftime("%Y-%m-%d") #used for image tag
TIMEZONE = "America/Denver" #adjust as needed
GITVERSION = subprocess.check_output(["git", "-C", SCRIPTPATH, "rev-parse", "HEAD"]) #appended to image metadata
REGISTRY = "crucible.lab:4000" #point to your registry
NAMESPACE = "/oci/" #adjust as needed
STAGE3URL = "https://crucible.lab/distfiles/stage3-amd64-hardened-latest.tar.bz2" #point to any valid stage3
INITIAL_FILES = [entry for entry in os.listdir(SCRIPTPATH) if re.match(r'[0-9]+.*\.buildah$', entry)] #matches any file with a numeric prefix and a .buildah suffix from the root directory of the script
INITIAL_FILES.sort()
EXCLUDE_FILES = set(INITIAL_FILES)
BUILDAH_FILES = []
for root, dirnames, filenames in os.walk(SCRIPTPATH):
    for filename in filenames:
        if re.match(r'.*buildah$', filename) and filename not in EXCLUDE_FILES:
            BUILDAH_FILES.append(os.path.splitext(os.path.relpath(os.path.join(root, filename), SCRIPTPATH))[0])
PROJECT_FILES = set(BUILDAH_FILES) #a set of *..buildah files located under the root directory and excludes INITIAL_FILES
LOGFILE = ''.join([SCRIPTPATH, '/build.log']) #logfile used throughout

class bcolors:
    ISUCCESS = '\033[94m' #intermediate success; blue
    SUCCESS = '\033[92m' #success; green
    VOUT = '\033[0;37m' #Verbose output; White/Grey
    PROGRESS = '\033[33m' #Function progress; Yellow
    FAILURE = '\033[31m' #Failure; Red
    ENDC = '\033[0m' #Color Reset
    BOLD = '\033[1m' #Bold
    UNDERLINE = '\033[4m' #Underline

class subprocessReturn(object):
    def __init__(self, call, output):
        self.call = call
        self.output = output

class imageList(object):
    """
    Class tracking images in various build states.
    """
    def __init__(self):
        self.images = {}
        self.base_uri = ''.join([REGISTRY, NAMESPACE])
        self.date = DATE

    def addBuilt(self, name, build_status):
        lname = name + ":latest"
        dname = name + ":" + self.date
        uri = self.base_uri + name
        self.images[lname] = {'uri': uri, 'tag': 'latest', 'build_status': build_status, 'push_status': -1}
        self.images[dname] = {'uri': uri, 'tag': self.date, 'build_status': build_status, 'push_status': -1}
    
    def updatePushed(self, name, push_status):
        self.images[''.join([name, ':latest'])].update({'push_status': push_status})
        self.images[''.join([name, ':', self.date])].update({'push_status': push_status})

    def statusList(self):
        failure = bcolors.FAILURE + bcolors.BOLD
        success = bcolors.SUCCESS + bcolors.BOLD
        built = bcolors.VOUT + bcolors.BOLD
        end = bcolors.ENDC
        returnlist = []
        for name, value in self.images.items():
            uri = ''.join([self.images[name]['uri'], ':',self.images[name]['tag']])
            build_status = self.images[name]['build_status']
            push_status = self.images[name]['push_status']
            if build_status == 0 and push_status == 0:
                string = ''.join([success, "Image: ", uri, " - pushed", end])
                returnlist.append(string)
            if build_status == 0 and push_status == -1:
                string = ''.join([built, "Image: ", uri, " - built, unpushed", end])
                returnlist.append(string)
            if build_status > 0:
                string = ''.join([failure, "Image: ", uri, " - failed build", end])
                returnlist.append(string)
            if build_status == 0 and push_status > 0:
                string = ''.join([failure, "Image: ", uri, " - failed push", end])
                returnlist.append(string)
        if not returnlist:
            string = built + "No images built." + end
            returnlist.append(string)
        return returnlist

    def listBuilt(self):
        returnlist = []
        for name, value in self.images.items():
            uri = ''.join([self.images[name]['uri'], ':', self.images[name]['tag']])
            build_status = self.images[name]['build_status']
            if build_status == 0:
                returnlist.append(uri)
        return returnlist

    def listFailed(self):
        returnlist = []
        for name, value in self.images.items():
            uri = ''.join([self.images[name]['uri'], ':', self.images[name]['tag']])
            build_status = self.images[name]['build_status']
            push_status = self.images[name]['push_status']
            if build_status > 0 or push_status > 0:
                returnlist.append(uri)
        return returnlist

    def listPushed(self):
        returnlist = []
        for name, value in self.images.items():
            uri = ''.join([self.images[name]['uri'], ':', self.images[name]['tag']])
            build_status = self.images[name]['build_status']
            push_status = self.images[name]['push_status']
            if build_status == 0 and push_status == 0:
                returnlist.append(uri)
        return returnlist

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

def sp_run(command, verbose = False):
    output_list = []
    with open(LOGFILE, 'a', 1) as log:
        subprocess_call = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #with io.TextIOWrapper(subprocess_call.stdout, write_through = True, encoding = "ascii", errors = 'ignore') as wrapper:  
        with io.TextIOWrapper(subprocess_call.stdout, line_buffering = True, encoding = "ascii", errors = 'ignore') as wrapper:  
            for line in wrapper:
                try:
                    if verbose == True:
                        colorizedline = (bcolors.VOUT + line + bcolors.ENDC)
                        print(colorizedline, end="")
                    log.write(line)
                    log.flush()
                    output_list.append(line)
                except BlockingIOError:
                    tb = sys.exc_info()[2]
                    pass
            subprocess_call.wait()
    return subprocessReturn(subprocess_call, output_list)

def portage_build(build_portage, images, verbose = False):
    """Build portage container from host snapshot"""
    if build_portage is True:
        log = open(LOGFILE, 'a', 1)
        print(bcolors.PROGRESS + bcolors.BOLD + "Building portage" + bcolors.ENDC)
        log.write("Building portage\n")
        name = "portagedir"
        latest_nametag = name + ":latest"
        dated_nametag = name + ":" + DATE
        uri_base = ''.join([REGISTRY, NAMESPACE])
        uri = ''.join([REGISTRY, NAMESPACE, name])
        latest_uri = ''.join([uri_base, latest_nametag])
        dated_uri = ''.join([uri_base, dated_nametag])
        sync_target_run = sp_run("sudo buildah from " + latest_uri, verbose)
        sync_target = sync_target_run.output[-1].rstrip()
        sync_target_mount_run = sp_run("sudo buildah mount " + sync_target, verbose)
        sync_target_mount = sync_target_mount_run.output[-1].rstrip()
        emaint = sp_run("env " + ''.join(["PORTDIR=", sync_target_mount]) + " emaint -a sync", verbose)
        commit = sp_run("sudo buildah commit --format oci --rm -q --squash " + sync_target + " " + dated_uri, verbose)
        add_latest = sp_run(" sudo buildah tag " + dated_uri + " " + latest_uri, verbose)
        if sync_target_run.call.returncode == 0 and commit.call.returncode == 0:
            images.addBuilt(name, 0)
            log.close()
            return 0
        else:
            images.addBuilt(name, 1)
            log.close()
            return 1

def portage_overlay(args, verbose = False):
    """Create portage overlay container to be mounted on gentoo containers"""
    if args.build_catalyst is True or args.build_initial is True or args.build_targets:
        log = open(LOGFILE, 'a', 1)
        print(bcolors.PROGRESS + bcolors.BOLD + "Spawning portage" + bcolors.ENDC)
        log.write("Spawning portage\n")
        portagedir_container_run = sp_run("sudo buildah from " + ''.join([REGISTRY, NAMESPACE, "portagedir:latest"]), verbose)
        portagedir_container = portagedir_container_run.output[-1].rstrip()
        portagedir_container_mount_run = sp_run("sudo buildah mount " + portagedir_container, verbose)
        portagedir_container_mount = portagedir_container_mount_run.output[-1].rstrip()
        log.close()
        return portagedir_container_mount

def catalyst_build(build_catalyst, images, portagedir, bindpath = None, verbose = False):
    """Build all stages from specfiles located in .stages/default/"""
    if build_catalyst is True:
        if bindpath == None:
            bindpath = ''.join([SCRIPTPATH, '/.stages/'])
        log = open(LOGFILE, 'a', 1)
        print(bcolors.PROGRESS + bcolors.BOLD + "Building Catalyst" + bcolors.ENDC)
        log.write("Building Catalyst\n")
        name = "catalyst-cache"
        latest_nametag = name + ":latest"
        dated_nametag = name + ":" + DATE
        uri_base = ''.join([REGISTRY, NAMESPACE])
        latest_uri = ''.join([uri_base, latest_nametag])
        dated_uri = ''.join([uri_base, dated_nametag])
        emaint = sp_run("emaint -a sync", verbose)
        catalyst_cache_run = sp_run("sudo buildah from " + latest_uri, verbose)
        catalyst_cache = catalyst_cache_run.output[-1].rstrip()
        catalyst_cache_mount_run = sp_run("sudo buildah mount " + catalyst_cache, verbose)
        catalyst_cache_mount = catalyst_cache_mount_run.output[-1].rstrip()
        os.system("sudo mkdir -p /var/tmp/catalyst/packages/")
        os.system("sudo mkdir -p /usr/portage/distfiles")
        catalyst_bind_mount = sp_run("sudo mount --bind " + catalyst_cache_mount + " /var/tmp/catalyst/packages/", verbose)
        build_bind_mount = sp_run("sudo mount --bind " + bindpath + " /var/tmp/catalyst/builds/", verbose)
        if not os.path.isfile("/var/tmp/catalyst/builds/hardened/stage3-amd64-hardened-latest.tar.bz2"):
            print(bcolors.PROGRESS + bcolors.BOLD + "Stage3 not found. Downloading from " + STAGE3URL + bcolors.ENDC)
            log.write("Stage3 not found. Downloading from " + STAGE3URL + "\n")
            os.system("sudo mkdir -p /var/tmp/catalyst/builds/hardened/")
            curl = sp_run("sudo curl -s " + STAGE3URL + " -o /var/tmp/catalyst/builds/hardened/stage3-amd64-hardened-latest.tar.bz2", verbose)
        specfile_list = [entry for entry in os.listdir("/var/tmp/catalyst/builds/default/") if re.match(r'.*\.spec$', entry)]
        snapshot = sp_run("sudo catalyst -s latest", verbose)
        for specfile in specfile_list:
            print(bcolors.PROGRESS + bcolors.BOLD + "Catalyst build using specfile: " + specfile + bcolors.ENDC)
            log.write("Catalyst build using specfile: " + specfile + "\n")
            build = sp_run("sudo catalyst -f " + ''.join(["/var/tmp/catalyst/builds/default/", specfile]), verbose)
        catalyst_bind_umount = sp_run("sudo umount /var/tmp/catalyst/packages/", verbose)
        build_bind_umount = sp_run("sudo umount /var/tmp/catalyst/builds/", verbose)
        commit = sp_run("sudo buildah commit --format oci --rm -q --squash " + catalyst_cache + " " + dated_uri, verbose)
        sp_run("sudo buildah tag " + dated_uri + " " + latest_uri, verbose)
        if catalyst_cache_run.call.returncode == 0 and commit.call.returncode == 0:
            print(bcolors.ISUCCESS + bcolors.BOLD + "Build of " + latest_uri + " succeeded." + bcolors.ENDC)
            log.write("Build of " + latest_uri + " succeeded.\n")
            log.close()
            images.addBuilt(name, 0)
            return 0
        else:
            print(bcolors.FAILURE + bcolors.BOLD + "Build of " + latest_uri + " failed." + bcolors.ENDC)
            log.write("Build of " + latest_uri + " failed\n")
            log.close()
            images.addBuilt(name, 1)
            return 1

def stage3_bootstrap(build_initial, images, verbose = False):
    """Unpack stage3 bootstrap image inside a blank container"""
    if build_initial is True:
        log = open(LOGFILE, 'a', 1)
        name = "gentoo-stage3-amd64-hardened"
        print(bcolors.PROGRESS + bcolors.BOLD + "Bootstrapping stage3" + bcolors.ENDC)
        log.write("Bootstrapping stage3\n")
        uri = ''.join([REGISTRY, NAMESPACE, name])
        dated_uri = ''.join([uri, ":", DATE])
        latest_uri = ''.join([uri, ":latest"])
        scratch_run = sp_run("sudo buildah from scratch", verbose)
        scratch = scratch_run.output[-1].rstrip()
        scratch_mount_run = sp_run("sudo buildah mount " + scratch, verbose)
        scratch_mount = scratch_mount_run.output[-1].rstrip()
        if not os.path.isfile(''.join([SCRIPTPATH, "/.stages/hardened/stage3-amd64-hardened-latest.tar.bz2"])):
            print(bcolors.PROGRESS + bcolors.BOLD + "Stage3 not found. Downloading from " + STAGE3URL + bcolors.ENDC)
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
        sp_run("sudo buildah config --cmd /bin/bash --label " + ''.join([REGISTRY, NAMESPACE, name]) + " " + scratch, verbose)
        sp_run("sudo buildah umount " + scratch, verbose)
        commit = sp_run("sudo buildah commit --format oci --rm -q --squash " + scratch + " " + ''.join([REGISTRY, NAMESPACE, name, ":", DATE]), verbose)
        sp_run("sudo buildah tag " + ''.join([REGISTRY, NAMESPACE, name, ":", DATE]) + " " + latest_uri, verbose)
        if copy_stage3.call.returncode == 0 and commit.call.returncode == 0:
            log.close()
            images.addBuilt(name, 0)
            return 0
        else:
            log.close()
            images.addBuilt(name, 1)
            return 1

def stage3_spawn(build_initial, verbose = False):
    """Spawn a stage3 container from image"""
    if build_initial is True:
        log = open(LOGFILE, 'a', 1)
        print(bcolors.PROGRESS + bcolors.BOLD + "Spawning stage3" + bcolors.ENDC)
        log.write("Spawning stage3\n")
        stage3_run = sp_run("sudo buildah from " + ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened:latest"]), verbose)
        stage3 = stage3_run.output[-1].rstrip()
        log.close()
        return stage3

def buildah_build(file, image_name, path, images, portagedir, verbose = False):
    """Build a buildah file"""
    log = open(LOGFILE, 'a', 1)
    uri = ''.join([REGISTRY, NAMESPACE, image_name])
    uri_latest = ''.join([uri, ":latest"])
    uri_dated = ''.join([uri, ":", DATE])
    log.write("Python build script called with buildah for " + file + ", " + image_name + ", " + path + "\n")
    log.flush()
    log.close()
    build = sp_run("sudo buildah bud --cap-add CAP_net_raw -v " + ''.join([portagedir, ":/usr/portage/"]) + " -f " + file + " -t " + uri_dated + " -t " + uri_latest + " --build-arg " + ''.join(["BDATE=", DATE]) + " --build-arg " + ''.join(["GHEAD=", GITVERSION.decode("ascii")]) + " " + path, verbose)
    if build.call.returncode == 0:
        print(bcolors.ISUCCESS + bcolors.BOLD + "Build of " + image_name + " succeeded!" + bcolors.ENDC)
        log = open(LOGFILE, 'a', 1)
        log.write("Build of " + image_name + " succeeded!\n")
        log.close()
        images.addBuilt(image_name, 0)
        return 0
    else:
        print(bcolors.FAILURE + bcolors.BOLD + "Build of " + image_name + " failed." + bcolors.ENDC)
        log = open(LOGFILE, 'a', 1)
        log.write("Build of " + image_name + " failed.\n")
        log.close()
        images.addBuilt(image_name, 1)
        return 1

def initial_build(build_initial, images, portagedir, verbose = False):
    """Build all numbered images in the root directory of the repo"""
    if build_initial is True:
        log = open(LOGFILE, 'a', 1)
        print(bcolors.PROGRESS + bcolors.BOLD + "Initial images" + bcolors.ENDC)
        log.write("Initial images\n")
        for filename in INITIAL_FILES:
            buildfile = os.path.join(SCRIPTPATH, filename)
            buildpath = os.path.dirname(os.path.realpath(buildfile))
            buildname = buildfile.split('.')[1]
            buildah_build(buildfile, buildname, buildpath, images, portagedir, verbose)
        log.close()
        return 0

def project_build(build_targets, images, portagedir, verbose = False):
    """Call buildah_build for all buildah files matching the regex passed after -b"""
    if build_targets:
        log = open(LOGFILE, 'a', 1)
        print(bcolors.PROGRESS + bcolors.BOLD + "Project images" + bcolors.ENDC)
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
            buildah_build(buildfile, buildname, buildpath, images, portagedir, verbose)
        log.close()
        return 0
    return 0

def cleanup(verbose = False):
    """Remove any remaining containers"""
    log = open(LOGFILE, 'a', 1)
    remove = sp_run("sudo buildah rm -a", verbose)
    if remove.call.returncode == 0:
        log.close()
        return 0
    else:
        log.close()
        return 1

def registry_push(images, verbose = False):
    """Push successfully built images to registry"""
    log = open(LOGFILE, 'a', 1)
    for image in images.listBuilt():
        push_run = sp_run("sudo buildah push -q " + image + " " + ''.join(["docker://", image]), verbose)
        nametag = image.rsplit(sep='/')[-1]
        name = ''.join(nametag.rsplit(sep=':')[:-1])
        images.updatePushed(name, push_run.call.returncode)
        if push_run.call.returncode == 0:
            print(bcolors.SUCCESS + bcolors.BOLD + "Successfully pushed " + image + bcolors.ENDC)
        if push_run.call.returncode == 1:
            print(bcolors.FAILURE + bcolors.BOLD + "Failed to push " + image + bcolors.ENDC)
    log.close()
    return 0

##Main
if __name__ == "__main__":
    args = parse_arguments(sys.argv[1:])
    images = imageList()
    portage_build = portage_build(args.build_portage, images, verbose = args.verbose)
    portagedir = portage_overlay(args, verbose = args.verbose)
    catalyst_build(args.build_catalyst, images, portagedir, verbose = args.verbose)
    stage3_bootstrap(args.build_initial, images, verbose = args.verbose)
    stage3 = stage3_spawn(args.build_initial, verbose = args.verbose)
    initial_build(args.build_initial, images, portagedir, verbose = args.verbose)
    project_build(args.build_targets, images, portagedir, verbose = args.verbose)
    registry_push(images, verbose = args.verbose)
    status = images.statusList()
    if args.verbose == True:
        for line in status:
            print(line)
    with open(LOGFILE, 'a', 1) as log:
        for line in status:
           log.write(line + "\n")
    cleanup(args.verbose)
