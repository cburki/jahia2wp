#!/usr/bin/env python3
# -*- coding: utf-8; -*-
# All rights reserved. ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, VPSI, 2017

"""wordpress_inventories.py: Create Ansible inventories from the CSV file.

Create a pair of Ansible-compatible inventory files, picking short
names for all sites that we know about (either by actually probing
them for the 'source' column, or verbatim from the 'destination_site'
column). If two such sites end up having the same name, disambiguate
them and persist the mapping to disk for future invocations of the
same code.

Usage:
  wordpress_inventories.py --sources=<sources_inventory_file> --targets=<targets_inventory_file> <ventilation_csv_file>

"""

from docopt import docopt

import os
import sys
import re
from urllib.parse import urlparse
import itertools
import pickle

# This script is being used both as a library and as a script.
# Only fix up the sys.path in the latter case.
if __name__ == '__main__':
    dirname = os.path.dirname
    basename = os.path.basename
    sys.path.append(dirname(dirname(os.path.realpath(__file__))))

from utils import Utils        # noqa: E402
from ops import SshRemoteSite  # noqa: E402


class SiteBag:
    """All the urls and monikers known to this invocation of the ventilation pipeline."""

    def __init__(self):
        self.used_monikers = set()
        # Maps from URLs to Ansible monikers
        self.source_urls = {}
        self.target_urls = {}

    def _persistable_fields(self):
        return ('used_monikers', 'source_urls', 'target_urls')

    @classmethod
    def load(cls):
        if not hasattr(cls, '_singleton'):
            cls._singleton = cls()
            cls._singleton._unpickle(pickle.load(open(cls._get_save_filename(), 'rb')))
        return cls._singleton

    def save(self):
        pickle.dump(self._pickle(), open(self._get_save_filename(), 'wb'))

    def _pickle(self):
        """Returns a class-name-neutral copy of our state, using only standard Python types.

        Fact is, the name of this class changes depending on whether
        we run wordpress_inventories.py as a script or import it as a
        library; and that throws pickle off the tracks.
        """
        state = dict()
        for k in self._persistable_fields():
            state[k] = getattr(self, k)
        return state

    def _unpickle(self, state):
        for k in self._persistable_fields():
            setattr(self, k, state[k])

    @classmethod
    def _get_save_filename(cls):
        return "./wxr_inventory.pickle"

    def get_ansible_moniker(self, url):
        url = self._canonicalize_url(url)
        if url in self.source_urls:
            return self.source_urls[url]
        elif url in self.target_urls:
            return self.target_urls[url]
        else:
            raise KeyError(url)

    def add_source(self, url):
        url = self._canonicalize_url(url)
        if url in self.source_urls:
            return self.source_urls[url]
        else:
            m = self._create_unique_moniker(url, 'src')
            self.source_urls[url] = m
            return m

    def add_target(self, url):
        url = self._canonicalize_url(url)
        if url in self.target_urls:
            return self.target_urls[url]
        else:
            m = self._create_unique_moniker(url)
            self.target_urls[url] = m
            return m

    def _canonicalize_url(self, url):
        if not url.endswith('/'):
            url = url + '/'
        return url

    def _create_unique_moniker(self, url, disambiguator=None):
        m = self._get_moniker_stem(url)

        if m in self.used_monikers and disambiguator is not None:
            m = '{}-{}'.format(m, disambiguator)

        if m in self.used_monikers:
            for d in itertools.count():
                m_with_digit = '{}-{}'.format(m, d)
                if m_with_digit not in self.used_monikers:
                    m = m_with_digit
                    break

        self.used_monikers.add(m)
        return m

    def _get_moniker_stem(self, url):
        """
        Return
        A short name that identifies this URL either in a file path (under wxr-ventilated/),
        or in an Ansible hosts file.

        Example:
        url = "https://migration-wp.epfl.ch/help-actu/"
        return "help-actu"
        """
        parsed = urlparse(url)
        hostname = parsed.netloc.split('.')[0]
        if hostname not in ('migration-wp', 'www2018'):
            return hostname
        return re.search('([^/]*)/?$', parsed.path).group(1)


class AnsibleGroup:
    def __init__(self):
        self.hosts = {}

    def has_wordpress(self, designated_name):
        return designated_name in self.hosts

    def add_wordpress_by_url(self, moniker, site):
        self.hosts[moniker] = dict(
            ansible_host=site.host,
            ansible_port=site.port,
            # The other properties of SshRemoteSite just happen to
            # be aligned with ours.
            wp_hostname=site.wp_hostname,
            wp_env=site.wp_env,
            wp_path=site.wp_path)

    def save(self, target):
        group_name = basename(target)
        with open(target, 'w') as f:
            f.write("# Automatically generated by %s\n\n" % basename(__file__))
            f.write("[all-wordpresses:children]\n%s\n\n" % group_name)

            f.write("[%s]\n" % group_name)
            for host, vars in self.hosts.items():
                vars_txt = ' '.join(
                    '%s=%s' % (k, v) for (k, v) in vars.items())
                f.write("%s\t%s\n" % (host, vars_txt))

    def __repr__(self):
        return '<%s %s>' % (self.__class__, self.name)


class VentilationTodo:
    """A list of action items for ventilation, materialized as a CSV file."""

    class Item:
        """One line in the CSV file."""

        def __init__(self, line):

            source_url = line['source']

            self.source_pattern = source_url

            if source_url.endswith("*"):
                # all pages requested - end character * must be deleted
                self.one_page = False
                self.source_url = source_url.rstrip('*')

            else:
                # single page requested - source url must be URL of WP site
                self.one_page = True
                self.source_url = source_url

            self.destination_site = line['destination_site']
            self.relative_uri = line['relative_uri']

    def __init__(self, csv_path):
        self.items = [self.Item(line) for line in Utils.csv_filepath_to_dict(csv_path)]


def site_moniker(url):
    """
    Return
      The name already chosen for the site at `url`
    """
    return SiteBag.load().get_ansible_moniker(url)


if __name__ == '__main__':
    args = docopt(__doc__)
    sources = AnsibleGroup()
    targets = AnsibleGroup()
    todo = VentilationTodo(args['<ventilation_csv_file>'])
    bag = SiteBag()
    for task in todo.items:
        # For targets, we know the URL ahead of time (and using
        # discover_site_path would do us no good, as the target
        # site may not exist yet)
        url = task.destination_site
        moniker = bag.add_target(url)
        site = SshRemoteSite(url)
        targets.add_wordpress_by_url(moniker, site)
    # Add sources second, because we want to disambiguate with 'src'
    # (rationale: we don't usually want to type in the name of a source;
    # on the other hand we do want to set wp_destructive with the names
    # of the targets)
    for task in todo.items:
        site = SshRemoteSite(task.source_url, discover_site_path=True)
        url = site.get_url()
        moniker = bag.add_source(url)
        sources.add_wordpress_by_url(moniker, site)
    sources.save(args['--sources'])
    targets.save(args['--targets'])
    bag.save()
