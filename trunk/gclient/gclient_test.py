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


# Some utilities for generating arbitrary arguments.


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


def RootDir(max_elt_count=4, max_elt_length=8):
  return '/' + _DirElts(max_elt_count, max_elt_length)


class GclientTestCase(unittest.TestCase):
  # Like unittest's assertRaises, but checks for Gclient.Error.

  def assertRaisesError(self, msg, fn, *args, **kwargs):
    try:
      fn(*args, **kwargs)
    except gclient.Error, e:
      self.assertEquals(e.message, msg)
    else:
      self.fail('%s not raised' % msg)


class TestRunSVN(GclientTestCase):
  def setUp(self):
    self.mox = mox.Mox()
    self.stdout = self.mox.CreateMock(sys.stdout)
    self.subprocess = self.mox.CreateMock(subprocess)
    self.logger = self.mox.CreateMock(sys.stdout)
    self.os_path = self.mox.CreateMock(os.path)

    self.args = Args()
    self.dir = Dir()

    # The function we want to test with all the dependencies mocked out.
    self.run_svn = lambda args, dir: gclient.RunSVN(
        args, dir,
        self.stdout, self.subprocess.call, self.os_path.realpath)

    # Set shared expectations--every call to RunSVN will make these calls.
    self.os_path.realpath(self.dir).AndReturn(os.path.realpath(self.dir))
    self.stdout.write("\n________ running 'svn %s' in '%s'" %
                      (' '.join(self.args), os.path.realpath(self.dir)))
    self.stdout.write('\n')
    self.stdout.flush()

    self.shell_arg = (sys.platform == 'win32')

  def testBasic(self):
    self.subprocess.call([gclient.SVN_COMMAND] + list(self.args),
                         cwd=self.dir, shell=self.shell_arg).AndReturn(0)

    self.mox.ReplayAll()
    result = self.run_svn(self.args, self.dir)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testRaiseOnError(self):
    exception_msg = 'failed to run command: '
    self.subprocess.call([gclient.SVN_COMMAND] + list(self.args),
                         cwd=self.dir, shell=self.shell_arg).AndReturn(1)

    self.mox.ReplayAll()
    self.assertRaisesError(exception_msg + ' '.join(['svn'] + self.args),
                           self.run_svn, self.args, self.dir)
    self.mox.VerifyAll()


class TestRunSVNCommandForModule(unittest.TestCase):
  def testRunSVNCommandForModule(self):
    def MockRunSVN(args, in_directory):
      self.args = args
      self.in_directory = in_directory
      return 7

    args = Args()
    gclient.RunSVN = MockRunSVN
    result = gclient.RunSVNCommandForModule('status', 'relative/path',
                                            '/root', args)
    self.assertEquals(result, 7)
    self.assertEquals(self.args, ['status'] + args, '/root/relative/path')


class TestRunSVNCommandForClientModules(unittest.TestCase):
  def setUp(self):
    self.mox = mox.Mox()
    self.gclient = self.mox.CreateMock(gclient)
    self.root_dir = RootDir()
    self.args = Args()

    # Mock out dependencies.
    self.run_svn_command_for_client_modules = (
        lambda command, client, verbose, args:
        gclient.RunSVNCommandForClientModules(
            command, client, verbose, args,
            run_svn_command_for_module=self.gclient.RunSVNCommandForModule,
            get_all_deps=self.gclient.GetAllDeps))

  def testNoSolutions(self):
    self.gclient.GetAllDeps(
        {'root_dir': self.root_dir, 'solutions': []}, {}).AndReturn({})

    self.mox.ReplayAll()
    self.run_svn_command_for_client_modules(
        'status', {'solutions': [], 'root_dir': self.root_dir}, True,
        self.args)
    self.mox.VerifyAll()

  def testOneSolution(self):
    client = {'solutions': [{'name': 'solution_name',
                             'url': 'http://blah'}],
              'root_dir': self.root_dir}

    self.gclient.RunSVNCommandForModule('diff', 'solution_name',
                                        self.root_dir, self.args)
    self.gclient.GetAllDeps(
        client, {'solution_name': 'http://blah'}
        ).AndReturn({'dep1_key': 'd1_val', 'dep2_key': 'd2_val'})

    # Called once per dependency.
    self.gclient.RunSVNCommandForModule('diff', 'dep1_key',
                                        self.root_dir, self.args)
    self.gclient.RunSVNCommandForModule('diff', 'dep2_key',
                                        self.root_dir, self.args)

    self.mox.ReplayAll()
    self.run_svn_command_for_client_modules('diff', client, True, self.args)
    self.mox.VerifyAll()

  def testSolutionSpecifiedTwice(self):
    args = Args()
    root_dir = RootDir()
    client = {'solutions': [{'name': 'solution_name',
                             'url': 'http://blah'},
                            {'name': 'solution_name',
                             'url': 'http://foo'}],
              'root_dir': root_dir}

    self.gclient.RunSVNCommandForModule(
        'status', 'solution_name', root_dir, args)

    self.mox.ReplayAll()
    self.assertRaises(gclient.Error, self.run_svn_command_for_client_modules,
                      'status', client, True, args)
    self.mox.VerifyAll()


class TestUpdateAll(GclientTestCase):
  class Options(object):
    def __init__(self, verbose=False, force=False, revision=None):
      self.verbose = verbose
      self.force = force
      self.revision = revision

  def setUp(self):
    self.mox = mox.Mox()
    self.gclient = self.mox.CreateMock(gclient)
    self.os_path = self.mox.CreateMock(os.path)
    self.stdout = self.mox.CreateMock(sys.stdout)

    self.args = Args()
    self.root_dir = RootDir()

    result = self.update_all = (
        lambda client, options, args:
        gclient.UpdateAll(
            client, options, args,
            update_to_url=self.gclient.UpdateToURL,
            create_client_entries_file=self.gclient.CreateClientEntriesFile,
            read_client_entries_file=self.gclient.ReadClientEntriesFile,
            get_default_solution_deps=self.gclient.GetDefaultSolutionDeps,
            get_all_deps=self.gclient.GetAllDeps,
            path_exists=self.os_path.exists,
            logger=self.stdout))

  def testNoSolutions(self):
    client = {'solutions': []}
    entries = {}

    self.gclient.GetAllDeps(client, entries).AndReturn({})
    self.gclient.ReadClientEntriesFile(client).AndReturn([])
    self.gclient.CreateClientEntriesFile(client, entries)

    self.mox.ReplayAll()
    result = self.update_all(client, self.Options(), self.args)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testOneSolution(self):
    client = {'solutions':
              [{'name': 'solution_name',
                'url': 'http://lolcats'}],
              'root_dir': self.root_dir}
    entries = {'solution_name': 'http://lolcats'}
    options = self.Options()

    self.gclient.UpdateToURL('solution_name', 'http://lolcats', self.root_dir,
                             options, self.args).AndReturn(0)
    self.gclient.GetAllDeps(client, entries).AndReturn({})
    self.gclient.ReadClientEntriesFile(client).AndReturn([])
    self.gclient.CreateClientEntriesFile(client, entries)

    self.mox.ReplayAll()
    result = self.update_all(client, options, self.args)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testOneSolutionError(self):
    client = {'solutions':
              [{'name': 'solution_name',
                'url': 'http://lolcats'}],
              'root_dir': self.root_dir}
    entries = {'solution_name': 'http://lolcats'}
    options = self.Options()

    self.gclient.UpdateToURL('solution_name', 'http://lolcats', self.root_dir,
                             options, self.args).AndReturn(123)
    self.gclient.GetAllDeps(client, entries).AndReturn({})
    self.gclient.ReadClientEntriesFile(client).AndReturn([])
    self.gclient.CreateClientEntriesFile(client, entries)

    self.mox.ReplayAll()
    result = self.update_all(client, options, self.args)
    self.assertEquals(result, 123)
    self.mox.VerifyAll()

  def testSolutionSpecifiedMoreThanOnce(self):
    client = {'solutions':
              [{'name': 'solution_name',
                'url': 'http://a_url'},
               {'name': 'solution_name',
                'url': 'http://another_url'}],
              'root_dir': self.root_dir}
    options = self.Options()

    self.gclient.UpdateToURL('solution_name', 'http://a_url', self.root_dir,
                             options, self.args).AndReturn(0)

    self.mox.ReplayAll()
    self.assertRaisesError(
        'solution specified more than once',
        self.update_all, client, options, self.args)
    self.mox.VerifyAll()

  def testSyncToGivenRevisionAllSolutions(self):
    client = {'solutions':
              [{'name': 'solution_name',
                'url': 'http://lolcats@revision'}],
              'root_dir': self.root_dir}
    entries = {'solution_name': 'http://lolcats@123'}
    options = self.Options(revision='123')

    self.gclient.UpdateToURL('solution_name', 'http://lolcats@123',
                             self.root_dir, options, self.args).AndReturn(0)
    self.gclient.GetAllDeps(client, entries).AndReturn({})
    self.gclient.ReadClientEntriesFile(client).AndReturn([])
    self.gclient.CreateClientEntriesFile(client, entries)

    self.mox.ReplayAll()
    result = self.update_all(client, options, self.args)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testSyncToGivenRevisionThisSolutionOnly(self):
    client = {'solutions':
              [{'name': 'a_solution',
                'url': 'http://lolcats@change_me'},
               {'name': 'another_solution',
                'url': 'http://ytmd@keep_me'}],
              'root_dir': self.root_dir}
    entries = {'a_solution': 'http://lolcats@new_rev',
               'another_solution': 'http://ytmd@keep_me'}
    options = self.Options(revision='a_solution@new_rev')

    self.gclient.UpdateToURL('a_solution', 'http://lolcats@new_rev',
                             self.root_dir, options, self.args).AndReturn(0)
    self.gclient.UpdateToURL('another_solution', 'http://ytmd@keep_me',
                             self.root_dir, options, self.args).AndReturn(0)
    self.gclient.GetAllDeps(client, entries).AndReturn({})
    self.gclient.ReadClientEntriesFile(client).AndReturn([])
    self.gclient.CreateClientEntriesFile(client, entries)

    self.mox.ReplayAll()
    result = self.update_all(client, options, self.args)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testExplicitDep(self):
    # inputs
    solutions = [{'name': 'solution1',
                  'url': 'http://url1'},
                 {'name': 'solution2',
                  'url': 'http://url2'}]
    client = {'solutions': solutions,
              'root_dir': self.root_dir}
    deps = {'solution1': 'http://a_dependency'}
    options = self.Options()

    # expected output
    entries = {'solution1': 'http://url1',
               'solution2': 'http://url2'}
    entries_with_deps = {'solution1': 'http://a_dependency',
                         'solution2': 'http://url2'}

    self.gclient.UpdateToURL('solution1', 'http://url1', self.root_dir,
                             options, self.args).AndReturn(0)
    self.gclient.UpdateToURL('solution2', 'http://url2', self.root_dir,
                             options, self.args).AndReturn(0)
    self.gclient.GetAllDeps(client, entries).AndReturn(deps)
    self.gclient.UpdateToURL('solution1', 'http://a_dependency', self.root_dir,
                             options, self.args).AndReturn(0)
    self.gclient.ReadClientEntriesFile(client).AndReturn([])
    self.gclient.CreateClientEntriesFile(client, entries_with_deps)

    self.mox.ReplayAll()
    result = self.update_all(client, options, self.args)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testInheritedDep(self):
    # inputs
    solutions = [{'name': 'solution1',
                  'url': 'http://url1'},
                 {'name': 'solution2',
                  'url': 'http://url2'}]
    client = {'solutions': solutions,
              'root_dir': self.root_dir}

    class DummyModule(object):
      def __init__(self):
        self.module_name = 'my_module'

    deps = {'solution1': DummyModule()}
    default_solution_dep = {'solution1':
                            'http://default_solution_dep'}

    # expected output
    entries = {'solution1': 'http://url1',
               'solution2': 'http://url2'}
    entries_with_deps = {'solution1': 'http://default_solution_dep',
                         'solution2': 'http://url2'}
    options = self.Options()

    self.gclient.UpdateToURL('solution1', 'http://url1', self.root_dir,
                             options, self.args).AndReturn(0)
    self.gclient.UpdateToURL('solution2', 'http://url2', self.root_dir,
                             options, self.args).AndReturn(0)
    self.gclient.GetAllDeps(client, entries).AndReturn(deps)
    self.gclient.GetDefaultSolutionDeps(
        client, 'my_module').AndReturn(default_solution_dep)
    self.gclient.UpdateToURL('solution1', 'http://default_solution_dep',
                             self.root_dir, options, self.args).AndReturn(0)
    self.gclient.ReadClientEntriesFile(client).AndReturn([])
    self.gclient.CreateClientEntriesFile(client, entries_with_deps)

    self.mox.ReplayAll()
    result = self.update_all(client, options, self.args)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testOrphanedEntry(self):
    client = {'solutions':
              [{'name': 'solution_name',
                'url': 'http://lolcats'}],
              'root_dir': self.root_dir}
    entries = {'solution_name': 'http://lolcats'}
    prev_entries = ['solution_name',
                    'solution_path_doesnt_exist',
                    'solution_path_exists']
    entries_with_orphans = entries.copy()
    entries_with_orphans['solution_path_exists'] = None
    options = self.Options()

    self.gclient.UpdateToURL('solution_name', 'http://lolcats', self.root_dir,
                             options, self.args).AndReturn(0)
    self.gclient.GetAllDeps(client, entries).AndReturn({})
    self.gclient.ReadClientEntriesFile(client).AndReturn(prev_entries)

    # We don't use os.path.join() to construct these path names because
    # Subversion canonicalizes everything to normal / path separators.
    self.os_path.exists(
        self.root_dir + '/solution_path_doesnt_exist'
        ).AndReturn(False)
    self.os_path.exists(self.root_dir + '/solution_path_exists').AndReturn(True)

    print >>self.stdout, ('\nWARNING: "%s" is no longer part of this client.  '
                          'It is recommended that you manually remove it.\n'
                         ) % 'solution_path_exists'
    self.gclient.CreateClientEntriesFile(client, entries_with_orphans)

    self.mox.ReplayAll()
    result = self.update_all(client, options, self.args)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testMultipleSolutionError(self):
    # inputs
    solutions = [{'name': 'solution1',
                  'url': 'http://url1'},
                 {'name': 'solution2',
                  'url': 'http://url2'}]
    client = {'solutions': solutions,
              'root_dir': self.root_dir}
    deps = {'solution1': 'http://a_dependency'}
    options = self.Options()

    # expected output
    entries = {'solution1': 'http://url1',
               'solution2': 'http://url2'}
    entries_with_deps = {'solution1': 'http://a_dependency',
                         'solution2': 'http://url2'}

    self.gclient.UpdateToURL('solution1', 'http://url1', self.root_dir,
                             options, self.args).AndReturn(0)
    self.gclient.UpdateToURL('solution2', 'http://url2', self.root_dir,
                             options, self.args).AndReturn(789)
    self.gclient.GetAllDeps(client, entries).AndReturn(deps)
    self.gclient.UpdateToURL('solution1', 'http://a_dependency', self.root_dir,
                             options, self.args).AndReturn(678)
    self.gclient.ReadClientEntriesFile(client).AndReturn([])
    self.gclient.CreateClientEntriesFile(client, entries_with_deps)

    self.mox.ReplayAll()
    result = self.update_all(client, options, self.args)
    self.assertEquals(result, 789)
    self.mox.VerifyAll()


class TestUpdateToURL(GclientTestCase):
  class Options(object):
    def __init__(self, verbose=False, force=False, relocate=False):
      self.verbose = verbose
      self.force = force
      self.relocate = relocate

  def setUp(self):
    self.mox = mox.Mox()
    self.gclient = self.mox.CreateMock(gclient)
    self.os_path = self.mox.CreateMock(os.path)
    self.stdout = self.mox.CreateMock(sys.stdout)

    # Common fake data used by the individual tests.
    self.rel = 'relative_path'
    self.root = 'root_directory'
    self.rootpath = os.path.join(self.root, self.rel)
    self.url_rev = 'http://svn/trunk@123'
    self.url, self.rev = self.url_rev.split('@')
    self.uuid = 'a-fake-UUID-value'
    self.root_url = 'http://svn'
    self.svn_info = {'URL': self.url,
                     'Repository Root': self.root_url,
                     'Repository UUID': self.uuid,
                     'Revision': self.rev,
                    }

    self.update_to_url = (
        lambda relpath, svnurl, root_dir, options, args:
        gclient.UpdateToURL(
            relpath, svnurl, root_dir, options, args,
            output_stream=self.stdout,
            path_exists=self.os_path.exists,
            capture_svn_info=self.gclient.CaptureSVNInfo,
            run_svn=self.gclient.RunSVN))

  def testSimpleCall(self):
    self.os_path.exists(self.rootpath).AndReturn(False)
    self.gclient.RunSVN(['checkout', self.url_rev, self.rel],
                        self.root).AndReturn(0)

    self.mox.ReplayAll()
    result = self.update_to_url(self.rel, self.url_rev, self.root,
                                self.Options(), None)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testCallWithArguments(self):
    self.os_path.exists(self.rootpath).AndReturn(False)
    self.gclient.RunSVN(['checkout', self.url_rev, self.rel, 'arg1', 'arg2'],
                        self.root).AndReturn(7)

    self.mox.ReplayAll()
    result = self.update_to_url(self.rel, self.url_rev, self.root,
                                self.Options(), ['arg1', 'arg2'])
    self.assertEquals(result, 7)
    self.mox.VerifyAll()

  def testRelativeError(self):
    exception_msg = ("Couldn't get URL for relative path: "
                     "'%s' under root directory: %s.\n"
                     '\tSVN URL was:\n\t\t%s\n'
                     '\tInfo dict was:\n\t\t{}'
                     % (self.rel, self.root, self.url_rev))

    # Have CaptureSVNInfo() simulate an "svn info" error by returning
    # an empty dictionary.
    self.os_path.exists(self.rootpath).AndReturn(True)
    self.gclient.CaptureSVNInfo(self.rel, self.root, False).AndReturn({})

    self.mox.ReplayAll()
    self.assertRaisesError(
        exception_msg, self.update_to_url, self.rel, self.url_rev, self.root,
        self.Options(), None)
    self.mox.VerifyAll()

  def testSwitch(self):
    url = 'svn://new_svn/trunk'

    self.os_path.exists(self.rootpath).AndReturn(True)
    self.gclient.CaptureSVNInfo(
        self.rel, self.root, False).AndReturn(self.svn_info)
    self.gclient.CaptureSVNInfo(url, self.root, False).AndReturn(self.svn_info)
    self.gclient.RunSVN(['switch', url, self.rel], self.root).AndReturn(3)

    self.mox.ReplayAll()
    result = self.update_to_url(self.rel, url, self.root, self.Options(), None)
    self.assertEquals(result, 3)
    self.mox.VerifyAll()

  def testSwitchRelocateBranch(self):
    url_rev = 'svn://new_svn/branches/foo@789'
    url, rev = url_rev.split('@')
    root_url = 'svn://new_svn'
    info = {'URL': url,
            'Repository Root': root_url,
            'Repository UUID': self.uuid,
            'Revision': rev,
           }

    self.os_path.exists(self.rootpath).AndReturn(True)
    self.gclient.CaptureSVNInfo(
        self.rel, self.root, False).AndReturn(self.svn_info)
    self.gclient.CaptureSVNInfo(url_rev, self.root, False).AndReturn(info)
    self.gclient.RunSVN(['switch', '--relocate', self.root_url, root_url,
                         self.rel], self.root).AndReturn(0)
    self.gclient.RunSVN(['switch', '-r', rev, url, self.rel],
                        self.root).AndReturn(17)

    self.mox.ReplayAll()
    result = self.update_to_url(self.rel, url_rev, self.root,
                                self.Options(relocate=True), None)
    self.assertEquals(result, 17)
    self.mox.VerifyAll()

  def testSwitchRelocateTrunk(self):
    url_rev = 'svn://new_svn/trunk@789'
    url, rev = url_rev.split('@')
    root_url = 'svn://new_svn'
    info = {'URL': url,
            'Repository Root': root_url,
            'Repository UUID': self.uuid,
            'Revision': rev,
           }

    self.os_path.exists(self.rootpath).AndReturn(True)
    self.gclient.CaptureSVNInfo(
        self.rel, self.root, False).AndReturn(self.svn_info)
    self.gclient.CaptureSVNInfo(url_rev, self.root, False).AndReturn(info)
    self.gclient.RunSVN(['switch', '--relocate', self.root_url, root_url,
                         self.rel], self.root).AndReturn(0)
    self.gclient.RunSVN(['update', '-r', rev], self.rootpath).AndReturn(123)

    self.mox.ReplayAll()
    result = self.update_to_url(self.rel, url_rev, self.root,
                                self.Options(relocate=True), None)
    self.assertEquals(result, 123)
    self.mox.VerifyAll()

  def testSwitchRelocateDifferentUUID(self):
    url_rev = 'svn://new_svn/trunk@789'
    url, rev = url_rev.split('@')
    info = {'URL': url,
            'Repository Root': 'svn://new_svn',
            'Repository UUID': 'a-different-UUID-value',
            'Revision': rev,
           }

    expected_message = ('Skipping update to %s;\n'
                        '\tcan not relocate to URL with different Repository '
                        'UUID.\n' % (url_rev))

    self.os_path.exists(self.rootpath).AndReturn(True)
    self.gclient.CaptureSVNInfo(
        self.rel, self.root, False).AndReturn(self.svn_info)
    self.gclient.CaptureSVNInfo(url_rev, self.root, False).AndReturn(info)
    self.stdout.write(expected_message)
    self.stdout.write('\n')

    self.mox.ReplayAll()
    self.update_to_url(self.rel, url_rev, self.root, self.Options(), None)
    self.mox.VerifyAll()

  def testSwitchNoRelocateOption(self):
    url_rev = 'svn://new_svn/trunk@789'
    url, rev = url_rev.split('@')
    info = {'URL': url,
            'Repository Root': 'svn://new_svn',
            'Repository UUID': self.uuid,
            'Revision': rev,
           }

    expected_message = ('Skipping update to %s;\n'
                        '\tuse the --relocate option to switch\n'
                        '\tfrom %s\n'
                        '\tto   %s.\n'
                        % (url_rev, self.url, url))

    self.os_path.exists(self.rootpath).AndReturn(True)
    self.gclient.CaptureSVNInfo(
        self.rel, self.root, False).AndReturn(self.svn_info)
    self.gclient.CaptureSVNInfo(url_rev, self.root, False).AndReturn(info)
    self.stdout.write(expected_message)
    self.stdout.write('\n')

    self.mox.ReplayAll()
    self.update_to_url(self.rel, url_rev, self.root, self.Options(), None)
    self.mox.VerifyAll()

  def testSwitchRevision(self):
    url_rev = 'svn://new_svn/trunk@789'
    url, rev = url_rev.split('@')

    self.os_path.exists(self.rootpath).AndReturn(True)
    self.gclient.CaptureSVNInfo(
        self.rel, self.root, False).AndReturn(self.svn_info)
    self.gclient.CaptureSVNInfo(
        url_rev, self.root, False).AndReturn(self.svn_info)
    self.gclient.RunSVN(['switch', '-r', rev, url, self.rel],
                        self.root).AndReturn(234)

    self.mox.ReplayAll()
    result = self.update_to_url(self.rel, url_rev, self.root,
                                self.Options(), None)
    self.assertEquals(result, 234)
    self.mox.VerifyAll()

  def testUpdate(self):
    self.os_path.exists(self.rootpath).AndReturn(True)
    self.gclient.CaptureSVNInfo(
        self.rel, self.root, False).AndReturn(self.svn_info)
    self.gclient.RunSVN(['update'], self.rootpath).AndReturn(345)

    self.mox.ReplayAll()
    result = self.update_to_url(self.rel, self.url, self.root,
                                self.Options(), None)
    self.assertEquals(result, 345)
    self.mox.VerifyAll()

  def testMatchingRevision(self):
    self.os_path.exists(self.rootpath).AndReturn(True)
    self.gclient.CaptureSVNInfo(
        self.rel, self.root, False).AndReturn(self.svn_info)

    self.mox.ReplayAll()
    self.update_to_url(self.rel, self.url_rev, self.root, self.Options(), None)
    self.mox.VerifyAll()

  def testMatchingRevisionForce(self):
    self.os_path.exists(self.rootpath).AndReturn(True)
    self.gclient.CaptureSVNInfo(
        self.rel, self.root, False).AndReturn(self.svn_info)
    self.gclient.RunSVN(['update', '-r', '123'], self.rootpath).AndReturn(456)

    self.mox.ReplayAll()
    result = self.update_to_url(self.rel, self.url_rev, self.root,
                                self.Options(force=True), None)
    self.assertEquals(result, 456)
    self.mox.VerifyAll()

  def testMatchingRevisionVerbose(self):
    self.os_path.exists(self.rootpath).AndReturn(True)
    self.gclient.CaptureSVNInfo(
        self.rel, self.root, True).AndReturn(self.svn_info)
    self.stdout.write('\n_____ %(URL)s at %(Revision)s' % self.svn_info)
    self.stdout.write('\n')

    self.mox.ReplayAll()
    self.update_to_url(self.rel, self.url_rev, self.root,
                       self.Options(verbose=True), None)
    self.mox.VerifyAll()


class TestDoConfig(GclientTestCase):
  class Options(object):
    def __init__(self, a_spec):
      self.spec = a_spec

  def setUp(self):
    self.mox = mox.Mox()
    self.os_path = self.mox.CreateMock(os.path)
    self.gclient = self.mox.CreateMock(gclient)

    # Call the function to be tested, mocking out all the dependencies.
    self.do_config = (
        lambda options, args, CLIENT_FILE=gclient.CLIENT_FILE: gclient.DoConfig(
            options, args, CLIENT_FILE,
            path_exists=self.os_path.exists,
            create_client_file=self.gclient.CreateClientFile,
            create_client_file_from_text=self.gclient.CreateClientFileFromText))

  def testMissingArgument(self):
    exception_msg = "required argument missing; see 'gclient help config'"

    self.mox.ReplayAll()
    self.assertRaisesError(
        exception_msg, self.do_config, TestDoConfig.Options(None), ())
    self.mox.VerifyAll()

  def testExistingClientFile(self):
    exception_msg = '.gclient file already exists in the current directory'
    self.os_path.exists('an_existing_client_file').AndReturn(True)

    self.mox.ReplayAll()
    self.assertRaisesError(
        exception_msg, self.do_config, TestDoConfig.Options(None), (1,),
        CLIENT_FILE='an_existing_client_file')
    self.mox.VerifyAll()

  def testFromText(self):
    self.os_path.exists('a_client_file').AndReturn(False)
    self.gclient.CreateClientFileFromText('a_client_file')

    self.mox.ReplayAll()
    self.do_config(TestDoConfig.Options('a_client_file'), (),
                   CLIENT_FILE='a_client_file')
    self.mox.VerifyAll()

  def testCreateClientFile(self):
    self.os_path.exists('new_client_file').AndReturn(False)
    self.gclient.CreateClientFile('the_name', 'http://svn/url/the_name')

    self.mox.ReplayAll()
    self.do_config(TestDoConfig.Options(None),
                   ('http://svn/url/the_name', 'other', 'args', 'ignored'),
                   'new_client_file')
    self.mox.VerifyAll()


class TestDoHelp(GclientTestCase):
  def setUp(self):
    self.mox = mox.Mox()
    self.stdout = self.mox.CreateMock(sys.stdout)
    self.gclient = self.mox.CreateMock(gclient)

    # Call the function to be tested, mocking out all the dependencies.
    self.do_help = lambda options, args: gclient.DoHelp(
        options, args, output_stream=self.stdout)

  def testGetUsage(self):
    print >> self.stdout, gclient.COMMAND_USAGE_TEXT['config']

    self.mox.ReplayAll()
    self.do_help(None, ('config',))
    self.mox.VerifyAll()

  def testTooManyArgs(self):
    self.mox.ReplayAll()
    self.assertRaisesError("unknown subcommand; see 'gclient help'",
                           self.do_help, None, ('config', 'another argument'))
    self.mox.VerifyAll()

  def testUnknownSubcommand(self):
    self.mox.ReplayAll()
    self.assertRaisesError("unknown subcommand; see 'gclient help'",
                           self.do_help, None, ('xyzzy',))
    self.mox.VerifyAll()


class TestDoStatus(GclientTestCase):
  class Options(object):
    def __init__(self):
      self.verbose = random.choice((True, False))

  def setUp(self):
    self.mox = mox.Mox()
    self.gclient = self.mox.CreateMock(gclient)
    self.args = Args()

    # Call the function to be tested, mocking out all the dependencies.
    self.do_status = (
        lambda options, args:
        gclient.DoStatus(options, args,
                         self.gclient.GetClient,
                         self.gclient.RunSVNCommandForClientModules))

  def testGoodClient(self):
    client = {'client': 'my client'}

    options = self.Options()
    self.gclient.GetClient().AndReturn(client)
    self.gclient.RunSVNCommandForClientModules('status', client,
                                               options.verbose,
                                               self.args).AndReturn(0)
    self.mox.ReplayAll()
    result = self.do_status(options, self.args)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testError(self):
    client = {'client': 'my client'}

    options = self.Options()
    self.gclient.GetClient().AndReturn(client)
    self.gclient.RunSVNCommandForClientModules('status', client,
                                               options.verbose,
                                               self.args).AndReturn(333)
    self.mox.ReplayAll()
    result = self.do_status(options, self.args)
    self.assertEquals(result, 333)
    self.mox.VerifyAll()

  def testClientNotConfigured(self):
    self.gclient.GetClient().AndReturn({})

    self.mox.ReplayAll()
    self.assertRaisesError("client not configured; see 'gclient config'",
                           self.do_status, self.Options(), Args())
    self.mox.VerifyAll()


class TestDoUpdate(GclientTestCase):
  class Options(object):
    def __init__(self):
      self.verbose = False
      self.force = random.choice((True, False))
      self.revision = random.randint(0, 10000000)

  def setUp(self):
    self.mox = mox.Mox()
    self.gclient = self.mox.CreateMock(gclient)

  def testBasic(self):
    client = {'client': 'my client', 'source': 'contents of the source file'}
    options = TestDoUpdate.Options()
    args = Args()
    self.gclient.GetClient().AndReturn(client)
    self.gclient.UpdateAll(client, options, args).AndReturn(0)

    self.mox.ReplayAll()
    result = gclient.DoUpdate(options, args, self.gclient.GetClient,
                              self.gclient.UpdateAll)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testError(self):
    client = {'client': 'my client', 'source': 'contents of the source file'}
    options = TestDoUpdate.Options()
    args = Args()
    self.gclient.GetClient().AndReturn(client)
    self.gclient.UpdateAll(client, options, args).AndReturn(555)

    self.mox.ReplayAll()
    result = gclient.DoUpdate(options, args, self.gclient.GetClient,
                              self.gclient.UpdateAll)
    self.assertEquals(result, 555)
    self.mox.VerifyAll()

  def testBadClient(self):
    client = {}
    options = TestDoUpdate.Options()
    args = Args()
    self.gclient.GetClient().AndReturn(client)

    self.mox.ReplayAll()
    self.assertRaisesError(
        "client not configured; see 'gclient config'",
        gclient.DoUpdate, options, args, self.gclient.GetClient)
    self.mox.VerifyAll()

  def testVerbose(self):
    client = {'client': 'my client', 'source': 'contents of the source file'}
    options = TestDoUpdate.Options()
    options.verbose = True
    args = Args()
    self.stdout = self.mox.CreateMock(sys.stdout)
    self.gclient.GetClient().AndReturn(client)

    print >>self.stdout, client['source']
    self.gclient.UpdateAll(client, options, args).AndReturn(0)

    self.mox.ReplayAll()
    result = gclient.DoUpdate(options, args, self.gclient.GetClient,
                              self.gclient.UpdateAll, self.stdout)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()


class TestDoDiff(GclientTestCase):
  # TODO(sng): pull out common stuff with TestDoUpdate

  class Options(object):
    def __init__(self):
      self.verbose = False
      self.force = random.choice((True, False))
      self.revision = random.randint(0, 10000000)

  def setUp(self):
    self.mox = mox.Mox()
    self.gclient = self.mox.CreateMock(gclient)

  def testBasic(self):
    client = {'client': 'my client', 'source': 'contents of the source file'}
    options = TestDoDiff.Options()
    args = Args()
    self.gclient.GetClient().AndReturn(client)
    self.gclient.RunSVNCommandForClientModules(
        'diff', client, options.verbose, args).AndReturn(0)

    self.mox.ReplayAll()
    result = gclient.DoDiff(options, args, self.gclient.GetClient,
                            self.gclient.RunSVNCommandForClientModules)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testError(self):
    client = {'client': 'my client', 'source': 'contents of the source file'}
    options = TestDoDiff.Options()
    args = Args()
    self.gclient.GetClient().AndReturn(client)
    self.gclient.RunSVNCommandForClientModules(
        'diff', client, options.verbose, args).AndReturn(444)

    self.mox.ReplayAll()
    result = gclient.DoDiff(options, args, self.gclient.GetClient,
                            self.gclient.RunSVNCommandForClientModules)
    self.assertEquals(result, 444)
    self.mox.VerifyAll()

  def testBadClient(self):
    client = {}
    options = TestDoDiff.Options()
    args = Args()
    self.gclient.GetClient().AndReturn(client)

    self.mox.ReplayAll()
    self.assertRaisesError(
        "client not configured; see 'gclient config'",
        gclient.DoDiff, options, args, self.gclient.GetClient)
    self.mox.VerifyAll()

  def testVerbose(self):
    client = {'client': 'my client', 'source': 'contents of the source file'}
    options = TestDoDiff.Options()
    options.verbose = True
    args = Args()
    self.stdout = self.mox.CreateMock(sys.stdout)
    self.gclient.GetClient().AndReturn(client)

    print >>self.stdout, client['source']
    self.gclient.RunSVNCommandForClientModules(
        'diff', client, options.verbose, args)

    self.mox.ReplayAll()
    gclient.DoDiff(
        options, args,
        self.gclient.GetClient,
        run_svn_command_for_client_modules=
        self.gclient.RunSVNCommandForClientModules,
        output_stream=self.stdout)
    self.mox.VerifyAll()


class TestDoRevert(GclientTestCase):
  # TODO(sng): pull out common stuff with TestDoUpdate

  class Options(object):
    def __init__(self):
      self.verbose = False

  def setUp(self):
    self.mox = mox.Mox()
    self.gclient = self.mox.CreateMock(gclient)

  def testBasic(self):
    client = {'client': 'my client', 'source': 'contents of the source file'}
    options = TestDoRevert.Options()
    args = Args()
    self.gclient.GetClient().AndReturn(client)
    self.gclient.RunSVNCommandForClientModules(
        'revert', client, options.verbose, args).AndReturn(0)

    self.mox.ReplayAll()
    result = gclient.DoRevert(options, args, self.gclient.GetClient,
                              self.gclient.RunSVNCommandForClientModules)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testError(self):
    client = {'client': 'my client', 'source': 'contents of the source file'}
    options = TestDoRevert.Options()
    args = Args()
    self.gclient.GetClient().AndReturn(client)
    self.gclient.RunSVNCommandForClientModules(
        'revert', client, options.verbose, args).AndReturn(444)

    self.mox.ReplayAll()
    result = gclient.DoRevert(options, args, self.gclient.GetClient,
                              self.gclient.RunSVNCommandForClientModules)
    self.assertEquals(result, 444)
    self.mox.VerifyAll()

  def testBadClient(self):
    client = {}
    options = TestDoRevert.Options()
    args = Args()
    self.gclient.GetClient().AndReturn(client)

    self.mox.ReplayAll()
    self.assertRaisesError(
        "client not configured; see 'gclient config'",
        gclient.DoRevert, options, args, self.gclient.GetClient)
    self.mox.VerifyAll()


class TestDispatchCommand(GclientTestCase):
  class Options(object):
    def __init__(self):
      self.verbose = False
      self.force = random.choice((True, False))
      self.revision = random.randint(0, 10000000)

  def setUp(self):
    self.mox = mox.Mox()
    self.gclient = self.mox.CreateMock(gclient)
    self.options = TestDispatchCommand.Options()
    self.args = Args()

  def testBasic(self):
    self.gclient.DoDiff(self.options, self.args).AndReturn(0)
    self.gclient.DoConfig(self.options, self.args).AndReturn(0)

    self.mox.ReplayAll()
    # Declare after ReplayAll so mox doesn't think these are expectations.
    command_map = {
        'config': self.gclient.DoConfig,
        'diff': self.gclient.DoDiff,
        }
    result = gclient.DispatchCommand('diff', self.options, self.args,
                                     command_map)
    self.assertEquals(result, 0)
    result = gclient.DispatchCommand('config', self.options, self.args,
                                     command_map)
    self.assertEquals(result, 0)
    self.mox.VerifyAll()

  def testError(self):
    self.gclient.DoDiff(self.options, self.args).AndReturn(777)
    self.gclient.DoConfig(self.options, self.args).AndReturn(888)

    self.mox.ReplayAll()
    # Declare after ReplayAll so mox doesn't think these are expectations.
    command_map = {
        'config': self.gclient.DoConfig,
        'diff': self.gclient.DoDiff,
        }
    result = gclient.DispatchCommand('diff', self.options, self.args,
                                     command_map)
    self.assertEquals(result, 777)
    result = gclient.DispatchCommand('config', self.options, self.args,
                                     command_map)
    self.assertEquals(result, 888)
    self.mox.VerifyAll()

  def testUnknownCommand(self):
    self.mox.ReplayAll()
    self.assertRaisesError(
        "unknown subcommand; see 'gclient help'",
        gclient.DispatchCommand, 'speak', self.options, self.args,
        {})
    self.mox.VerifyAll()


class TestGetDefaultSolutionDeps(GclientTestCase):
  def setUp(self):
    self.mox = mox.Mox()
    self.gclient = self.mox.CreateMock(gclient)
    self.stdout = self.mox.CreateMock(sys.stdout)

    # Have to monkey-patch execfile since it's a built-in
    # and pymox can't handle that.
    self.save_execfile = __builtin__.execfile

    self.get_default_solution_deps = (
        lambda client, solution_name, platform=None,
        execf=self.save_execfile:
        gclient.GetDefaultSolutionDeps(client, solution_name, platform,
                                       execf=execf,
                                       logger=self.stdout))

  def tearDown(self):
    __builtin__.execfile = self.save_execfile

  def testNoDepsFile(self):
    client = {'root_dir': '/my/dir'}

    def MockExecFile(fname, scope):
      raise IOError('No such file or directory: %s' % repr(fname))

    print >>self.stdout, (
        '\nWARNING: DEPS file not found for solution: my_solution\n')
    self.mox.ReplayAll()
    result = self.get_default_solution_deps(client, 'my_solution',
                                            execf=MockExecFile)
    self.mox.VerifyAll()
    self.assertEqual(result, {})

  def testSimpleDepsFile(self):
    client = {'root_dir': '/my/dir'}

    deps = {'component1': 'http:/url1',
            'component2': 'http:/url2'}

    def MockExecFile(fname, scope):
      self.my_execfile_fname = fname
      scope.update({'deps': deps})

    self.mox.ReplayAll()
    result = self.get_default_solution_deps(client, 'my_solution',
                                            execf=MockExecFile)
    self.mox.VerifyAll()
    self.assertEqual(result, deps)

  def testDepsOs(self):
    client = {'root_dir': '/my/dir'}

    deps = {'component1': 'http:/url1'}
    deps_os = {'win': {'component2': 'http:/url2'},
               'mac': {'component3': 'http:/url3'},
               'unix': {'component4': 'http:/url4'},
              }

    def MockExecFile(fname, scope):
      self.my_execfile_fname = fname
      scope.update({'deps': deps.copy(), 'deps_os': deps_os.copy()})

    self.mox.ReplayAll()
    result = self.get_default_solution_deps(client, 'my_solution',
                                            platform='win',
                                            execf=MockExecFile)
    self.mox.VerifyAll()
    self.assertEqual(result, {'component1': 'http:/url1',
                              'component2': 'http:/url2',
                             })

    result = self.get_default_solution_deps(client, 'my_solution',
                                            platform='win32',
                                            execf=MockExecFile)
    self.assertEqual(result, {'component1': 'http:/url1',
                              'component2': 'http:/url2',
                             })

    result = self.get_default_solution_deps(client, 'my_solution',
                                            platform='mac',
                                            execf=MockExecFile)
    self.assertEqual(result, {'component1': 'http:/url1',
                              'component3': 'http:/url3',
                             })

    result = self.get_default_solution_deps(client, 'my_solution',
                                            platform='darwin',
                                            execf=MockExecFile)
    self.assertEqual(result, {'component1': 'http:/url1',
                              'component3': 'http:/url3',
                             })

    result = self.get_default_solution_deps(client, 'my_solution',
                                            platform='unix',
                                            execf=MockExecFile)
    self.assertEqual(result, {'component1': 'http:/url1',
                              'component4': 'http:/url4',
                             })

    result = self.get_default_solution_deps(client, 'my_solution',
                                            platform='linux2',
                                            execf=MockExecFile)
    self.assertEqual(result, {'component1': 'http:/url1',
                              'component4': 'http:/url4',
                             })

    result = self.get_default_solution_deps(client, 'my_solution',
                                            platform='unrecognized',
                                            execf=MockExecFile)
    self.assertEqual(result, {'component1': 'http:/url1',
                              'component4': 'http:/url4',
                             })


class TestGetAllDeps(GclientTestCase):
  def setUp(self):
    self.mox = mox.Mox()
    self.gclient = self.mox.CreateMock(gclient)
    self.get_all_deps = (
        lambda client, solution_urls:
        gclient.GetAllDeps(
            client, solution_urls,
            get_default_solution_deps=self.gclient.GetDefaultSolutionDeps,
            capture_svn_info=self.gclient.CaptureSVNInfo))

  def testEmptyDeps(self):
    solutions = [{'name': 'solution1',
                  'url': 'http://solution1'},
                 {'name': 'solution2',
                  'url': 'http://solution2'},
                ]
    client = {'solutions': solutions}

    self.gclient.GetDefaultSolutionDeps(client, 'solution1').AndReturn({})
    self.gclient.GetDefaultSolutionDeps(client, 'solution2').AndReturn({})
    self.mox.ReplayAll()
    result = self.get_all_deps(client, {})
    self.mox.VerifyAll()
    self.assertEqual(result, {})

  def testActualDeps(self):
    solutions = [{'name': 'solution1',
                  'url': 'http://solution1'},
                 {'name': 'solution2',
                  'url': 'http://solution2'},
                ]
    client = {'solutions': solutions}

    deps1 = {'dep1a': 'http://url1a', 'dep1b': 'http://url1b'}
    deps2 = {'dep2a': 'http://url2a', 'dep2b': 'http://url2b'}

    expected_result = {}
    expected_result.update(deps1)
    expected_result.update(deps2)

    self.gclient.GetDefaultSolutionDeps(client, 'solution1').AndReturn(deps1)
    self.gclient.GetDefaultSolutionDeps(client, 'solution2').AndReturn(deps2)
    self.mox.ReplayAll()
    result = self.get_all_deps(client, {})
    self.mox.VerifyAll()
    self.assertEqual(result, expected_result)

  def testCustomDeps(self):
    solutions = [{'name': 'solution1',
                  'url': 'http://solution1',
                  'custom_deps': {'dep1a': 'http://custom_dep_1a'},
                 },
                 {'name': 'solution2',
                  'url': 'http://solution2',
                  'custom_deps': {'dep2a': None,
                                  'dep2b': 'http://custom_dep_2b'},
                 },
                ]
    client = {'solutions': solutions}

    deps1 = {'dep1a': 'http://url1a', 'dep1b': 'http://url1b'}
    deps2 = {'dep2a': 'http://url2a', 'dep2b': 'http://url2b'}

    expected_result = {
        'dep1a': 'http://custom_dep_1a',
        'dep1b': 'http://url1b',
        'dep2b': 'http://custom_dep_2b',
    }

    self.gclient.GetDefaultSolutionDeps(client, 'solution1').AndReturn(deps1)
    self.gclient.GetDefaultSolutionDeps(client, 'solution2').AndReturn(deps2)
    self.mox.ReplayAll()
    result = self.get_all_deps(client, {})
    self.mox.VerifyAll()
    self.assertEqual(result, expected_result)

  def testRelativeDeps(self):
    root_url = 'http://url1'
    solutions = [{'name': 'solution1',
                  'url': root_url + '/solution1'}]
    client = {'solutions': solutions,
              'root_dir': RootDir()}
    deps = {'component1': 'http://an/absolute/url/path',
            'component2': '/a/relative/path'}
    svn_info = {'Repository Root': root_url}

    expected_result = deps.copy()
    expected_result['component2'] = root_url + deps['component2']

    self.gclient.GetDefaultSolutionDeps(client, 'solution1').AndReturn(deps)
    self.gclient.CaptureSVNInfo('http://url1/solution1', client['root_dir'],
                                False).AndReturn(svn_info)
    self.mox.ReplayAll()
    result = self.get_all_deps(client, {})
    self.mox.VerifyAll()
    self.assertEqual(result, expected_result)

  def testRelativeDepsError(self):
    solutions = [{'name': 'solution1',
                  'url': '/http://url1/solution1'}]
    client = {'solutions': solutions}
    deps = {'component1': 'a/bad/relative/path'}

    self.gclient.GetDefaultSolutionDeps(client, 'solution1').AndReturn(deps)
    self.mox.ReplayAll()
    self.assertRaisesError(
        'relative DEPS entry \"component1\" must begin with a slash',
        self.get_all_deps, client, {})
    self.mox.VerifyAll()

  def testConflictingSolutions(self):
    solutions = [{'name': 'solution1',
                  'url': 'http://solution1',
                 },
                 {'name': 'solution2',
                  'url': 'http://solution2',
                 },
                ]
    client = {'solutions': solutions}

    deps1 = {'conflict': 'http://url1'}
    deps2 = {'conflict': 'http://url2'}

    self.gclient.GetDefaultSolutionDeps(client, 'solution1').AndReturn(deps1)
    self.gclient.GetDefaultSolutionDeps(client, 'solution2').AndReturn(deps2)
    self.mox.ReplayAll()
    self.assertRaisesError(
        'solutions have conflicting versions of dependency "conflict"',
        self.get_all_deps, client, {})
    self.mox.VerifyAll()

  def testConflictingSpecified(self):
    solutions = [{'name': 'solution1',
                  'url': 'http://solution1',
                 },
                ]
    client = {'solutions': solutions}

    deps1 = {'conflict': 'http://url1'}

    self.gclient.GetDefaultSolutionDeps(client, 'solution1').AndReturn(deps1)
    self.mox.ReplayAll()
    self.assertRaisesError(
        'dependency "conflict" conflicts with specified solution',
        self.get_all_deps, client, {'conflict': 'http://url2'})
    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
