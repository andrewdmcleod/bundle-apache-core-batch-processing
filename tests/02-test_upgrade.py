#!/usr/bin/env python3

import os
import unittest

import yaml
import amulet


class TestBundle(unittest.TestCase):
    bundle_file = os.path.join(os.path.dirname(__file__), '..', 'bundle-ha.yaml')

    @classmethod
    def setUpClass(cls):
        # classmethod inheritance doesn't work quite right with
        # setUpClass / tearDownClass, so subclasses have to manually call this
        cls.d = amulet.Deployment(series='trusty')
        with open(cls.bundle_file) as f:
            bun = f.read()
        bundle = yaml.safe_load(bun)
        cls.d.load(bundle)
        cls.d.setup(timeout=1800)
        cls.d.sentry.wait_for_messages({'namenode': {'Ready (3 DataNodes, active, with automatic fail-over)'}}, timeout=1800)
        cls.d.sentry.wait_for_messages({'namenode': {'Ready (3 DataNodes, standby, with automatic fail-over)'}}, timeout=1800)
        cls.hdfs_a = cls.d.sentry['namenode'][0]
        cls.hdfs_b = cls.d.sentry['namenode'][1]
        cls.yarn = cls.d.sentry['resourcemanager'][0]
        cls.slave = cls.d.sentry['slave'][0]
        cls.client = cls.d.sentry['client'][0]

    def _hdfs_write_file(self):
        test_steps = [
            ('create_file',     "su ubuntu -c 'echo hi > /tmp/testfile'"),
            ('write_file',      "su ubuntu -c 'hdfs dfs -put /tmp/testfile'"),
        ]
        for name, step in test_steps:
            output, retcode = self.slave.run(step)
            assert retcode == 0, "{} FAILED:\n{}".format(name, output)

    def _hdfs_read_file(self):
        output, retcode = self.slave.run("su ubuntu -c 'hdfs dfs -cat testfile'")
        assert retcode == 0, "HDFS READ FILE FAILED:\n{}".format(output)

    def test_create_file(self):
        self._hdfs_write_file()
        self._hdfs_read_file()

    def test_prepare(self):
        """
        Run prepare action and make sure it is successful.
        """
        version = '2.7.2'
        self.d.configure('namenode', {'hadoop_version': version})
        self.d.configure('slave', {'hadoop_version': version})
        self.d.configure('resourcemanager', {'hadoop_version': version})
        id = self.d.action_do('namenode/0', 'hadoop-upgrade', {'version': version, 'prepare': 'true'})
        self.assertEqual({'result': 'Upgrade image prepared - proceed with rolling upgrade'}, self.d.action_fetch(id))
        id = self.d.action_do('namenode/0', 'hadoop-upgrade', {'version': version, 'query': 'true'})
        self.assertEqual({'result': 'Upgrade prepared'}, self.d.action_fetch(id))

    def test_upgrade(self):
        """
        Test upgrade to 2.7.2
        """
        version = '2.7.2'
        #for unit_data in self.d.sentry['namenode']:
        #unit_names = [i.info['namenode'] for i in self.d.sentry['namenode']]
        #for unit in self.d.sentry['namenode']:
        id = self.d.action_do('namenode/0', 'hadoop-upgrade', {'version': version})
        self.assertEqual({'result': 'complete'}, self.d.action_fetch(id))
        id = self.d.action_do('namenode/1', 'hadoop-upgrade', {'version': version})
        self.assertEqual({'result': 'complete'}, self.d.action_fetch(id))

        #for sentry in self.d.sentry['slave']:
        id = self.d.action_do('slave/0', 'hadoop-upgrade', {'version': version})
        self.assertEqual({'result': 'complete'}, self.d.action_fetch(id))
        id = self.d.action_do('slave/1', 'hadoop-upgrade', {'version': version})
        self.assertEqual({'result': 'complete'}, self.d.action_fetch(id))
        id = self.d.action_do('slave/2', 'hadoop-upgrade', {'version': version})
        self.assertEqual({'result': 'complete'}, self.d.action_fetch(id))

    def test_first_file_check(self):
        self._hdfs_read_file()

    def test_hadoop_version(self):
        version = 'Hadoop 2.7.2'
        output, retcode = self.hdfs_a.run("su ubuntu -c 'hadoop version|head -n1'")
        self.assertEqual(version, output)
        output, retcode = self.hdfs_b.run("su ubuntu -c 'hadoop version|head -n1'")
        self.assertEqual(version, output)

        for sentry in self.d.sentry['slave']:
            output, retcode = self.d.sentry['slave'][sentry.info['unit']].run("su ubuntu -c 'hadoop version|head -n1'")
            self.assertEqual(version, output)

    def test_downgrade(self):
        pass

    def test_second_file_check(self):
        self._hdfs_read_file()

    def test_upgrade_again(self):
        #test_upgrade()
        pass

    def test_finalize(self):
        pass

    def test_third_file_check(self):
        self._hdfs_read_file()

if __name__ == '__main__':
    unittest.main()
