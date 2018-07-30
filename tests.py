#!/usr/bin/python3

import sys
import os
import time
import unittest
from pybuild import bcolors, parse_arguments, sp_run, portage_build, portage_overlay, catalyst_build, stage3_bootstrap, stage3_spawn, buildah_build, initial_build, project_build, cleanup, registry_push, parse_arguments

SCRIPTPATH = os.path.dirname(os.path.realpath(__file__))
LOGFILE = ''.join([SCRIPTPATH, '/log.unittest'])
REGISTRY = "crucible.lab:4000"
NAMESPACE = "/oci/"
TESTIMAGE = "alpine:edge"
DATE = time.strftime("%Y-%m-%d")

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

class nopTests(unittest.TestCase):
    """All tests responsible for testing functions disabled by arguments."""
   
    def test_portage_build_nop(self):
        """Test to ensure that a portage container isn't built and synced if -p isn't called."""
        code = portage_build(nopargs.build_portage, True)
        self.assertEqual(code, 0)

    def test_portage_overlay_nop(self):
        """Test to ensure that a portage overlay container isn't spawned if -i, -c, or -b [...] aren't called."""
        code = portage_overlay(nopargs, True)
        self.assertEqual(code, 0)

    def test_catalyst_build_nop(self):
        """Test to ensure that catalyst_build doesn't do anything if -c isn't called."""
        code = catalyst_build(nopargs.build_catalyst, '', True)
        self.assertEqual(code, 0)

    def test_stage3_bootstrap_nop(self):
        """Test to ensure that stage3_bootstrap doesn't do anything if -i isn't called."""
        code = stage3_bootstrap(nopargs.build_initial, True)
        self.assertEqual(code, 0)

    def test_stage3_spawn_nop(self):
        """Test to ensure that stage3_spawn doesn't do anything if -i isn't called."""
        code = stage3_bootstrap(nopargs.build_initial, True)
        self.assertEqual(code, 0)
    
    def test_initial_build_nop(self):
        """Test to ensure that initial build doesn't do anything if -i isn't called."""
        code = stage3_bootstrap(nopargs.build_initial, True)
        self.assertEqual(code, 0)
    
    def test_project_build_nop(self):
        """Test to ensure that project build doesn't do anything if fed an empty list of targets."""
        code = stage3_bootstrap(nopargs.build_targets, True)
        self.assertEqual(code, 0)
    
    #buildah_build
    #sp_run

class proceduralTests(unittest.TestCase):
    """All methods responsible for testing functional code paths."""

    def test_buildah_build_nop(self):
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
        prefix = ''.join([REGISTRY, NAMESPACE])
        xfail_list = [''.join([prefix, "tmp:", DATE]), ''.join([prefix, "tmp:latest"])]
        self.assertEqual(result, 1)
        self.assertEqual(failed, xfail_list)

    def test_portage_overlay_spawn(self):
        """Test to ensure that buidlah can spawn and mount a container."""
        mount_point = portage_overlay(nonverboseargs)
        self.assertIn('/var/lib/containers/storage/overlay', mount_point)

    def test_cleanup_none(self):
        """Test to ensure that the cleanup function runs successfully."""
        code = cleanup(True)
        self.assertEqual(code, 0)

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
    
def nopSuite():
    """List and include all methods in the nopSuite class"""
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(nopTests))
    return suite
    
if __name__ == '__main__':
    arguments = ["-v", "-p", "-c", "-i", "-b", "all"]
    args = parse_arguments(arguments)
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
