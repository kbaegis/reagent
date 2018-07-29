#!/usr/bin/python3

import sys
import os
import unittest
from pybuild import bcolors, parse_arguments, sp_run, portage_build, catalyst_build, stage3_spawn, buildah_build, initial_build, project_build, cleanup, registry_push, parse_arguments

SCRIPTPATH = os.path.dirname(os.path.realpath(__file__))
LOGFILE = ''.join([SCRIPTPATH, '/log.unittest'])
REGISTRY = "crucible.lab:4000"
NAMESPACE = "/nulllabs/"
TESTIMAGE = "alpine:edge"

#class TestBuildFunctions(unittest.TestCase):
class unitTests(unittest.TestCase):

    def test_sp_run_output(self):
        output_test = sp_run("echo test", True)
        xoutput = ["test\n"]
        self.assertEqual(output_test.call.returncode, 0)
        self.assertEqual(output_test.output, xoutput)
    
    def test_sp_run_xfail(self):
        xfail_test = sp_run("/bin/false")
        self.assertEqual(xfail_test.call.returncode, 1)
    
    def test_sp_run_xpass(self):
        xpass_test = sp_run("/bin/true")
        self.assertEqual(xpass_test.call.returncode, 0)

    def test_sp_run_file(self):
        write_test = sp_run("touch " + SCRIPTPATH + "/test.file")
        read_test = sp_run("cat " + SCRIPTPATH + "/test.file")
        rm_test = sp_run("rm " + SCRIPTPATH + "/test.file")
        self.assertEqual(write_test.call.returncode, 0)
        self.assertEqual(read_test.call.returncode, 0)
        self.assertEqual(rm_test.call.returncode, 0)

class proceduralTests(unittest.TestCase):

    def test_buildah_build_nop(self):
        tmpfile = ''.join([SCRIPTPATH,"/.test_buildah_build_nop"])
        tmpmnt = ''.join([SCRIPTPATH,"/.tmpmnt"])
        image = ''.join([REGISTRY, NAMESPACE, TESTIMAGE])
        os.makedirs(tmpmnt)
        with open(tmpfile, 'w') as bud:
            bud.write("FROM " + image + "\nRUN /bin/true\n")
            bud.flush()
            result = buildah_build(tmpfile, "tmp", SCRIPTPATH, tmpmnt, args.verbose)
        os.remove(tmpfile)
        os.rmdir(tmpmnt)
        self.assertEqual(result, 0)

    def test_buildah_build_xfail(self):
        tmpfile = ''.join([SCRIPTPATH,"/.test_buildah_build_xfail"])
        tmpmnt = ''.join([SCRIPTPATH,"/.tmpmnt"])
        image = ''.join([REGISTRY, NAMESPACE, TESTIMAGE])
        os.makedirs(tmpmnt)
        with open(tmpfile, 'w') as bud:
            bud.write("FROM " + image + "\nRUN /bin/false\n")
            bud.flush()
            result = buildah_build(tmpfile, "tmp", SCRIPTPATH, tmpmnt, args.verbose)
        os.remove(tmpfile)
        os.rmdir(tmpmnt)
        self.assertEqual(result, 1)

def unitSuite():
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(unitTests))
    return suite

def proceduralSuite():
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(proceduralTests))
    return suite
    

if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2, warnings='always')
    print(bcolors.YELLOW + bcolors.BOLD +"Running unit tests.\n" + bcolors.ENDC)
    arguments = ["-v", "-p", "-c", "-i", "-b", "all"]
    args = parse_arguments(arguments)
    runner.run(unitSuite())
    print(bcolors.YELLOW + bcolors.BOLD +"Running procedural functional tests.\n" + bcolors.ENDC)
    arguments = ["-p", "-c", "-i", "-b", "all"]
    args = parse_arguments(arguments)
    runner.run(proceduralSuite())
