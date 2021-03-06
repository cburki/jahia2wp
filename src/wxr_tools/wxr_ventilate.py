# -*- coding: utf-8; -*-
# All rights reserved. ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, VPSI, 2017

import lxml.etree
from urllib.parse import urlparse, urlunparse
import os
import sys
import logging

dirname = os.path.dirname
sys.path.append(dirname(dirname(os.path.realpath(__file__))))

from wxr_tools.wxr_model import Channel, Page, NavMenu, NavMenuItem, Item  # noqa: E402
from wxr_tools.html import fix_links                                       # noqa: E402


def normalize_site_url(url_text):
    url = urlparse(url_text)
    # Believe it or not, _replace is public and documented API
    url = url._replace(scheme='https')
    if not url.path.endswith('/'):
        url = url._replace(path=url.path + '/')
    return urlunparse(url)


class Ventilator:
    """
    wxr-ventilate: Transform WXR to WXR for the EPFL web sites

    WXR, short for Wordpress Export RSS (https://github.com/pbiron/wxr) is
    the native XML dump/restore format for WordPress.

    This class consumes and produces WXR files. It takes part in the
    "ventilation" process by filtering and reparenting pages so as to make
    a number of independent WordPress instances appear to the public as
    one large site, such as www.epfl.ch and vpsi.epfl.ch. Specifically, it
    gets invoked once per line in the governing CSV file, and produces
    exactly one XML file per run on standard output.
    """
    def __init__(self, file, new_site_url_base, filter,
                 url_rewrite_from, url_rewrite_to, relative_uri):

        self.etree = lxml.etree.parse(file)
        self.new_site_url_base = new_site_url_base
        self.filter = filter
        self.url_rewrite_from = url_rewrite_from
        self.url_rewrite_to = url_rewrite_to
        self.relative_uri = relative_uri

    @property
    def new_root_url(self):
        return normalize_site_url(self.new_site_url_base)

    def ventilate(self):
        """Filter and rearrange the pages under the --add-structure path.

        If the site has a homepage, place it at the path given by
        --add-structure (and its translations at a closely-related
        path), and reparent all other pages under the homepage (and
        translations).

        If the site has no homepage, create a synthetic (untranslated)
        node at --add-structure and reparent everything under it.

        If --add-structure is not specified on the command line, still
        reparent under the home page(s) if any (but don't move them).

        Returns: The lxml etree object.
        """

        unique_page = None

        if self.filter.endswith("**"):
            keep_children = True
            keep_this_page = True
        elif self.filter.endswith("*"):
            keep_children = True
            keep_this_page = False
        else:
            keep_children = False
            keep_this_page = False

        if self.filter:

            if not keep_children:
                # we try to ventilate one page

                url_page = self.filter
                if not url_page.endswith('/'):
                    url_page += "/"

                # Delete all nodes except node corresponding
                # to page to ventilate
                for item in Item.all(self.etree):
                    if item.guid != url_page:
                        item.delete()
                    else:
                        unique_page = item
            else:
                filter_url = self.filter.rstrip('*')

                for item in Item.all(self.etree):
                    if filter_url == item.link:
                        if not keep_this_page:
                            item.delete()
                    elif filter_url in item.link:
                        if not keep_children:
                            item.delete()

        if self.relative_uri:
            path_components = self.relative_uri.split('/')
            if path_components[0] == '':
                # Tolerate incorrect --add-structure=/foo/bar
                path_components.pop(0)

            assert len(path_components) > 0

            if unique_page:
                reparent_under = self.add_structure(path_components[:-1])
                unique_page.parent_id = reparent_under
            else:
                homepage = self.homepageify()
                if homepage is not None:
                    reparent_under = self.add_structure(path_components[:-1])
                    for p in homepage.translations_list:
                        p.parent_id = reparent_under
                        p.post_slug = path_components[-1] + (
                            '' if p.id == homepage.id else p.language)
                else:
                    reparent_under = self.add_structure(path_components)
                    for p in Page.all(self.etree):
                        if not p.parent_id:
                            p.parent_id = reparent_under

            if self.filter and not keep_children:
                # Single page requested - we don't want menus
                for menu in NavMenu.all(self.etree):
                    menu.delete()
            else:
                # All pages requested
                self.trim_and_reparent_menus()

        if self.url_rewrite_from and self.url_rewrite_to:
            self.fix_links()

        return self.etree

    def homepageify(self):
        """Rearrange all pages under the home page(s).

        (The plural case is when Polylang is in play.)

        If the site has a homepage, reparent all other pages under it.
        If the site has no homepage, do nothing.

        Returns: The homepage as a Page object, or None.
        """

        homepage = Page.homepage(self.etree)
        if homepage is None:
            return

        translations = homepage.translations or {}
        do_not_reparent = set(t.id for t in homepage.translations_list)

        for page in Page.all(self.etree):
            if (page.id not in do_not_reparent) and (not page.parent_id):
                page.parent_id = translations.get(page.language, homepage).id

        return homepage

    def trim_and_reparent_menus(self):
        """Ensure that menus will import/merge sanely.

        * Remove all menus except the "main" one (in all languages)

        * Reparent everything in said menu, so that it becomes easier to
          manipulate the imported menu in the stock wp-admin menu editor
        """

        will_reparent_under = {}
        for menu in NavMenu.all(self.etree):
            slug = menu.slug
            if slug.startswith('main'):
                new_nav = will_reparent_under[slug] = NavMenuItem.insert_structural(self.etree)
                new_nav.menu_slug = slug
                new_nav.menu_item_type = 'custom'
                new_nav.url = '#'
                new_nav.title = '["%s" menu of %s]' % (
                    slug, Channel.the(self.etree).moniker)
            else:
                menu.delete()

        for nav in NavMenuItem.all(self.etree):
            if nav.menu_slug not in will_reparent_under:
                nav.delete()  # We already tossed the menu it belongs to
                continue
            if nav.parent_id == 0:
                nav.parent_id = will_reparent_under[nav.menu_slug].id

    def add_structure(self, path_components):
        current_id = 0
        path_so_far = ""
        for path_component in path_components:
            if path_so_far:
                path_so_far = path_so_far + "/"
            path_so_far += path_component
            structural_page = Page.insert_structural(
                self.etree, path_component)
            # Abuse the <guid> to hold a relative link.
            # See ../importer.php for the corresponding logic and
            # explanation.
            structural_page.guid = path_so_far
            structural_page.post_title = '[%s]' % path_component
            structural_page.parent_id = current_id
            current_id = structural_page.id

        return current_id

    def fix_links(self):

        logging.info("Starting fix links...")

        for page in Page.all(self.etree):
            if page.content is not None:
                page.content = fix_links(page.content, self.url_rewrite_from, self.url_rewrite_to, self.relative_uri)

        logging.info("End fix links...")
