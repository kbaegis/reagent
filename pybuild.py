#!/usr/bin/sudo /usr/bin/python3

"""This python program can be leveraged to create a CI/CD pipeline for gentoo images."""

import argparse
import sys
import os
import io
import time
import subprocess
import re
import shlex
import json
import signal
import readline
import cProfile

#Please adjust to fit your environment
SCRIPTPATH = os.path.dirname(os.path.realpath(__file__))
DATE = time.strftime("%Y-%m-%d") #used for image tag
TIMEZONE = "America/Denver" #adjust as needed
GITVERSION = subprocess.check_output(["git", "-C", SCRIPTPATH, "rev-parse", "--short", "HEAD"]) #appended to image metadata
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
TESTLABEL = 'nulllabs.cri.cmd.test' #What label your dockerfiles use to store the test commands
GENESISLABEL = 'nulllabs.genesis' #Where reagent looks for the layer chain
SELFLABEL = 'nulllabs.self' #Where reagent documents the image built

##Return Convention:
# 0: success
# 1+: failure
# -1: pending/intermediate
# -2: disabled

class tcolors(object):
    """Class containing terminal codes for colorized output."""
    def __init__(self):
        self.ISUCCESS = '\033[94m' #intermediate success; blue
        self.SUCCESS = '\033[92m' #success; green
        self.VOUT = '\033[0;37m' #Verbose output; White/Grey
        self.NOTIFY = '\033[33m' #Function progress; Yellow
        self.FAILURE = '\033[31m' #Failure; Red
        self.ENDC = '\033[0m' #Color Reset
        self.BOLD = '\033[1m' #Bold
        self.UNDERLINE = '\033[4m' #Underline
        self.codeMapping = {0: self.SUCCESS, 1: self.FAILURE, -1: self.ISUCCESS, -2: self.VOUT, 2: self.NOTIFY}

class subprocessReturn(object):
    """Class containing both the Popen state tracking (call) and a list of output lines (output) from a subprocess run."""
    def __init__(self, call, output):
        self.call = call
        self.output = output

class pendingOperation(object):
    """Class storing a procedure to be run inside signal_handler if invoked."""
    def enableOperation(self, name, methodname):
        self.name = name
        self.method = getattr(containerGroup, methodname)
        self.profile = cProfile.Profile()
        self.profile.enable(subcalls=False,builtins=False)
        return self.profile
    
    def completeOperation(self):
        #progressNotify("Calculating runtime", -2)
        #run_time = profileTiming("^\('" + __file__ + "', [0-9]*, '(?!signal_handler).*$", self.profile)
        run_time = profileTiming("^\('" + __file__ + ".*$", self.profile)
        #run_time = profileTiming(".*", self.profile)
        #progressNotify("Calculating pausetime", -2)
        pause_time = profileTiming("^\('" + __file__ + "', [0-9]*, 'signal_handler.*$", self.profile)
        elapsed = run_time - pause_time
        self.profile.disable()
        del self.name
        del self.profile
        del self.method
        return elapsed

    def run_method(self):
        #progressNotify("Calculating runtime", -2)
        #run_time = profileTiming("^\('" + __file__ + "', [0-9]*, '(?!signal_handler).*$", self.profile)
        run_time = profileTiming("^\('" + __file__ + ".*$", self.profile)
        #run_time = profileTiming(".*", self.profile)
        #progressNotify("Calculating pausetime", -2)
        pause_time = profileTiming("^\('" + __file__ + "', [0-9]*, 'signal_handler.*$", self.profile)
        elapsed = run_time - pause_time
        self.method(images, self.name, -1, time = elapsed)

class containerGroup(object):
    """Class tracking images in various container image states."""
    def __init__(self, args):
        self.images = {} #used for state tracking
        self.time = {} #used for profiled time consumed
        self.base_uri = ''.join([REGISTRY, NAMESPACE])
        self.date = DATE
        self.tags = [self.date, 'latest']
        self.image_types = ['bootstrapping', 'base', 'leaf', 'default'] #unused, classifies image for initial states and pending operations
        self.base_properties = ['uri', 'tag', 'type'] #unused
        self.add_properties = {'build': 'core', 'test': 'test', 'vuln test': 'vuln_test', 'push': 'core'} #Operations and the category they fall under, translated to an initial state via enablement.
        self.enablement = {'default': {'core': -1, 'test': -2, 'vuln_test': -2}, 'bootstrapping': {'core': -1, 'test': -2, 'vuln_test': -2}} #Used in addImage to set the initial state of various operations (pulled in from add_properties). Updated via methods below.
        self.features = args
        if self.features.test_images == True:
            self.enablement['default']['test'] = -1
        if self.features.test_images == False:
            self.enablement['default']['test'] = -2
        if self.features.vuln_test_images == True:
            self.enablement['default']['vuln_test'] = -1
        if self.features.vuln_test_images == False:
            self.enablement['default']['vuln_test'] = -2

    def addImage(self, name, image_type = 'default'):
        """Method to track a new image. Initial states are assigned by image_type -> enablement -> add_properties."""
        uri = self.base_uri + name
        enablement = self.enablement
        self.images[name] = {'uri': uri, 'tags': self.tags, 'type': image_type} #Basic properties
        self.time[name] = {}
        for key, value in self.add_properties.items():
            self.images[name][key + ' state'] = enablement[image_type][value]
            self.time[name][key + ' time'] = 0
        if self.features.disable_registry == True:
            self.images[name].update({'push state': -2})

    def updateBuilt(self, name, build_state, time = 0):
        """Simple method to update the state of the build."""
        self.images[name].update({'build state': build_state})
        self.time[name].update({'build time': time})
    
    def updatePushed(self, name, push_state, time = 0):
        """Simple method to update the push state of the build."""
        self.images[name].update({'push state': push_state})
        self.time[name].update({'push time': time})
    
    def updateTested(self, name, test_state, time = 0):
        """Simple method to update the test state of the build."""
        #
        self.images[name].update({'test state': test_state})
        self.time[name].update({'test time': time})
    
    def updateVulnTested(self, name, vuln_test_state, time = 0):
        """Simple method to update the vulnerability test state of the build."""
        self.images[name].update({'vuln test state': vuln_test_state})
        self.time[name].update({'vuln test time': time})

    def statusList(self):
        """Method to return a list of image states."""
        colors = tcolors()
        failure = colors.FAILURE + colors.BOLD
        success = colors.SUCCESS + colors.BOLD
        isuccess = colors.ISUCCESS
        none = colors.VOUT
        end = colors.ENDC
        returnlist = []
        for name, unused in self.images.items():
            uri = self.images[name]['uri']
            string = "Image: " + uri + end
            fails = 0
            unfinished = 0
            return_keys = []
            for key, state in self.images[name].items():
                return_keys.append(key)
            for item in return_keys[3:]:
                state = self.images[name][item]
                time = self.time[name][item.replace('state', 'time')]
                if state >= 1:
                    fails = fails + 1
                    string = string + "; " + item + ":" + failure + "Failed (" + str(time) + " seconds)" + end
                elif state == -1:
                    unfinished = unfinished + 1
                    string = string + "; " + item + ":" + isuccess + "Pending (" + str(time) + " seconds)" + end
                elif state == -2:
                    string = string + "; " + item + ":" + success + "Disabled (" + str(time) + " seconds)" + end
                else:
                    string = string + "; " + item + ":" + success + "Complete (" + str(time) + " seconds)" + end
            if fails > 0:
                string = failure + string
            if unfinished > 0:
                string = isuccess + string
            else:
                string = success + string
            tags = self.images[name]['tags'][0]
            for tag in self.images[name]['tags'][1:]:
                tags = tags + "," + tag
            string = string + "; Tags: " + tags
            returnlist.append(string)
        if not returnlist:
            string = none + "No images built." + end
            returnlist.append(string)
        return returnlist

    def listBuilt(self):
        """Method to return a list of successfully built images."""
        returnlist = []
        for name, value in self.images.items():
            build_status = self.images[name]['build state']
            if build_status == 0:
                returnlist.append(name)
        return returnlist

    def listUntested(self):
        """Method to return a list of images with a pending image test state."""
        testlist = []
        returnlist = []
        unique_uri = set()
        for key, value in self.images.items():
            uri = self.images[key]['uri']
            tag = self.images[key]['tags'][0]
            if not uri in unique_uri:
                name = uri.rsplit(sep='/')[-1]
                testlist.append(name + ':' + tag)
                unique_uri.add(uri)
        for uri in testlist:
            build_status = self.images[uri]['build state']
            test_status = self.images[uri]['test status']
            if build_status == 0 and test_status == -1:
                returnlist.append(uri)
        return returnlist

    def listFailed(self):
        """Method to return a list of images with any failed states."""
        returnlist = []
        for name, value in self.images.items():
            uri = self.images[name]['uri']
            failures = 0
            failable = []
            for key, value in self.images[name].items():
                failable.append(key)
            for item in failable[3:]:
                value = self.images[name][item]
                if value > 0:
                    failures = failures + 1
            if failures > 0:
                returnlist.append(uri)
        return returnlist

    def listUnpushed(self):
        """Method to return a list of images with a successful push state."""
        returnlist = []
        for name, value in self.images.items():
            uri = self.images[name]['uri']
            failures = 0
            failable = []
            push_status = self.images[name]['push status']
            for key, value in self.images[name].items():
                failable.append(key)
            for item in failable[3:]:
                value = self.images[name][item]
                if value > 0:
                    failures = failures + 1
            if push_status == 0 and falures == 0:
                returnlist.append(uri)
        return returnlist

class handler:
    """Class to track forked and child processes run by sp_run."""
    def __init__(self):
        self.processList = []
    
    def handle_child(self, child):
        self.processList.append(child)

    def abandon_child(self, child):
        self.processList.remove(child)

def signal_handler(signum, frame):
    """Handles SIG*"""
    signal.signal(2, signal.SIG_IGN)
    try:
        pending.run_method()
    except AttributeError:
        print("No pending operation stored.")
    status = images.statusList()
    for line in status:
        print(line)
    while True:
        confirm = input('Would you like to terminate now? [(y)es/(n)o]')
        if confirm == 'y' or confirm == 'yes':
            try:
                cleanup(verbose = images.features)
            except:
                pass
            for child in children.processList:
                child.terminate()
            progressNotify("Reagent killed by signal.", 1)
            sys.exit(0)
        elif confirm == 'n' or confirm == 'no':
            signal.signal(2, signal_handler)
            return 0

def parse_arguments(arguments):
    """Parse arguments from cli-invocation"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help="Show verbose output from subprocess commands.")
    parser.add_argument('-p', '--portage', dest='build_portage', action='store_true', help="Regenerate a container with synced portage contents.")
    parser.add_argument('-c', '--catalyst', dest='build_catalyst', action='store_true', help="Build contents of .stages/default/ with catalyst using specfiles.")
    parser.add_argument('-i', '--initial', dest='build_initial', action='store_true', help="Build all numbered buildah files in the root directory in order with buildah.")
    parser.add_argument('-b', '--build', dest='build_targets', nargs="+", help="Build selected contents matched by regex. Use 'all' to build all leaf containers.")
    parser.add_argument('-t', '--test', dest='test_images', action='store_true', help="Test images using OCIv1.config.Labels instruction before pushing them to registry.")
    parser.add_argument('-T', '--vulnerability', dest='vuln_test_images', action='store_true', help="Run vulnerability tests against images.")
    parser.add_argument('-R', '--disable-registry', dest='disable_registry', action='store_true', help="Disable push to registry.")
    args = parser.parse_args(arguments)
    return args

def sp_run(command, verbose = False, nonscrolling = True):
    """Command wraps and executes commands passed to it."""
    colors = tcolors()
    output_list = []
    with open(LOGFILE, 'a', 1) as log:
        subprocess_call = subprocess.Popen(shlex.split(command), start_new_session=True, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            children.handle_child(subprocess_call) #Tracks "start_new_session instances, divorces SIG* from running subprocesses
        except NameError:
            children = handler()
            children.handle_child(subprocess_call)
        else:
            print("Untracked rugrat at pid: " + subprocess_call.pid)
        if nonscrolling == False:
            lb = True
            wt = False
            nl = None
        elif nonscrolling == True:
            lb = True
            wt = False
            nl = ''
        with io.TextIOWrapper(subprocess_call.stdout, encoding = "ascii", errors = 'ignore', newline = nl, line_buffering = lb, write_through = wt) as wrapper:  
            for line in wrapper:
                try:
                    if verbose == True:
                        colorizedline = (colors.VOUT + line + colors.ENDC)
                        if nonscrolling == False:
                            print(colorizedline, end="")
                        elif nonscrolling == True:
                            print(colorizedline, end="", flush=True)
                    log.write(line)
                    log.flush()
                    output_list.append(line)
                except BlockingIOError:
                    tb = sys.exc_info()[2]
                    pass
            subprocess_call.wait()
            children.abandon_child(subprocess_call)
    return subprocessReturn(subprocess_call, output_list)

def portage_build(build_portage, images, verbose = False):
    """Build portage container from host snapshot"""
    if build_portage is True:
        name = "portagedir"
        pbprofile = pending.enableOperation(name, 'updateBuilt')
        progressNotify("Building portage.", 2)
        images.addImage(name, image_type = 'bootstrapping')
        prime_tag = images.images[name]['tags'][0]
        prime_uri = images.base_uri + name + ':' + prime_tag
        latest_uri = images.base_uri + name + ':latest'
        sync_target_run = sp_run("sudo buildah from " + latest_uri, verbose)
        sync_target = sync_target_run.output[-1].rstrip()
        sync_target_mount_run = sp_run("sudo buildah mount " + sync_target, verbose)
        sync_target_mount = sync_target_mount_run.output[-1].rstrip()
        emaint = sp_run("env " + ''.join(["PORTDIR=", sync_target_mount]) + " emaint -a sync", verbose)
        commit = sp_run("sudo buildah commit --format oci --rm -q --squash " + sync_target + " " + prime_uri, verbose)
        for tag in images.images[name]['tags'][1:]:
            sp_run("sudo buildah tag " + prime_uri + " " + prime_uri.replace(prime_tag,tag), verbose)
        elapsed = pending.completeOperation()
        if sync_target_run.call.returncode == 0 and commit.call.returncode == 0:
            images.updateBuilt(name, 0, time = elapsed)
            progressNotify("Portage build succeeded.", 0)
            return 0
        else:
            images.updateBuilt(name, 1, time = elapsed)
            progressNotify("Portage build failed.", 1)
            return 1

def portage_overlay(args, verbose = False):
    """Create portage overlay container to be mounted on gentoo containers"""
    if args.build_catalyst is True or args.build_initial is True or args.build_targets:
        progressNotify("Spawning portage", 2)
        portagedir_container_run = sp_run("sudo buildah from " + ''.join([REGISTRY, NAMESPACE, "portagedir:latest"]), verbose)
        portagedir_container = portagedir_container_run.output[-1].rstrip()
        portagedir_container_mount_run = sp_run("sudo buildah mount " + portagedir_container, verbose)
        portagedir_container_mount = portagedir_container_mount_run.output[-1].rstrip()
        progressNotify("Portage container creation complete", 2)
        return portagedir_container_mount

def catalyst_build(build_catalyst, images, portagedir, bindpath = None, verbose = False):
    """Build all stages from specfiles located in .stages/default/"""
    if build_catalyst is True:
        name = "catalyst-cache"
        if bindpath == None:
            bindpath = ''.join([SCRIPTPATH, '/.stages/'])
        progressNotify("Building Catalyst.", 2)
        images.addImage(name, image_type = 'bootstrapping')
        #prime_tag =  images.images[name]['tags'][0]
        prime_tag =  "latest"
        prime_uri = images.base_uri + name + ':' + prime_tag
        emaint = sp_run("emaint -a sync", verbose)
        catalyst_cache_run = sp_run("sudo buildah from " + prime_uri, verbose)
        catalyst_cache = catalyst_cache_run.output[-1].rstrip()
        catalyst_cache_mount_run = sp_run("sudo buildah mount " + catalyst_cache, verbose)
        catalyst_cache_mount = catalyst_cache_mount_run.output[-1].rstrip()
        os.system("sudo mkdir -p /var/tmp/catalyst/packages/")
        os.system("sudo mkdir -p /usr/portage/distfiles")
        catalyst_bind_mount = sp_run("sudo mount --bind " + catalyst_cache_mount + " /var/tmp/catalyst/packages/", verbose)
        build_bind_mount = sp_run("sudo mount --bind " + bindpath + " /var/tmp/catalyst/builds/", verbose)
        if not os.path.isfile("/var/tmp/catalyst/builds/hardened/stage3-amd64-hardened-latest.tar.bz2"):
            progressNotify("Stage3 not found. Downloading from " + STAGE3URL, 2)
            os.system("sudo mkdir -p /var/tmp/catalyst/builds/hardened/")
            curl = sp_run("sudo curl " + STAGE3URL + " -o /var/tmp/catalyst/builds/hardened/stage3-amd64-hardened-latest.tar.bz2", verbose)
        specfile_list = [entry for entry in os.listdir("/var/tmp/catalyst/builds/default/") if re.match(r'.*\.spec$', entry)]
        snapshot = sp_run("sudo catalyst -s latest", verbose)
        for specfile in specfile_list:
            csprofile = cProfile.Profile()
            csprofile.enable()
            progressNotify("Catalyst build using specfile: " + specfile + ".", 2)
            build = sp_run("sudo catalyst -f " + ''.join(["/var/tmp/catalyst/builds/default/", specfile]), verbose)
            elapsed = profileTiming(".*", csprofile, persist = False)
            progressNotify("Specfile " + specfile + " ended after " + str(elapsed) + " seconds.", build.call.returncode)
        catalyst_bind_umount = sp_run("sudo umount /var/tmp/catalyst/packages/", verbose)
        build_bind_umount = sp_run("sudo umount /var/tmp/catalyst/builds/", verbose)
        commit = sp_run("sudo buildah commit --format oci --rm -q --squash " + catalyst_cache + " " + prime_uri, verbose)
        for tag in images.images[name]['tags'][1:]:
            sp_run("sudo buildah tag " + prime_uri + " " + prime_uri.replace(prime_tag, tag), verbose)
        if catalyst_cache_run.call.returncode == 0 and commit.call.returncode == 0:
            progressNotify("Build of " + prime_uri + " succeeded.", 0)
            images.updateBuilt(name, 0)
            return 0
        else:
            progressNotify("Build of " + prime_uri + " failed.", 1)
            images.updateBuilt(name, 1)
            return 1

def stage3_bootstrap(build_initial, images, verbose = False):
    """Unpack stage3 bootstrap image inside a blank container"""
    if build_initial is True:
        name = "gentoo-stage3-amd64-hardened"
        s3profile = pending.enableOperation(name, 'updateBuilt')
        images.addImage(name, image_type = 'bootstrapping')
        progressNotify("Building base container from scratch + stage3.", 2)
        prime_tag =  images.images[name]['tags'][0]
        prime_uri = images.base_uri + name + ':' + prime_tag
        scratch_run = sp_run("sudo buildah from scratch", verbose)
        scratch = scratch_run.output[-1].rstrip()
        scratch_mount_run = sp_run("sudo buildah mount " + scratch, verbose)
        scratch_mount = scratch_mount_run.output[-1].rstrip()
        if not os.path.isfile(''.join([SCRIPTPATH, "/.stages/hardened/stage3-amd64-hardened-latest.tar.bz2"])):
            progressNotify("Stage3 not found. Downloading from " + STAGE3URL, 2)
            curllocation = ''.join(["sudo mkdir -p ", SCRIPTPATH, "/.stages/hardened"])
            os.system(curllocation)
            curl = sp_run("sudo curl -s " + STAGE3URL + " -o " + ''.join([SCRIPTPATH, "/.stages/hardened/stage3-amd64-hardened-latest.tar.bz2"]), verbose)
        copy_stage3 = sp_run("sudo buildah add " + scratch + " " + ''.join([SCRIPTPATH, "/.stages/hardened/stage3-amd64-hardened-latest.tar.bz2"]), verbose)
        sp_run("sudo buildah run " + scratch + " -- sed -i -e 's/#rc_sys=\"\"/rc_sys=\"docker\"/g' /etc/rc.conf", verbose)
        timezonefile = open(''.join([scratch_mount, "/etc/timezone"]), "w+")
        timezonefile.write(TIMEZONE)
        timezonefile.flush()
        timezonefile.close()
        sp_run("sudo buildah run " + scratch + " mkdir -p /usr/portage", verbose)
        sp_run("sudo buildah config --cmd /bin/bash --label " + GENESISLABEL + '=scratch' + ' --label ' + SELFLABEL + '="' + prime_uri + ' (' + GITVERSION.decode("ascii").rstrip() + ')" ' + '--env GENESIS="scratch" ' + scratch, verbose)
        sp_run("sudo buildah umount " + scratch, verbose)
        commit = sp_run("sudo buildah commit --format oci --rm -q --squash " + scratch + " " + ''.join([REGISTRY, NAMESPACE, name, ":", DATE]), verbose)
        for tag in images.images[name]['tags'][1:]:
            sp_run("sudo buildah tag " + prime_uri + " " + prime_uri.replace(prime_tag, tag), verbose)
        elapsed = pending.completeOperation()
        if copy_stage3.call.returncode == 0 and commit.call.returncode == 0:
            images.updateBuilt(name, 0, time = elapsed)
            progressNotify("Base image complete.", 0)
            return 0
        else:
            images.updateBuilt(name, 1, time = elapsed)
            progressNotify("Base image complete (with errors).", 1)
            return 1

def stage3_spawn(build_initial, verbose = False):
    """Spawn a stage3 container from image"""
    if build_initial is True:
        progressNotify("Spawning stage3.", 2)
        stage3_run = sp_run("sudo buildah from " + ''.join([REGISTRY, NAMESPACE, "gentoo-stage3-amd64-hardened:latest"]), verbose)
        stage3 = stage3_run.output[-1].rstrip()
        progressNotify("Spawning stage3 complete.", 2)
        return stage3

def buildah_build(file, image_name, path, images, portagedir, verbose = False, profiler = None, capabilities = None):
    """Build a buildah file"""
    bprofile = pending.enableOperation(image_name, 'updateBuilt')
    images.addImage(image_name)
    uri = images.base_uri + image_name
    tags = images.images[image_name]['tags']
    tagstr = ""
    for tag in tags:
        tagstr = tagstr + '-t ' + uri + ':' + tag + ' '
    capargs = ''
    for cap in capabilities or []:
        capargs = "--cap-add " + cap + ' ' + capargs
    filegrep = sp_run("grep ^FROM " + file)
    fromout = filegrep.output[0].replace('FROM ', '')
    image_jlist = ""
    fromimage = sp_run("buildah inspect " + fromout, False)
    #fromimage = sp_run("buildah inspect " + fromout, verbose)
    for line in fromimage.output:
        image_jlist = image_jlist + line
    try:
        fromjson = json.loads(image_jlist)
        genesis = fromjson['OCIv1']['config']['Labels'][GENESISLABEL]
        priorSelfLabel = fromjson['OCIv1']['config']['Labels'][SELFLABEL]
    #except KeyError:
    except:
        genesis = "exception (unknown)"
        priorSelfLabel = fromout.rstrip()
    imageGenesis = priorSelfLabel + '; ' + genesis
    selfVersion = uri + ':' + tag + ' (' + GITVERSION.decode("ascii").rstrip() + ')'
    genesisArg = 'GENESISARG="' + imageGenesis + '"' #Presently unassignable in ENV, valid at build time.
    genesisLabel = GENESISLABEL + '="' + imageGenesis + '"'
    selfArg = 'SELFARG="' + selfVersion + '"' #Presently unassignable in ENV, valid at build time.
    selfLabel = SELFLABEL + '="' + selfVersion + '"'
    command = "sudo buildah bud " + capargs + "-v " + ''.join([portagedir, ":/usr/portage/"]) + " -f " + file + " " + tagstr + " --build-arg " + ''.join(["BDATE=", DATE]) + " --build-arg " + ''.join(["GHEAD=", GITVERSION.decode("ascii").rstrip()]) + " --build-arg " + selfArg + " --build-arg " + genesisArg+ " --label " + selfLabel + " --label " + genesisLabel + " " + path
    if verbose:
        progressNotify("Build initiated for " + image_name + " with " + command, 2)
    else:
        progressNotify("Build initiated for " + image_name, 2)
    build = sp_run(command, verbose)
    elapsed = pending.completeOperation()
    if build.call.returncode == 0:
        images.updateBuilt(image_name, 0, time = elapsed)
        progressNotify("Build of " + image_name + " succeeded.", 0)
        return 0
    else:
        images.updateBuilt(image_name, 1, time = elapsed)
        progressNotify("Build of " + image_name + " failed.", 1)
        return 1

def initial_build(build_initial, images, portagedir, verbose = False):
    """Build all numbered images in the root directory of the repo"""
    if build_initial is True:
        progressNotify("Initial images.", 2)
        for filename in INITIAL_FILES:
            buildfile = os.path.join(SCRIPTPATH, filename)
            buildpath = os.path.dirname(os.path.realpath(buildfile))
            buildname = buildfile.split('.')[1]
            buildah_build(buildfile, buildname, buildpath, images, portagedir, verbose)
        progressNotify("Initial images complete.", 2)
        return 0

def project_build(build_targets, images, portagedir, verbose = False):
    """Call buildah_build for all buildah files matching the regex passed after -b"""
    if build_targets:
        progressNotify("Project Images.", 2)
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
        return 0
    return 0

def cleanup(verbose = False):
    """Remove any remaining containers"""
    listing = sp_run("sudo buildah containers -q", verbose)
    if len(listing.output) > 0:
        progressNotify("Performing cleanup.", 2)
        remove = sp_run("sudo buildah rm -a", verbose)
        if remove.call.returncode == 0:
            progressNotify("Cleanup complete.", 0)
            return 0
        else:
            progressNotify("Cleanup complete (with errors).", 1)
            return 1
    return 0

def test_images(test_images, images, verbose = False):
    """Test image"""
    if test_images:
        progressNotify("Image testing.", 2)
        for image in images.listUntested():
            pending.enableOperation(image, 'updateTested')
            image_olist = ""
            inspect = sp_run("buildah inspect " + images.base_uri + image + ':' + images.images[name]['tags'][0], False)
            for entry in inspect.output:
                image_olist = image_olist + entry
            image_json = json.loads(image_olist)
            try:
                test_command = image_json['OCIv1']['config']['Labels'][TESTLABEL]
            except KeyError:
                test_command = "podman --cgroup-manager cgroupfs run --entrypoint=/usr/local/bin/test.sh " + image
            test = sp_run(test_command, verbose)
            nametag = image.rsplit(sep='/')[-1]
            name = ''.join(nametag.rsplit(sep=':')[:-1])
            elapsed = pending.completeOperation()
            images.updateTested(name, test.call.returncode, time = elapsed)
            if test.call.returncode == 0:
                progressNotify("Image tests passed.", 0)
            if test.call.returncode == 1:
                progressNotify("Image tests failed.", 1)
        progressNotify("Image tests complete.", 2)
        return 0
    return 0

def registry_push(disable_registry, images, verbose = False):
    """Push successfully built images to registry"""
    if not disable_registry:
        name_list = images.listBuilt()
        if len(name_list) > 0:
            progressNotify("Registry upload.", 2)
            append = "-q "
            if verbose == True:
                append = ""
            for name in name_list:
                pprofile = cProfile.Profile()
                pprofile = pending.enableOperation(name, 'updatePushed')
                push_failures = 0
                prime_tag =  images.images[name]['tags'][0]
                prime_uri = images.base_uri + name + ':' + prime_tag
                progressNotify("Attempting to push: " + prime_uri, -2)
                push_run = sp_run("sudo buildah push " + append + prime_uri + " " + ''.join(["docker://", prime_uri]), verbose, nonscrolling = True)
                if push_run.call.returncode > 0:
                    progressNotify("Failed to push " + prime_uri, 1)
                    push_failures = push_failures + 1
                elif push_run.call.returncode == 0:
                    progressNotify("Successfully pushed " + prime_uri, 0)
                    for tag in images.images[name]['tags'][1:]:
                        tagged_uri = prime_uri.replace(prime_tag, tag)
                        progressNotify("Attempting to copy: " + tagged_uri, -2)
                        copy_run = sp_run("skopeo copy docker://" + prime_uri + " docker://" + tagged_uri)
                        if copy_run.call.returncode > 0:
                            progressNotify("Failed to copy " + tagged_uri, 1)
                            push_failures = push_failures + 1
                        elif copy_run.call.returncode == 0:
                            progressNotify("Successfully copied " + tagged_uri, 0)
                elapsed = pending.completeOperation()
                if push_failures > 0:
                    images.updatePushed(name, 1, time = elapsed)
                elif push_failures == 0:
                    images.updatePushed(name, 0, time = elapsed)
            progressNotify("Registry upload complete.", 2)
        return 0
    return 0

def progressNotify(message, code):
    """Function to print and log progress."""
    colors = tcolors()
    log = open(LOGFILE, 'a', 1)
    coloring = colors.codeMapping[code]
    print(coloring + colors.BOLD + message + colors.ENDC)
    log.write(message + "\n")
    log.close()

def profileTiming(search, profiler, persist = True):
    """Function to return time consumed by expression passed."""
    #DEFECT: Presently, cProfile presents no ability to pause profiling for signal_handle. This can introduce timing inaccuracies when a user hits ctrl+c to pause or retrieve a summary of the build status.
    timeSum = 0
    profiler.snapshot_stats()
    stats=profiler.stats
    keylist=stats.keys()
    for key in keylist:
        string=str(key)
        regex=re.compile(search) #Find any tuple-key matching search name
        if regex.search(string):
            #print("Key:" + string + "//" + "Value:" + str(stats[key][2]) + ", " + str(stats[key][3]))
            time = stats[key][2]
            timeSum = time + timeSum
            #print(str(timeSum))
    return timeSum

##Main
if __name__ == "__main__":
    pending = pendingOperation()
    signal.signal(2, signal_handler)
    args = parse_arguments(sys.argv[1:])
    images = containerGroup(args)
    children = handler()
    portage_build = portage_build(args.build_portage, images, verbose = args.verbose)
    portagedir = portage_overlay(args, verbose = args.verbose)
    catalyst_build(args.build_catalyst, images, portagedir, verbose = args.verbose)
    stage3_bootstrap(args.build_initial, images, verbose = args.verbose)
    stage3 = stage3_spawn(args.build_initial, verbose = args.verbose)
    initial_build(args.build_initial, images, portagedir, verbose = args.verbose)
    project_build(args.build_targets, images, portagedir, verbose = args.verbose)
    test_images(args.test_images, images, verbose = args.verbose)
    registry_push(args.disable_registry, images, verbose = args.verbose)
    status = images.statusList()
    if args.verbose == True:
        for line in status:
            print(line)
    with open(LOGFILE, 'a', 1) as log:
        for line in status:
           log.write(line + "\n")
    cleanup(verbose = args.verbose)
