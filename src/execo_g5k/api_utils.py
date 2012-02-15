# Copyright 2009-2012 INRIA Rhone-Alpes, Service Experimentation et
# Developpement
#
# This file is part of Execo.
#
# Execo is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Execo is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public
# License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Execo.  If not, see <http://www.gnu.org/licenses/>

from execo_g5k.config import g5k_api_params
import httplib2
import json

"""Tools for using grid5000.

- Functions for wrapping the grid5000 rest api. The functions which
  query the reference api cache their results for the life of the
  module.

- Miscellaneous functions.

This module is currently not thread-safe.
"""

_g5k_api = None
"""Internal singleton instance of the g5k api rest resource."""
_g5k = None
"""cache of g5k structure.

a dict whose keys are sites, whose values are dict whose keys are
clusters, whose values are hosts.
"""

class APIConnexion:

    def __init__(self, base_uri, username = None, password = None, headers = None, timeout = 300):
        self.base_uri = base_uri.rstrip("/")
        self.headers = {
            'ACCEPT': 'application/json'
            }
        if headers:
            self.headers.update(headers)
        self.http = httplib2.Http(timeout = timeout,
                                  disable_ssl_certificate_validation = True)
        if username and password:
            self.http.add_credentials(username, password)

    def get(self, relative_uri):
        uri = self.base_uri + "/" + relative_uri.lstrip("/")
        response, content = self.http.request(uri,
                                              headers = self.headers)
        if response['status'] not in ['200', '304']:
            raise Exception, "unable to retrieve %s http response = %s, http content = %s" % (uri, response, content)
        return response, content

def _get_g5k_api():
    """Get a singleton instance of a g5k api rest resource."""
    global _g5k_api #IGNORE:W0603
    if not _g5k_api:
        _g5k_api = APIConnexion(g5k_api_params['api_uri'],
                                username = g5k_api_params.get('username'),
                                password = g5k_api_params.get('password'))
    return _g5k_api

def get_g5k_sites():
    """Get the list of Grid5000 sites. Returns an iterable."""
    global _g5k #IGNORE:W0603
    if not _g5k:
        (_, content) = _get_g5k_api().get('/grid5000/sites')
        sites = json.loads(content)
        _g5k = dict()
        for site in [site['uid'] for site in sites['items']]:
            _g5k[site] = None
    return _g5k.keys()

def get_site_clusters(site):
    """Get the list of clusters from a site. Returns an iterable."""
    get_g5k_sites()
    if not _g5k.has_key(site):
        raise ValueError, "unknown g5k site %s" % (site,)
    if not _g5k[site]:
        (_, content) = _get_g5k_api().get('/grid5000/sites/'
                         + site
                         + '/clusters') 
        clusters = json.loads(content)
        _g5k[site] = dict()
        for cluster in [cluster['uid'] for cluster in clusters['items']]:
            _g5k[site][cluster] = None
    return _g5k[site].keys()

def get_cluster_hosts(cluster):
    """Get the list of hosts from a cluster. Returns an iterable."""
    _get_all_site_clusters()
    for site in _g5k.keys():
        if cluster in _g5k[site]:
            if not _g5k[site][cluster]:
                (_, content) = _get_g5k_api().get('/grid5000/sites/' + site
                                 + '/clusters/' + cluster
                                 + '/nodes')
                hosts = json.loads(content)
                _g5k[site][cluster] = ["%s.%s.grid5000.fr" % (host['uid'], site) for host in hosts['items']]
            return list(_g5k[site][cluster])
    raise ValueError, "unknown g5k cluster %s" % (cluster,)

def _get_all_site_clusters():
    """Trigger the querying of the list of clusters from all sites."""
    for site in get_g5k_sites():
        get_site_clusters(site)

def _get_all_clusters_hosts():
    """Trigger the querying of the list of hosts from all clusters from all sites."""
    _get_all_site_clusters()
    for site in get_g5k_sites():
        for cluster in get_site_clusters(site):
            get_cluster_hosts(cluster)

def get_g5k_clusters():
    """Get the list of all g5k clusters. Returns an iterable."""
    clusters = []
    for site in get_g5k_sites():
        clusters.extend(get_site_clusters(site))
    return clusters

def get_g5k_hosts():
    """Get the list of all g5k hosts. Returns an iterable."""
    hosts = []
    for cluster in get_g5k_clusters():
        hosts.extend(get_cluster_hosts(cluster))
    return hosts

def get_cluster_site(cluster):
    """Get the site of a cluster."""
    _get_all_site_clusters()
    for site in _g5k.keys():
        if cluster in _g5k[site]:
            return site
    raise ValueError, "unknown g5k cluster %s" % (cluster,)
