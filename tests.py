#!/usr/bin/python3

import sys
import os
import time
import unittest
from pybuild import bcolors, parse_arguments, sp_run, portage_build, portage_overlay, catalyst_build, stage3_bootstrap, stage3_spawn, buildah_build, initial_build, project_build, cleanup, registry_push, parse_arguments, build_return_sort, push_return_sort

SCRIPTPATH = os.path.dirname(os.path.realpath(__file__))
LOGFILE = ''.join([SCRIPTPATH, '/log.unittest'])
REGISTRY = "crucible.lab:4000"
NAMESPACE = "/oci/"
TESTIMAGE = "alpine:edge"
DATE = time.strftime("%Y-%m-%d")
CATALYST_BIND_PATH = ''.join([SCRIPTPATH, '/.tmpcatalyst'])
BUILT = []

class unitTests(unittest.TestCase):
    """All tests responsible for testing the internal components of individual functions."""

    def test_sp_run_output(self):
        """Test to ensure that sp_run can parse and run a command to generate terminal output."""
        output_test = sp_run("echo test", True)
        xoutput = ["test\n"]
        self.assertEqual(output_test.call.returncode, 0)
        self.assertEqual(output_test.output, xoutput)
    
    def test_sp_run_xfail(self):
        """Test to ensure that sp_run handles failures appropriately."""
        xfail_test = sp_run("/bin/false")
        self.assertEqual(xfail_test.call.returncode, 1)
    
    def test_sp_run_xpass(self):
        """Test to ensure that sp_run handles successes appropriately."""
        xpass_test = sp_run("/bin/true")
        self.assertEqual(xpass_test.call.returncode, 0)

    def test_sp_run_file(self):
        """Test to ensure that sp_run can read, write and  delete files."""
        write_test = sp_run("touch " + SCRIPTPATH + "/test.file")
        read_test = sp_run("cat " + SCRIPTPATH + "/test.file")
        rm_test = sp_run("rm " + SCRIPTPATH + "/test.file")
        self.assertEqual(write_test.call.returncode, 0)
        self.assertEqual(read_test.call.returncode, 0)
        self.assertEqual(rm_test.call.returncode, 0)

    #def test_build_return_sort_failure(self):
    #    """Test to ensure that build_return_sort handles failures appropriately."""
    
    #def test_build_return_sort_built(self):
    #    """Test to ensure that build_return_sort handles successful builds appropriately."""
    
    #def test_push_return_sort_failure(self):
    #    """Test to ensure that push_return_sort handles failures appropriately."""

    #def test_push_return_sort_succeeded(self):
    #    """Test to ensure that push_return_sort handles successes appropriately."""

class nopTests(unittest.TestCase):
    """All tests responsible for testing functions disabled by arguments."""
   
    def test_portage_build_nop(self):
        """Test to ensure that a portage container isn't built and synced if -p isn't called."""
        code = portage_build(nopargs.build_portage, True)
        self.assertEqual(code, None)

    def test_portage_overlay_nop(self):
        """Test to ensure that a portage overlay container isn't spawned if -i, -c, or -b [...] aren't called."""
        code = portage_overlay(nopargs, True)
        self.assertEqual(code, None)

    def test_catalyst_build_nop(self):
        """Test to ensure that catalyst_build doesn't do anything if -c isn't called."""
        code = catalyst_build(nopargs.build_catalyst, '', True)
        self.assertEqual(code, None)

    def test_stage3_bootstrap_nop(self):
        """Test to ensure that stage3_bootstrap doesn't do anything if -i isn't called."""
        code = stage3_bootstrap(nopargs.build_initial, True)
        self.assertEqual(code, None)

    def test_stage3_spawn_nop(self):
        """Test to ensure that stage3_spawn doesn't do anything if -i isn't called."""
        code = stage3_bootstrap(nopargs.build_initial, True)
        self.assertEqual(code, None)
    
    def test_initial_build_nop(self):
        """Test to ensure that initial build doesn't do anything if -i isn't called."""
        code = stage3_bootstrap(nopargs.build_initial, True)
        self.assertEqual(code, None)
    
    def test_project_build_nop(self):
        """Test to ensure that project build doesn't do anything if fed an empty list of targets."""
        code = stage3_bootstrap(nopargs.build_targets, True)
        self.assertEqual(code, None)
    
    #buildah_build [not called directly]
    #sp_run [not called directly]

class proceduralTests(unittest.TestCase):
    """All methods responsible for testing functional code paths."""
    def setUp(self):
        BUILT = []
        FAILED = []
        SUCCEEDED = []

    def test_portage_build_xpass(self):
        """Test to ensure that buildah can run the portage_build procedure."""
        prefix = ''.join([REGISTRY, NAMESPACE])
        built_list = [''.join([prefix, "portagedir:", DATE]), ''.join([prefix, "portagedir:latest"])]
        result = portage_build(verboseargs.build_portage, False)
        self.assertEqual(result[0], 0)
        #self.assertIn()

    #def test_portage_build_xfail(self):
    #    """Test to ensure that portage_build fails appropriately when sync or buildah commit fail."""
    #    result = portage_build(verboseargs.build_portage, False)
    #    self.assertEqual(result[0], 1)

    def test_portage_overlay_run(self):
        """Test to ensure that buidlah can spawn and mount a container."""
        mount_point = portage_overlay(nonverboseargs)
        self.assertIn('/var/lib/containers/storage/overlay', mount_point)

    def test_catalyst_build_xpass(self):
        """Test to ensure that buidlah can run the catalyst_build procedure and download the STAGE3URL configured in pybuild.py."""
        tmpdir = ''.join([SCRIPTPATH, '/.tmpcatalyst'])
        specdir = ''.join([SCRIPTPATH, '/.tmpcatalyst/default'])
        #tmpspec = ''.join([specdir, '/test.spec'])
        stage3path = ''.join([SCRIPTPATH, '.stages/builds/hardened/stage3-amd64-hardened-latest.tar.bz2'])
        os.makedirs(specdir)
        if os.path.isfile(stage3path):
            os.remove(stage3path)
        #with open(tmpspec, 'w') as spec:
        #    spec.write('subarch: amd64\ntarget: stage3\nversion_stamp: hardened-latest\nrel_type: hardened\nprofile: default/linux/amd64/17.0/hardened\nsnapshot: latest\nsource_subpath: hardened/stage2-amd64-hardened-latest\ncompression_mode: bzip2\ndecompressor_search_order: tar pixz xz lbzip2 bzip2 gzip\nportage_confdir: /etc/catalyst/portage/')
        #    spec.flush()
        #    spec.close()
        #    result, uris = catalyst_build(verboseargs.build_catalyst, tmpdir, False, tmpdir)
        result = catalyst_build(nonverboseargs.build_catalyst, tmpdir, False, tmpdir)
        #os.remove(tmpspec)
        #os.rmdir(specdir)
        #os.rmdir(tmpdir)
        os.system("rm -rf " + tmpdir)
        prefix = ''.join([REGISTRY, NAMESPACE])
        xuris = [''.join([prefix, "catalyst-cache:latest"])]
        self.assertEqual(result, 0)
        #self.assertEqual(pybuild.BUILT, xuris)

    #def test_catalyst_build_xfail(self):
    #    """Test to ensure that catalyst_build fails appropriately when the cache fails to mount or commit fails."""
    
    #def test_stage3_bootstrap_xpass(self):
    #    """Test to ensure that stage3_bootstrap handles successful bootstrapping appropriately."""
    
    #def test_stage3_bootstrap_xfail(self):
    #    """Test to ensure that stage3_bootstrap handles failures appropriately."""

    #def test_stage3_spawn_run(self):
    #    """Test to ensure that stage3_spawn successfully creates a mounts a bootstrapped stage3 container."""

    def test_buildah_build_xpass(self):
        """Test to ensure that subprocess can run buildah to build a container."""
        tmpfile = ''.join([SCRIPTPATH,"/.test_buildah_build_nop"])
        tmpmnt = ''.join([SCRIPTPATH,"/.tmpmnt"])
        image = ''.join([REGISTRY, NAMESPACE, TESTIMAGE])
        os.makedirs(tmpmnt)
        with open(tmpfile, 'w') as bud:
            bud.write("FROM " + image + "\nRUN /bin/true\n")
            bud.flush()
            result, built = buildah_build(tmpfile, "tmp", SCRIPTPATH, tmpmnt, nonverboseargs.verbose)
        os.remove(tmpfile)
        os.rmdir(tmpmnt)
        prefix = ''.join([REGISTRY, NAMESPACE])
        built_list = [''.join([prefix, "tmp:", DATE]), ''.join([prefix, "tmp:latest"])]
        self.assertEqual(result, 0)
        self.assertEqual(built, built_list)

    def test_buildah_build_xfail(self):
        """Test to ensure that subprocess can run buildah and fails appropriately."""
        tmpfile = ''.join([SCRIPTPATH,"/.test_buildah_build_xfail"])
        tmpmnt = ''.join([SCRIPTPATH,"/.tmpmnt"])
        image = ''.join([REGISTRY, NAMESPACE, TESTIMAGE])
        os.makedirs(tmpmnt)
        with open(tmpfile, 'w') as bud:
            bud.write("FROM " + image + "\nRUN /bin/false\n")
            bud.flush()
        result, failed = buildah_build(tmpfile, "tmp", SCRIPTPATH, tmpmnt, nonverboseargs.verbose)
        os.remove(tmpfile)
        os.rmdir(tmpmnt)
        #prefix = ''.join([REGISTRY, NAMESPACE])
        #xfail_list = [''.join([prefix, "tmp:", DATE]), ''.join([prefix, "tmp:latest"])]
        self.assertEqual(result, 1)
        #self.assertEqual(failed, xfail_list)

    #def test_initial_build_run(self):
    #    """Test to ensure that initial_build can run appropriately."""
    
    #def test_project_build_run(self):
    #    """Test to ensure that project_build can run appropriately."""
    
    def test_cleanup_none(self):
        """Test to ensure that the cleanup function runs successfully."""
        code = cleanup(True)
        self.assertEqual(code, 0)
    
    #def test_registry_push_run(self):
    #    """Test to ensure that registry_push can run appropriately."""
    
def nopSuite():
    """List and include all methods in the nopSuite class"""
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(nopTests))
    return suite
    
def unitSuite():
    """List and include all methods in the unitSuite class"""
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(unitTests))
    return suite

def proceduralSuite():
    """List and include all methods in the proceduralSuite class"""
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(proceduralTests))
    return suite

if __name__ == '__main__':
    arguments = ["-v", "-p", "-c", "-i", "-b", "all"]
    verboseargs = parse_arguments(arguments)
    arguments = ["-v"]
    nopargs = parse_arguments(arguments)
    arguments = ["-p", "-c", "-i", "-b", "all"]
    nonverboseargs = parse_arguments(arguments)
    runner = unittest.TextTestRunner(verbosity=2, warnings='always')
    print(bcolors.YELLOW + bcolors.BOLD +"Running codepath tests for disabled functions.\n" + bcolors.ENDC)
    runner.run(nopSuite())
    print(bcolors.YELLOW + bcolors.BOLD +"Running unit tests.\n" + bcolors.ENDC)
    runner.run(unitSuite())
    print(bcolors.YELLOW + bcolors.BOLD +"Running procedural functional tests.\n" + bcolors.ENDC)
    runner.run(proceduralSuite())
