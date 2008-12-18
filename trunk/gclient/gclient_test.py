#!/usr/bin/python
#
# Copyright 2008 Google Inc.  All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for gclient.py."""

__author__ = 'stephen5.ng@gmail.com (Stephen Ng)'

import __builtin__
import copy
import os
import random
import string
import subprocess
import sys
import unittest

directory, _file = os.path.split(__file__)
if directory:
  directory += os.sep
sys.path.append(os.path.abspath(directory + '../pymox'))

import gclient
import mox


## Some utilities for generating arbitrary arguments.


def String(max_length):
  return ''.join([random.choice(string.letters)
                  for x in xrange(random.randint(1, max_length))])


def Strings(max_arg_count, max_arg_length):
  return [String(max_arg_length) for x in xrange(max_arg_count)]


def Args(max_arg_count=8, max_arg_length=16):
  return Strings(max_arg_count, random.randint(1, max_arg_length))


def _DirElts(max_elt_count=4, max_elt_length=8):
  return '/'.join(Strings(max_elt_count, max_elt_length))


def Dir(max_elt_count=4, max_elt_length=8):
  return random.choice(('/', '')) + _DirElts(max_elt_count, max_elt_length)

def Url(max_elt_count=4, max_elt_length=8):
  return 'svn://random_host:port/a' + _DirElts(max_elt_count, max_elt_length)

def RootDir(max_elt_count=4, max_elt_length=8):
  return '/' + _DirElts(max_elt_count, max_elt_length)


class BaseTestCase(unittest.TestCase):
  # Like unittest's assertRaises, but checks for Gclient.Error.
  def assertRaisesError(self, msg, fn, *args, **kwargs):
    try:
      fn(*args, **kwargs)
    except gclient.Error, e:
      self.assertEquals(e.message, msg)
    else:
      self.fail('%s not raised' % msg)

  def Options(self, *args, **kwargs):
    return self.OptionsObject(self, *args, **kwargs)

  def setUp(self):
    self.mox = mox.Mox()
    # Mock them to be sure nothing bad happens.
    gclient.FileRead = self.mox.CreateMockAnything()
    gclient.FileWrite = self.mox.CreateMockAnything()
    gclient.RemoveDirectory = self.mox.CreateMockAnything()
    gclient.RunSVN = self.mox.CreateMockAnything()
    gclient.CaptureSVN = self.mox.CreateMockAnything()
    # Doesn't seem to work very well:
    gclient.os = self.mox.CreateMock(os)
    gclient.sys = self.mox.CreateMock(sys)
    gclient.subprocess = self.mox.CreateMock(subprocess)


class GclientTestCase(BaseTestCase):
  class OptionsObject(object):
    def __init__(self, test_case, verbose=False, spec=None,
                 config_filename='a_file_name',
                 entries_filename='a_entry_file_name',
                 deps_file='a_deps_file_name'):
      self.verbose = verbose
      self.spec = spec
      self.config_filename = config_filename
      self.entries_filename = entries_filename
      self.deps_file = deps_file
      self.revisions = []
      self.manually_grab_svn_rev = True

      # Mox
      self.stdout = test_case.stdout
      self.path_exists = test_case.path_exists
      self.platform = test_case.platform
      self.gclient = test_case.gclient
      self.scm_wrapper = test_case.scm_wrapper

  def setUp(self):
    BaseTestCase.setUp(self)
    self.stdout = self.mox.CreateMock(sys.stdout)
    #self.subprocess = self.mox.CreateMock(subprocess)
    # Stub os.path.exists.
    self.path_exists = self.mox.CreateMockAnything()
    self.sys = self.mox.CreateMock(sys)
    self.platform = 'darwin'

    self.gclient = self.mox.CreateMock(gclient.GClient)
    self.scm_wrapper = self.mox.CreateMock(gclient.SCMWrapper)

    self.args = Args()
    self.root_dir = Dir()
    self.url = Url()


class GClientCommandsTestCase(BaseTestCase):
  def testCommands(self):
    known_commands = [gclient.DoConfig, gclient.DoDiff, gclient.DoHelp,
                      gclient.DoStatus, gclient.DoUpdate, gclient.DoRevert]
    for (k,v) in gclient.gclient_command_map.iteritems():
      # If it fails, you need to add a test case for the new command.
      self.assert_(v in known_commands)
    self.mox.ReplayAll()
    self.mox.VerifyAll()


class TestDoConfig(GclientTestCase):
  def setUp(self):
    GclientTestCase.setUp(self)
    # pymox has trouble to mock the class object and not a class instance.
    self.gclient = self.mox.CreateMockAnything()

  def testMissingArgument(self):
    exception_msg = "required argument missing; see 'gclient help config'"

    self.mox.ReplayAll()
    self.assertRaisesError(exception_msg, gclient.DoConfig, self.Options(), ())
    self.mox.VerifyAll()

  def testExistingClientFile(self):
    options = self.Options()
    exception_msg = ('%s file already exists in the current directory' %
                        options.config_filename)
    self.path_exists(options.config_filename).AndReturn(True)

    self.mox.ReplayAll()
    self.assertRaisesError(exception_msg, gclient.DoConfig, options, (1,))
    self.mox.VerifyAll()

  def testFromText(self):
    options = self.Options(spec='config_source_content')
    options.path_exists(options.config_filename).AndReturn(False)
    options.gclient('.', options).AndReturn(options.gclient)
    options.gclient.SetConfig(options.spec)
    options.gclient.SaveConfig()

    self.mox.ReplayAll()
    gclient.DoConfig(options, (1,),)
    self.mox.VerifyAll()

  def testCreateClientFile(self):
    options = self.Options()
    options.path_exists(options.config_filename).AndReturn(False)
    options.gclient('.', options).AndReturn(options.gclient)
    options.gclient.SetDefaultConfig('the_name', 'http://svn/url/the_name')
    options.gclient.SaveConfig()

    self.mox.ReplayAll()
    gclient.DoConfig(options,
                     ('http://svn/url/the_name', 'other', 'args', 'ignored'))
    self.mox.VerifyAll()


class TestDoHelp(GclientTestCase):
  def testGetUsage(self):
    options = self.Options()
    print >> options.stdout, gclient.COMMAND_USAGE_TEXT['config']

    self.mox.ReplayAll()
    gclient.DoHelp(options, ('config',))
    self.mox.VerifyAll()

  def testTooManyArgs(self):
    options = self.Options()
    self.mox.ReplayAll()
    self.assertRaisesError("unknown subcommand; see 'gclient help'",
                           gclient.DoHelp, options, ('config',
                                                     'another argument'))
    self.mox.VerifyAll()

  def testUnknownSubcommand(self):
    options = self.Options()
    self.mox.ReplayAll()
    self.assertRaisesError("unknown subcommand; see 'gclient help'",
                           gclient.DoHelp, options, ('xyzzy',))
    self.mox.VerifyAll()


class GenericCommandTestCase(GclientTestCase):
  def ReturnValue(self, command, function, return_value):
    options = self.Options()
    self.gclient.LoadCurrentConfig(options).AndReturn(self.gclient)
    self.gclient.RunOnDeps(command, self.args).AndReturn(return_value)

    self.mox.ReplayAll()
    result = function(options, self.args)
    self.assertEquals(result, return_value)
    self.mox.VerifyAll()

  def BadClient(self, function):
    options = self.Options()
    self.gclient.LoadCurrentConfig(options).AndReturn(None)

    self.mox.ReplayAll()
    self.assertRaisesError(
        "client not configured; see 'gclient config'",
        function, options, self.args)
    self.mox.VerifyAll()

  def Verbose(self, command, function):
    options = self.Options(verbose=True)
    self.gclient.LoadCurrentConfig(options).AndReturn(self.gclient)
    text = "# Dummy content\nclient = 'my client'"
    self.gclient.ConfigContent().AndReturn(text)
    print >>self.stdout, text
    self.gclient.RunOnDeps(command, self.args).AndReturn(0)

    self.mox.ReplayAll()
    result = function(options, self.args)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()


class TestDoStatus(GenericCommandTestCase):
  def Options(self, verbose=False, *args, **kwargs):
    return self.OptionsObject(self, verbose=verbose, *args, **kwargs)
  
  def testGoodClient(self):
    self.ReturnValue('status', gclient.DoStatus, 0)
  def testError(self):
    self.ReturnValue('status', gclient.DoStatus, 42)
  def testBadClient(self):
    self.BadClient(gclient.DoStatus)


class TestDoUpdate(GenericCommandTestCase):
  def Options(self, verbose=False, *args, **kwargs):
    return self.OptionsObject(self, verbose=verbose, *args, **kwargs)

  def testBasic(self):
    self.ReturnValue('update', gclient.DoUpdate, 0)
  def testError(self):
    self.ReturnValue('update', gclient.DoUpdate, 42)
  def testBadClient(self):
    self.BadClient(gclient.DoUpdate)
  def testVerbose(self):
    self.Verbose('update', gclient.DoUpdate)


class TestDoDiff(GenericCommandTestCase):
  def Options(self, *args, **kwargs):
      return self.OptionsObject(self, *args, **kwargs)

  def testBasic(self):
    self.ReturnValue('diff', gclient.DoDiff, 0)
  def testError(self):
    self.ReturnValue('diff', gclient.DoDiff, 42)
  def testBadClient(self):
    self.BadClient(gclient.DoDiff)
  def testVerbose(self):
    self.Verbose('diff', gclient.DoDiff)


class TestDoRevert(GenericCommandTestCase):
  def testBasic(self):
    self.ReturnValue('revert', gclient.DoRevert, 0)
  def testError(self):
    self.ReturnValue('revert', gclient.DoRevert, 42)
  def testBadClient(self):
    self.BadClient(gclient.DoRevert)




class GClientClassTestCase(GclientTestCase):
  def testDir(self):
    members = ['ConfigContent', 'FromImpl', '_GetAllDeps',
      '_GetDefaultSolutionDeps', 'GetVar', '_LoadConfig', 'LoadCurrentConfig',
      '_ReadEntries', 'RunOnDeps', 'SaveConfig', '_SaveEntries', 'SetConfig',
      'SetDefaultConfig', '__class__', '__delattr__', '__dict__', '__doc__',
      '__getattribute__', '__hash__', '__init__', '__module__', '__new__',
      '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__str__',
      '__weakref__', 'supported_commands']

    # If you add a member, be sure to add the relevant test!
    self.assertEqual(sorted(dir(gclient.GClient)), sorted(members))
    self.mox.ReplayAll()
    self.mox.VerifyAll()

  def testSetConfig_ConfigContent_GetVar_SaveConfig_SetDefaultConfig(self):
    options = self.Options()
    text = "# Dummy content\nclient = 'my client'"
    gclient.FileWrite(os.path.join(self.root_dir, options.config_filename),
                      text)

    self.mox.ReplayAll()
    client = gclient.GClient(self.root_dir, options)
    client.SetConfig(text)
    self.assertEqual(client.ConfigContent(), text)
    self.assertEqual(client.GetVar('client'), 'my client')
    self.assertEqual(client.GetVar('foo'), None)
    client.SaveConfig()

    solution_name = 'solution name'
    solution_url = 'solution url'
    default_text = gclient.DEFAULT_CLIENT_FILE_TEXT % (solution_name,
                                                       solution_url)
    client.SetDefaultConfig(solution_name, solution_url)
    self.assertEqual(client.ConfigContent(), default_text)
    solutions = [{'name':solution_name, 'url':solution_url, 'custom_deps':{}}]
    self.assertEqual(client.GetVar('solutions'), solutions)
    self.assertEqual(client.GetVar('foo'), None)
    self.mox.VerifyAll()

  def testLoadCurrentConfig(self):
    # pymox has trouble to mock the class object and not a class instance.
    self.gclient = self.mox.CreateMockAnything()
    options = self.Options()
    path = os.path.realpath(self.root_dir)
    options.path_exists(os.path.join(path, options.config_filename)
        ).AndReturn(True)
    options.gclient(path, options).AndReturn(options.gclient)
    options.gclient._LoadConfig()

    self.mox.ReplayAll()
    client = gclient.GClient.LoadCurrentConfig(options, self.root_dir)
    self.mox.VerifyAll()

  def testRunOnDepsSuccess(self):
    # Fake .gclient file.
    name = 'testRunOnDepsSuccess_solution_name'
    gclient_config = """solutions = [ {
  'name': '%s',
  'url': '%s',
  'custom_deps': {},
}, ]""" % (name, self.url)

    # pymox has trouble to mock the class object and not a class instance.
    self.scm_wrapper = self.mox.CreateMockAnything()
    options = self.Options()
    options.path_exists(os.path.join(self.root_dir, options.entries_filename)
        ).AndReturn(False)
    options.scm_wrapper(self.url, self.root_dir, name).AndReturn(
        options.scm_wrapper)
    options.scm_wrapper.RunCommand('update', options, self.args)
    gclient.FileRead(os.path.join(self.root_dir, name, options.deps_file)
        ).AndReturn("Boo = 'a'")
    gclient.FileWrite(os.path.join(self.root_dir, options.entries_filename),
                      'entries = [\n  "%s",\n]\n' % name)

    self.mox.ReplayAll()
    client = gclient.GClient(self.root_dir, options)
    client.SetConfig(gclient_config)
    client.RunOnDeps('update', self.args)
    self.mox.VerifyAll()

  def testRunOnDepsRevisions(self):
    def OptIsRev(options, rev):
      if not options.revision == str(rev):
        print "options.revision = %s" % options.revision
      return options.revision == str(rev)
    def OptIsRevNone(options):
      if options.revision:
        print "options.revision = %s" % options.revision
      return options.revision == None
    def OptIsRev42(options):
      return OptIsRev(options, 42)
    def OptIsRev123(options):
      return OptIsRev(options, 123)
    def OptIsRev333(options):
      return OptIsRev(options, 333)

    # Fake .gclient file.
    gclient_config = """solutions = [ {
  'name': 'src',
  'url': '%s',
  'custom_deps': {},
}, ]""" % self.url
    # Fake DEPS file.
    deps_content = """deps = {
  'src/breakpad/bar': 'http://google-breakpad.googlecode.com/svn/trunk/src@285',
  'foo/third_party/WebKit': '/trunk/deps/third_party/WebKit',
  'src/third_party/cygwin': '/trunk/deps/third_party/cygwin@3248',
}
deps_os = {
  'win': {
    'src/foosad/asdf': 'svn://random_server:123/asd/python_24@5580',
  },
  'mac': {
    'src/third_party/python_24': 'svn://random_server:123/trunk/python_24@5580',
  },
}"""
    entries_content = (
      'entries = [\n  "src",\n'
      '  "foo/third_party/WebKit",\n'
      '  "src/third_party/cygwin",\n'
      '  "src/third_party/python_24",\n'
      '  "src/breakpad/bar",\n'
      ']\n')
    cygwin_path = 'dummy path cygwin'
    webkit_path = 'dummy path webkit'

    # pymox has trouble to mock the class object and not a class instance.
    self.scm_wrapper = self.mox.CreateMockAnything()
    scm_wrapper_bleh = self.mox.CreateMock(gclient.SCMWrapper)
    scm_wrapper_src = self.mox.CreateMock(gclient.SCMWrapper)
    scm_wrapper_src2 = self.mox.CreateMock(gclient.SCMWrapper)
    scm_wrapper_webkit = self.mox.CreateMock(gclient.SCMWrapper)
    scm_wrapper_breakpad = self.mox.CreateMock(gclient.SCMWrapper)
    scm_wrapper_cygwin = self.mox.CreateMock(gclient.SCMWrapper)
    scm_wrapper_python = self.mox.CreateMock(gclient.SCMWrapper)
    options = self.Options()
    options.revisions = [ 'src@123', 'foo/third_party/WebKit@42',
                          'src/third_party/cygwin@333' ]

    # Also, pymox doesn't verify the order of function calling w.r.t. different
    # mock objects. Pretty lame. So reorder as we wish to make it clearer.
    gclient.FileRead(os.path.join(self.root_dir, 'src', options.deps_file)
        ).AndReturn(deps_content)
    gclient.FileWrite(os.path.join(self.root_dir, options.entries_filename),
                      entries_content)

    options.path_exists(os.path.join(self.root_dir, options.entries_filename)
        ).AndReturn(False)
    
    options.scm_wrapper(self.url, self.root_dir, 'src').AndReturn(
        scm_wrapper_src)
    scm_wrapper_src.RunCommand('update', mox.Func(OptIsRev123), self.args)

    options.scm_wrapper(self.url, self.root_dir,
                        None).AndReturn(scm_wrapper_src2)
    scm_wrapper_src2.FullUrlForRelativeUrl('/trunk/deps/third_party/cygwin@3248'
        ).AndReturn(cygwin_path)

    options.scm_wrapper(self.url, self.root_dir,
                        None).AndReturn(scm_wrapper_src2)
    scm_wrapper_src2.FullUrlForRelativeUrl('/trunk/deps/third_party/WebKit'
        ).AndReturn(webkit_path)

    options.scm_wrapper(webkit_path, self.root_dir,
                        'foo/third_party/WebKit').AndReturn(scm_wrapper_webkit)
    scm_wrapper_webkit.RunCommand('update', mox.Func(OptIsRev42), self.args)

    options.scm_wrapper(
        'http://google-breakpad.googlecode.com/svn/trunk/src@285',
        self.root_dir, 'src/breakpad/bar').AndReturn(scm_wrapper_breakpad)
    scm_wrapper_breakpad.RunCommand('update', mox.Func(OptIsRevNone), self.args)

    options.scm_wrapper(cygwin_path, self.root_dir,
                        'src/third_party/cygwin').AndReturn(scm_wrapper_cygwin)
    scm_wrapper_cygwin.RunCommand('update', mox.Func(OptIsRev333), self.args)

    options.scm_wrapper('svn://random_server:123/trunk/python_24@5580',
                        self.root_dir,
                        'src/third_party/python_24').AndReturn(
                            scm_wrapper_python)
    scm_wrapper_python.RunCommand('update', mox.Func(OptIsRevNone), self.args)

    self.mox.ReplayAll()
    client = gclient.GClient(self.root_dir, options)
    client.SetConfig(gclient_config)
    client.RunOnDeps('update', self.args)
    self.mox.VerifyAll()

  def testRunOnDepsFailureInvalidCommand(self):
    options = self.Options()

    self.mox.ReplayAll()
    client = gclient.GClient(self.root_dir, options)
    exception = "'foo' is an unsupported command"
    self.assertRaisesError(exception, gclient.GClient.RunOnDeps, client, 'foo',
                           self.args)
    self.mox.VerifyAll()

  def testRunOnDepsFailureEmpty(self):
    options = self.Options()

    self.mox.ReplayAll()
    client = gclient.GClient(self.root_dir, options)
    exception = "No solution specified"
    self.assertRaisesError(exception, gclient.GClient.RunOnDeps, client,
                           'update', self.args)
    self.mox.VerifyAll()

  def testFromImpl(self):
    # TODO(maruel):  Test me!
    pass

  # No test for internal functions.
  def test_GetAllDeps(self):
    pass
  def test_GetDefaultSolutionDeps(self):
    pass
  def test_LoadConfig(self):
    pass
  def test_ReadEntries(self):
    pass
  def test_SaveEntries(self):
    pass


class SCMWrapperTestCase(BaseTestCase):
  class OptionsObject(object):
     def __init__(self, test_case, verbose=False, revision=None):
      self.verbose = verbose
      self.revision = revision
      self.manually_grab_svn_rev = True

      # Mox
      self.stdout = test_case.stdout
      self.path_exists = test_case.path_exists

  def setUp(self):
    BaseTestCase.setUp(self)
    self.root_dir = Dir()
    self.args = Args()
    self.url = Url()
    self.relpath = 'asf'
    self.stdout = self.mox.CreateMock(sys.stdout)
    # Stub os.path.exists.
    self.path_exists = self.mox.CreateMockAnything()

  def testDir(self):
    members = ['FullUrlForRelativeUrl', 'RunCommand', '__class__',
      '__delattr__', '__dict__', '__doc__', '__getattribute__',
      '__hash__', '__init__', '__module__', '__new__', '__reduce__',
      '__reduce_ex__', '__repr__', '__setattr__', '__str__', '__weakref__',
      'diff', 'revert', 'status', 'update']

    # If you add a member, be sure to add the relevant test!
    self.assertEqual(sorted(dir(gclient.SCMWrapper)), sorted(members))
    self.mox.ReplayAll()
    self.mox.VerifyAll()

  def testFullUrlForRelativeUrl(self):
    self.url = 'svn://a/b/c/d'

    self.mox.ReplayAll()
    scm = gclient.SCMWrapper(url=self.url, root_dir=self.root_dir,
                             relpath=self.relpath)
    self.assertEqual(scm.FullUrlForRelativeUrl('/crap'), 'svn://a/b/crap')
    self.mox.VerifyAll()

  def testRunCommandException(self):
    options = self.Options(verbose=False)
    options.path_exists(os.path.join(self.root_dir, self.relpath, '.git')
        ).AndReturn(False)

    self.mox.ReplayAll()
    scm = gclient.SCMWrapper(url=self.url, root_dir=self.root_dir,
                             relpath=self.relpath)
    exception = "Unsupported argument(s): %s" % ','.join(self.args)
    self.assertRaisesError(exception, gclient.SCMWrapper.RunCommand,
                           scm, 'update', options, self.args)
    self.mox.VerifyAll()

  def testRunCommandUnknown(self):
    # TODO(maruel): if ever used.
    pass

  def testRevertMissing(self):
    options = self.Options(verbose=True)
    gclient.os.path.isdir = self.mox.CreateMockAnything()
    gclient.os.path.isdir(os.path.join(self.root_dir, self.relpath)
        ).AndReturn(False)
    print >>options.stdout, ("\n_____ %s is missing, can't revert" %
                             self.relpath)

    self.mox.ReplayAll()
    scm = gclient.SCMWrapper(url=self.url, root_dir=self.root_dir,
                             relpath=self.relpath)
    scm.revert(options, self.args)
    self.mox.VerifyAll()
    gclient.os.path.isdir = os.path.isdir

  def testRevertNone(self):
    options = self.Options(verbose=True)
    base_path = os.path.join(self.root_dir, self.relpath)
    gclient.os.path.isdir = self.mox.CreateMockAnything()
    gclient.os.path.isdir(base_path).AndReturn(True)
    text = "\n"
    gclient.CaptureSVN(options, ['status'], base_path).AndReturn(text)

    self.mox.ReplayAll()
    scm = gclient.SCMWrapper(url=self.url, root_dir=self.root_dir,
                             relpath=self.relpath)
    scm.revert(options, self.args)
    self.mox.VerifyAll()
    gclient.os.path.isdir = os.path.isdir

  def testRevert2Files(self):
    options = self.Options(verbose=True)
    base_path = os.path.join(self.root_dir, self.relpath)
    gclient.os.path.isdir = self.mox.CreateMockAnything()
    gclient.os.path.isdir(base_path).AndReturn(True)
    text = "M      a\nA      b\n"
    gclient.CaptureSVN(options, ['status'], base_path).AndReturn(text)

    print >>options.stdout, os.path.join(base_path, 'a')
    print >>options.stdout, os.path.join(base_path, 'b')
    gclient.RunSVN(options, ['revert', 'a', 'b'], base_path)

    self.mox.ReplayAll()
    scm = gclient.SCMWrapper(url=self.url, root_dir=self.root_dir,
                             relpath=self.relpath)
    scm.revert(options, self.args)
    self.mox.VerifyAll()
    gclient.os.path.isdir = os.path.isdir

  def testStatus(self):
    options = self.Options(verbose=True)
    base_path = os.path.join(self.root_dir, self.relpath)
    gclient.RunSVN(options, ['status'] + self.args, base_path).AndReturn(None)

    self.mox.ReplayAll()
    scm = gclient.SCMWrapper(url=self.url, root_dir=self.root_dir,
                             relpath=self.relpath)
    self.assertEqual(scm.status(options, self.args), None)
    self.mox.VerifyAll()

  # TODO(maruel):  TEST REVISIONS!!!
  # TODO(maruel):  TEST RELOCATE!!!
  def testUpdateCheckout(self):
    options = self.Options(verbose=True)
    base_path = os.path.join(self.root_dir, self.relpath)
    options.path_exists(os.path.join(base_path, '.git')).AndReturn(False)
    # Checkout or update.
    options.path_exists(base_path).AndReturn(False)
    gclient.RunSVN(options, ['checkout', self.url, base_path], self.root_dir)

    self.mox.ReplayAll()
    scm = gclient.SCMWrapper(url=self.url, root_dir=self.root_dir,
                             relpath=self.relpath)
    scm.update(options, ())
    self.mox.VerifyAll()

  def testUpdateUpdate(self):
    xml_text = """<?xml version="1.0"?>
<info>
<entry
   kind="dir"
   path="."
   revision="35">
<url>%s</url>
<repository>
<root>%s</root>
<uuid>7b9385f5-0452-0410-af26-ad4892b7a1fb</uuid>
</repository>
<wc-info>
<schedule>normal</schedule>
<depth>infinity</depth>
</wc-info>
<commit
   revision="35">
<author>maruel</author>
<date>2008-12-04T20:12:19.685120Z</date>
</commit>
</entry>
</info>
""" % (self.url, self.url)
    options = self.Options(verbose=True)
    base_path = os.path.join(self.root_dir, self.relpath)
    options.force = True
    options.path_exists(os.path.join(base_path, '.git')).AndReturn(False)
    # Checkout or update.
    options.path_exists(base_path).AndReturn(True)
    gclient.CaptureSVN(options, ['info', '--xml', os.path.join(base_path, '.')],
                       '.').AndReturn(xml_text)
    additional_args = []
    if options.manually_grab_svn_rev:
      gclient.CaptureSVN(options, ['info', '--xml', self.url],
                         '.').AndReturn(xml_text)
      additional_args = ['--revision', '35']
    gclient.RunSVN(options, ['update', base_path] + additional_args,
                   self.root_dir).AndReturn(xml_text)
    # print >>options.stdout, ("\n_____ updating %s%s" % (self.relpath, ' at 35'))

    self.mox.ReplayAll()
    scm = gclient.SCMWrapper(url=self.url, root_dir=self.root_dir,
                             relpath=self.relpath)
    scm.update(options, ())
    self.mox.VerifyAll()

  def testUpdateGit(self):
    options = self.Options(verbose=True)
    options.path_exists(os.path.join(self.root_dir, self.relpath, '.git')
        ).AndReturn(True)
    print >> options.stdout, (
        "________ found .git directory; skipping %s" % self.relpath)

    self.mox.ReplayAll()
    scm = gclient.SCMWrapper(url=self.url, root_dir=self.root_dir,
                             relpath=self.relpath)
    scm.update(options, self.args)
    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
