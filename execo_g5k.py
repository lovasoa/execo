# -*- coding: utf-8 -*-
#
# Copyright 2009-2011 INRIA Rhone-Alpes, Service Experimentation et
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

r"""Tools and extensions to execo suitable for use in Grid5000."""

import execo
from execo import *
from execo import  _strdate_to_unixts, _strduration_to_seconds, _cjoin
import operator, copy, time

logger = logging.getLogger("execo.g5k")
"""The execo_g5k logger."""

# _STARTOF_ g5k_configuration
g5k_configuration = {
    'kadeploy3': 'kadeploy3',
    'kadeploy3_options': '-k -d',
    'default_env_name': None,
    'default_env_file': None,
    'default_timeout': 900,
    'check_deployed_command': "! (mount | grep -E '^/dev/[[:alpha:]]+2 on / ')",
    'no_ssh_for_local_frontend' : False,
    'polling_interval' : 60,
    'tiny_polling_interval' : 10,
    }
# _ENDOF_ g5k_configuration
"""Global Grid5000 configuration parameters.

- ``kadeploy3``: kadeploy3 command.

- ``kadeploy3_options``: common kadeploy3 command line options.

- ``default_env_name``: a default environment name to use for
  deployments (as registered to kadeploy3).

- ``default_env_file``: a default environment file to use for
  deployments (for kadeploy3).

- ``default_timeout``: default timeout for all calls to g5k services
  (except deployments).

- ``check_deployed_command``: default shell command used by `deploy`
  to check that the nodes are correctly deployed. This command should
  return 0 if the node is correctly deployed, or another value
  otherwise. The default checks that the root is not on the second
  partition of the disk.

- ``no_ssh_for_local_frontend``: if True, don't use ssh to issue g5k
  commands for local site. If False, always use ssh, both for remote
  frontends and local site. Set it to True if you are sure that your
  scripts always run on the local frontend.

- ``polling_interval``: time interval between pollings for various
  operations, eg. wait oar job start.

- ``tiny_polling_interval``: small time interval between pollings for
  various operations, used for example when waiting for a job start,
  and start date of the job is over but the job is not yet in running
  state.
"""

# _STARTOF_ default_oarsh_oarcp_params
default_oarsh_oarcp_params = {
    'user':        None,
    'keyfile':     None,
    'port':        None,
    'ssh':         'oarsh',
    'scp':         'oarcp',
    'taktuk':      'taktuk',
    'ssh_options': ( '-tt',
                     '-o', 'BatchMode=yes',
                     '-o', 'PasswordAuthentication=no',
                     '-o', 'StrictHostKeyChecking=no',
                     '-o', 'UserKnownHostsFile=/dev/null',
                     '-o', 'ConnectTimeout=20' ),
    'scp_options': ( '-o', 'BatchMode=yes',
                     '-o', 'PasswordAuthentication=no',
                     '-o', 'StrictHostKeyChecking=no',
                     '-o', 'UserKnownHostsFile=/dev/null',
                     '-o', 'ConnectTimeout=20',
                     '-rp' ),
    'taktuk_options': ( '-s', ),
    'taktuk_connector': 'oarsh',
    'taktuk_connector_options': ( '-o', 'BatchMode=yes',
                                  '-o', 'PasswordAuthentication=no',
                                  '-o', 'StrictHostKeyChecking=no',
                                  '-o', 'UserKnownHostsFile=/dev/null',
                                  '-o', 'ConnectTimeout=20'),
    'ssh_scp_pty': True,
    'host_rewrite_func': lambda host: host
    }
# _ENDOF_ default_oarsh_oarcp_params
"""A convenient, predefined connexion paramaters dict with oarsh / oarcp configuration.

See `execo.default_connexion_params`
"""

# _STARTOF_ default_frontend_connexion_params
default_frontend_connexion_params = {
    'user':        None,
    'keyfile':     None,
    'port':        None,
    'ssh':         'ssh',
    'scp':         'scp',
    'taktuk':      'taktuk',
    'ssh_options': ( '-tt',
                     '-o', 'BatchMode=yes',
                     '-o', 'PasswordAuthentication=no',
                     '-o', 'StrictHostKeyChecking=no',
                     '-o', 'UserKnownHostsFile=/dev/null',
                     '-o', 'ConnectTimeout=20' ),
    'scp_options': ( '-o', 'BatchMode=yes',
                     '-o', 'PasswordAuthentication=no',
                     '-o', 'StrictHostKeyChecking=no',
                     '-o', 'UserKnownHostsFile=/dev/null',
                     '-o', 'ConnectTimeout=20',
                     '-rp' ),
    'taktuk_options': ( '-s', ),
    'taktuk_connector': 'ssh',
    'taktuk_connector_options': ( '-o', 'BatchMode=yes',
                                  '-o', 'PasswordAuthentication=no',
                                  '-o', 'StrictHostKeyChecking=no',
                                  '-o', 'UserKnownHostsFile=/dev/null',
                                  '-o', 'ConnectTimeout=20'),
    'ssh_scp_pty': False,
    'host_rewrite_func': lambda host: host + ".grid5000.fr"
    }
# _ENDOF_ default_frontend_connexion_params
"""Default connexion params when connecting to a Grid5000 frontend."""

read_user_configuration_dicts(((g5k_configuration, 'g5k_configuration'),
                               (default_frontend_connexion_params, 'default_frontend_connexion_params'),
                               (default_oarsh_oarcp_params, 'default_oarsh_oarcp_params')))

def get_local_site():
    """Return the name of the local site."""
    try:
        return re.search("^[^ \t\n\r\f\v\.]+\.([^ \t\n\r\f\v\.]+)\.grid5000.fr$", socket.gethostname()).group(1)
    except:
        return ""

local_site = get_local_site()

def _get_frontend_connexion_params(frontend_connexion_params):
    params = default_frontend_connexion_params
    if frontend_connexion_params:
        params.update(frontend_connexion_params)
    return params

class Deployment(object):
    """A kadeploy3 deployment.

    POD style class.

    members are:

    - hosts: iterable of hosts on which to deploy.

    - env_file:

    - env_name:

    - user:

    - other_options:

    there must be either one of env_name or env_file parameter
    given. If none given, will try to use the default environement
    from `g5k_configuration`.
    """

    def __init__(self,
                 hosts = None,
                 env_file = None,
                 env_name = None,
                 user = None,
                 other_options = None):
        self.hosts = hosts
        self.env_file = env_file
        self.env_name = env_name
        self.user = user
        self.other_options = other_options

    def _get_common_kadeploy_command_line(self):
        cmd_line = g5k_configuration['kadeploy3']
        cmd_line += " " + g5k_configuration['kadeploy3_options']
        if self.env_file and self.env_name:
            raise ValueError, "Deployment cannot have both env_file and env_name"
        if (not self.env_file) and (not self.env_name):
            if g5k_configuration.has_key('default_environment_name') and g5k_configuration.has_key('default_environment_file'):
                raise Exception, "g5k_configuration cannot have both default_environment_name and default_environment_file"
            if (not g5k_configuration.has_key('default_environment_name')) and (not g5k_configuration.has_key('default_environment_file')):
                raise Exception, "no environment name or file found"
            if g5k_configuration.has_key('default_environment_name'):
                cmd_line += " -e %s" % (g5k_configuration['default_environment_name'],)
            elif g5k_configuration.has_key('default_environment_file'):
                cmd_line += " -a %s" % (g5k_configuration['default_environment_file'],)
        elif self.env_name:
            cmd_line += " -e %s" % (self.env_name,)
        elif self.env_file:
            cmd_line += " -a %s" % (self.env_file,)
        if self.user != None:
            cmd_line += " -u %s" % (self.user,)
        if self.other_options:
            cmd_line += " %s" % (self.other_options,)
        return cmd_line

    def __repr__(self):
        s = ""
        if self.hosts != None: s = _cjoin(s, "hosts=%r" % (self.hosts,))
        if self.env_file != None: s = _cjoin(s, "env_file=%r" % (self.env_file,))
        if self.env_name != None: s = _cjoin(s, "env_name=%r" % (self.env_name,))
        if self.user != None: s = _cjoin(s, "user=%r" % (self.user,))
        if self.other_options: s = _cjoin(s, "other_options=%r" % (self.other_options,))
        return "Deployment(%s)" % (s,)

class _KadeployStdoutHandler(ProcessOutputHandler):

    """Parse kadeploy3 stdout."""
    
    def __init__(self, kadeployer, out = False):
        """
        :param kadeployer: the `Kadeployer` to which this
          `ProcessOutputHandler` is attached.
        """
        super(_KadeployStdoutHandler, self).__init__()
        self._kadeployer = kadeployer
        self._good_nodes_header_re = re.compile("^Nodes correctly deployed on cluster \w+\s*$")
        self._bad_nodes_header_re = re.compile("^Nodes not correctly deployed on cluster \w+\s*$")
        self._good_node_re = re.compile("^(\S+)\s*$")
        self._bad_node_re = re.compile("^(\S+)(\s+\(.*\))?\s*$")
        self._SECTION_NONE, self._SECTION_GOODNODES, self._SECTION_BADNODES = range(3)
        self._current_section = self._SECTION_NONE
        self._out = out

    def action_reset(self):
        self._current_section = self._SECTION_NONE
        
    def read_line(self, process, string, eof = False, error = False):
        if self._out:
            print string,
        if self._good_nodes_header_re.search(string) != None:
            self._current_section = self._SECTION_GOODNODES
            return
        if self._bad_nodes_header_re.search(string) != None:
            self._current_section = self._SECTION_BADNODES
            return
        if self._current_section == self._SECTION_GOODNODES:
            so = self._good_node_re.search(string)
            if so != None:
                host_address = so.group(1)
                self._kadeployer._add_good_host_address(host_address)
        elif self._current_section == self._SECTION_BADNODES:
            so = self._bad_node_re.search(string)
            if so != None:
                host_address = so.group(1)
                self._kadeployer._add_bad_host_address(host_address)

class _KadeployStderrHandler(ProcessOutputHandler):

    """Parse kadeploy3 stderr."""
    
    def __init__(self, kadeployer, out = False):
        """
        :param kadeployer: the `Kadeployer` to which this
          `ProcessOutputHandler` is attached.
        """
        super(_KadeployStderrHandler, self).__init__()
        self._kadeployer = kadeployer
        self._out = out

    def read_line(self, process, string, eof = False, error = False):
        if self._out:
            print string,

class Kadeployer(Remote):

    """Deploy an environment with kadeploy3 on several nodes.

    Able to deploy in parallel to multiple Grid5000 sites.
    """

    def __init__(self, deployment, frontend_connexion_params = None, out = False, **kwargs):
        """
        :param deployment: instance of Deployment class describing the
          intended kadeployment.

        :param frontend_connexion_params: connexion params for
          connecting to sites' frontends if needed. Values override
          those in `default_frontend_connexion_params`.

        :param out: if True, output kadeploy stdout / stderr to
          stdout.
        """
        super(Remote, self).__init__(**kwargs)
        self._frontend_connexion_params = frontend_connexion_params
        self._deployment = deployment
        self._out = out
        self._fhosts = get_hosts_set(deployment.hosts)
        searchre1 = re.compile("^[^ \t\n\r\f\v\.]+\.([^ \t\n\r\f\v\.]+)\.grid5000.fr$")
        searchre2 = re.compile("^[^ \t\n\r\f\v\.]+\.([^ \t\n\r\f\v\.]+)$")
        searchre3 = re.compile("^[^ \t\n\r\f\v\.]+$")
        sites = dict()
        for host in self._fhosts:
            site = None
            mo1 = searchre1.search(host.address)
            if mo1 != None:
                site = mo1.group(1)
            else:
                mo2 = searchre2.search(host.address)
                if mo2 != None:
                    site = mo1.group(1)
                else:
                    mo3 = searchre3.search(host.address)
                    if mo3 != None:
                        site = local_site
                    else:
                        raise ValueError, "unknown grid5000 site for host %s" % host.address
            if sites.has_key(site):
                sites[site].append(host)
            else:
                sites[site] = [host]
        self._processes = dict()
        lifecycle_handler = ActionNotificationProcessLifecycleHandler(self, len(sites))
        for site in sites.keys():
            kadeploy_command = self._deployment._get_common_kadeploy_command_line()
            for host in sites[site]:
                kadeploy_command += " -m %s" % host.address
            if g5k_configuration['no_ssh_for_local_frontend'] == True and site == local_site:
                p = Process(kadeploy_command,
                            stdout_handler = _KadeployStdoutHandler(self, out = self._out),
                            stderr_handler = _KadeployStderrHandler(self, out = self._out),
                            timeout = self._timeout,
                            ignore_exit_code = self._ignore_exit_code,
                            ignore_timeout = self._ignore_timeout,
                            process_lifecycle_handler = lifecycle_handler,
                            pty = True)
            else:
                p = SshProcess(Host(site),
                               kadeploy_command,
                               connexion_params = _get_frontend_connexion_params(frontend_connexion_params),
                               stdout_handler = _KadeployStdoutHandler(self, out = self._out),
                               stderr_handler = _KadeployStderrHandler(self, out = self._out),
                               timeout = self._timeout,
                               ignore_exit_code = self._ignore_exit_code,
                               process_lifecycle_handler = lifecycle_handler,
                               pty = True)
            self._processes[p] = host

    def _common_reset(self):
        super(Kadeployer, self)._common_reset()
        self._good_hosts = set()
        self._bad_hosts = set()
        
    def _args(self):
        return [ repr(self._deployment) ] + Action._args(self) + Kadeployer._kwargs(self)

    def _kwargs(self):
        kwargs = []
        if self._frontend_connexion_params: kwargs.append("frontend_connexion_params=%r" % (self._frontend_connexion_params,))
        if self._out: kwargs.append("out=%r" % (self._out,))
        return kwargs

    def _infos(self):
        return Remote._infos(self) + [ "cmds=%r" % ([ process.cmd() for process in self._processes],),
                                       "deployed_hosts=%r" % (self._good_hosts,),
                                       "error_hosts=%r" % (self._bad_hosts,) ]

    def name(self):
        if self._name == None:
            return "%s on %i hosts / %i frontends" % (self.__class__.__name__, len(self._fhosts), len(self._processes))
        else:
            return self._name

    def _add_good_host_address(self, host_address):
        """Add a host to the deployed hosts list. Intended to be called from the `ProcessOutputHandler`."""
        self._good_hosts.add(Host(host_address))

    def _add_bad_host_address(self, host_address):
        """Add a host to the hosts not deployed list. Intended to be called from the `ProcessOutputHandler`."""
        self._bad_hosts.add(Host(host_address))

    def get_deployed_hosts(self):
        """Return an iterable of `Host` containing the deployed hosts.

        this iterable won't be complete if `Kadeployer` has not
        terminated.
        """
        return list(self._good_hosts)

    def get_error_hosts(self):
        """Return an iterable of `Host` containing the hosts not deployed.

        this iterable won't be complete if `Kadeployer` has not
        terminated.
        """
        return list(self._fhosts.difference(self._good_hosts))

    def error(self):
        error = super(Kadeployer, self).error()
        if self.ended():
            if len(self._good_hosts.intersection(self._bad_hosts)) != 0:
                error = True
            if len(self._good_hosts.union(self._bad_hosts).symmetric_difference(self._fhosts)) != 0:
                error = True
        return error

    def reset(self):
        retval = super(Kadeployer, self).reset()
        for process in self._processes:
            process.stdout_handler().action_reset()
        return retval

def _date_in_range(date, range):
    """Check that a date is inside a range. If range is None, return True."""
    if range == None: return True
    if range[0] and date < range[0]:
        return False
    if range[1] and date > range[1]:
        return False
    return True

def format_oar_date(date):
    """Return a string with the formatted date (year, month, day, hour, min, sec, ms) formatted for oar/oargrid.

    timezone is discarded since oar doesn't know about them.

    :param date: a date in one of the formats handled.
    """
    date = int(get_unixts(date))
    t = time.localtime(date)
    formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", t)
    return formatted_time

def format_oar_duration(duration):
    """Return a string with a formatted duration (hours, mins, secs, ms) formatted for oar/oargrid.

    :param duration: a duration in one of the formats handled.
    """
    duration = get_seconds(duration)
    s = duration
    h = (s - (s % 3600)) / 3600
    s -= h * 3600
    m = (s - (s % 60)) / 60
    s -= m * 60
    s = int(s)
    formatted_duration = ""
    if duration >= 3600:
        formatted_duration += "%i:" % h
    else:
        formatted_duration += "0:"
    if duration >= 60:
        formatted_duration += "%i:" % m
    else:
        formatted_duration += "0:"
    formatted_duration += "%i" % s
    return formatted_duration

def oar_date_to_unixts(date):
    """Convert a date in the format returned by oar/oargrid to an unix timestamp."""
    return _strdate_to_unixts(date)

def oar_duration_to_seconds(duration):
    """Convert a duration in the format returned by oar/oargrid to a number of seconds."""
    return _strduration_to_seconds(duration)

class OarSubmission(object):
    """An oar submission.

    POD style class.

    members are:

    - resources: Set the requested resources for the job. Oar option
      -l, without the walltime.

    - walltime: Job walltime. Walltime part of oar -l option.

    - job_type: Job type, oar option -t: deploy, besteffort, cosystem,
      checkpoint, timesharing, allow_classic_ssh.

    - sql_properties: constraints to properties for the job, oar
      option -p (use single quotes for literal strings).

    - queue: the queue to submit the job to. Oar option -q.

    - reservation_date: Request that the job starts at a specified
      time. Oar option -r.

    - directory: Specify the directory where to launch the command
      (default is current directory). Oar option -d.

    - project: pecify a name of a project the job belongs to. Oar
      option --project.

    - name: Specify an arbitrary name for the job. Oar option -n.

    - additional_options: passed directly to oarsub on the command
      line.

    - command: run by oarsub (default: sleep a long time).
    """

    def __init__(self,
                 resources = None,
                 walltime = None,
                 job_type = None,
                 sql_properties = None,
                 queue = None,
                 reservation_date = None,
                 directory = None,
                 project = None,
                 name = None,
                 additional_options = None,
                 command = None):
        self.resources = resources
        self.walltime = walltime
        self.job_type = job_type
        self.sql_properties = sql_properties
        self.queue = queue
        self.reservation_date = reservation_date
        self.directory = directory
        self.project = project
        self.name = name
        self.additional_options = additional_options
        self.command = command

    def __repr__(self):
        s = ""
        if self.resources != None: s = _cjoin(s, "resources=%r" % (self.resources,))
        if self.walltime != None: s = _cjoin(s, "walltime=%r" % (format_duration(self.walltime),))
        if self.job_type != None: s = _cjoin(s, "job_type=%r" % (self.job_type,))
        if self.sql_properties != None: s = _cjoin(s, "sql_properties=%r" % (self.sql_properties,))
        if self.queue != None: s = _cjoin(s, "queue=%r" % (self.queue,))
        if self.reservation_date != None: s = _cjoin(s, "reservation_date=%r" % (format_date(self.reservation_date),))
        if self.directory != None: s = _cjoin(s, "directory=%r" % (self.directory,))
        if self.project != None: s = _cjoin(s, "project=%r" % (self.project,))
        if self.name != None: s = _cjoin(s, "name=%r" % (self.name,))
        if self.additional_options != None: s = _cjoin(s, "additional_options=%r" % (self.additional_options,))
        if self.command != None: s = _cjoin(s, "command=%r" % (self.command,))
        return "OarSubmission(%s)" % (s,)

def oarsub(job_specs, frontend_connexion_params = None, timeout = False):
    """Submit jobs.

    :param job_specs: iterable of tuples (OarSubmission, site) with None
      for local site

    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.
    
    :param timeout: timeout for retrieving. Default is False, which
      means use ``g5k_configuration['default_timeout']``. None means no
      timeout.

    Returns a list of tuples (oarjob id, site), with site == None for
    local site. If submission error, oarjob id == None. The returned
    list matches, in the same order, the job_specs parameter.
    """
    if timeout == False:
        timeout = g5k_configuration['default_timeout']
    processes = []
    for (spec, site) in job_specs:
        oarsub_cmdline = 'oarsub'
        if spec.additional_options != None:
            oarsub_cmdline += ' %s' % (spec.additional_options,)
        oarsub_cmdline += ' -l %s' % (spec.resources,)
        if spec.walltime != None:
            oarsub_cmdline += ',walltime=%s' % (format_oar_duration(spec.walltime),)
        if os.environ.has_key('OAR_JOB_KEY_FILE'):
            oarsub_cmdline += ' -k -i %s' % (os.environ['OAR_JOB_KEY_FILE'],)
        if spec.job_type != None:
            oarsub_cmdline += ' -t "%s"' % (spec.job_type,)
        if spec.sql_properties != None:
            oarsub_cmdline += ' -p "%s"' % (spec.sql_properties,)
        if spec.queue != None:
            oarsub_cmdline += ' -q "%s"' % (spec.queue,)
        if spec.reservation_date != None:
            oarsub_cmdline += ' -r "%s"' % (format_oar_date(spec.reservation_date),)
        if spec.directory != None:
            oarsub_cmdline += ' -d "%s"' % (spec.directory,)
        if spec.project != None:
            oarsub_cmdline += ' --project "%s"' % (spec.project,)
        if spec.name != None:
            oarsub_cmdline += ' -n "%s"' % (spec.name,)
        if spec.command != None:
            oarsub_cmdline += ' "%s"' % (spec.command,)
        else:
            oarsub_cmdline += ' "sleep 31536000"'
        if site == None:
            site = local_site
        if g5k_configuration['no_ssh_for_local_frontend'] == True and site == local_site:
            p = Process(oarsub_cmdline,
                        timeout = timeout,
                        pty = True)
            p.site = site
            processes.append(p)
        else:
            p = SshProcess(Host(site),
                           oarsub_cmdline,
                           connexion_params = _get_frontend_connexion_params(frontend_connexion_params),
                           timeout = timeout,
                           pty = True)
            p.site = site
            processes.append(p)
    oar_job_ids = []
    if len(processes) == 0:
        return oar_job_ids
    for process in processes: process.start()
    for process in processes: process.wait()
    for process in processes:
        job_id = None
        if process.ok():
            mo = re.search("^OAR_JOB_ID=(\d+)\s*$", process.stdout(), re.MULTILINE)
            if mo != None:
                job_id = int(mo.group(1))
        oar_job_ids.append((job_id, process.site))
    return oar_job_ids

def oardel(job_specs, frontend_connexion_params = None, timeout = False):
    """Delete oar jobs.

    Ignores any error, so you can delete inexistant jobs, already
    deleted jobs, or jobs that you don't own. Those deletions will be
    ignored.

    :param job_specs: iterable of tuples (job_id, site) with None for
      local site

    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.
    
    :param timeout: timeout for retrieving. Default is False, which
      means use ``g5k_configuration['default_timeout']``. None means no
      timeout.
    """
    if timeout == False:
        timeout = g5k_configuration['default_timeout']
    processes = []
    for (job_id, site) in job_specs:
        oardel_cmdline = "oardel %i" % (job_id,)
        if site == None:
            site = local_site
        if g5k_configuration['no_ssh_for_local_frontend'] == True and site == local_site:
            processes.append(Process(oardel_cmdline,
                                     timeout = timeout,
                                     ignore_exit_code = True,
                                     pty = True))
        else:
            processes.append(SshProcess(Host(site),
                                        oardel_cmdline,
                                        connexion_params = _get_frontend_connexion_params(frontend_connexion_params),
                                        timeout = timeout,
                                        ignore_exit_code = True,
                                        pty = True))
    for process in processes: process.start()
    for process in processes: process.wait()

def oargridsub(job_specs, reservation_date = None,
               walltime = None, job_type = None,
               queue = None, directory = None,
               additional_options = None,
               frontend_connexion_params = None,
               timeout = False):
    """Submit oargrid jobs.

    :param job_specs: iterable of tuples (OarSubmission,
      clusteralias). Reservation date, walltime, queue, directory,
      project, additional_options, command of the OarSubmission are
      ignored.

    :param reservation_date: grid job reservation date. Default: now.

    :param walltime: grid job walltime.

    :param job_type: type of job for all clusters: deploy, besteffort,
      cosystem, checkpoint, timesharing.

    :param queue: oar queue to use.

    :param directory: directory where the reservation will be
      launched.

    :param additional_options: passed directly to oargridsub on the
      command line.

    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.

    :param timeout: timeout for retrieving. Default is False, which
      means use ``g5k_configuration['default_timeout']``. None means no
      timeout.

    Returns a tuple (oargrid_job_id, ssh_key), or (None, None) if
    error.
    """
    if timeout == False:
        timeout = g5k_configuration['default_timeout']
    oargridsub_cmdline = 'oargridsub'
    if additional_options != None:
        oargridsub_cmdline += ' %s' % (additional_options,)
    oargridsub_cmdline += ' -v'
    if reservation_date:
        oargridsub_cmdline += ' -s "%s" ' % (format_oar_date(reservation_date),)
    if os.environ.has_key('OAR_JOB_KEY_FILE'):
        oargridsub_cmdline += ' -i %s' % (os.environ['OAR_JOB_KEY_FILE'],)
    if queue != None:
        oargridsub_cmdline += '-q "%s" ' % (queue,)
    if job_type != None:
        oargridsub_cmdline += '-t "%s" ' % (job_type,)
    if walltime != None:
        oargridsub_cmdline += '-w "%s" ' % (format_oar_duration(walltime),)
    if directory != None:
        oargridsub_cmdline += '-d "%s" ' % (directory,)
    firstclusteralias = True
    for (spec, clusteralias) in job_specs:
        if firstclusteralias:
            firstclusteralias = False
        else:
            oargridsub_cmdline += ','
            oargridsub_cmdline += '%s:rdef="%s"' % (clusteralias, spec.resources)
        if spec.job_type != None:
            oargridsub_cmdline += ':type="%s"' % (spec.job_type,)
        if spec.sql_properties != None:
            oargridsub_cmdline += ':prop="%s"' % (spec.sql_properties,)
        if spec.name != None:
            oargridsub_cmdline += ':name="%s"' % (spec.name,)
    if g5k_configuration['no_ssh_for_local_frontend'] == True:
        process = Process(oargridsub_cmdline,
                          timeout = timeout,
                          pty = True)
    else:
        process = SshProcess(Host(local_site),
                             oargridsub_cmdline,
                             connexion_params = _get_frontend_connexion_params(frontend_connexion_params),
                             timeout = timeout,
                             pty = True)
    process.run()
    job_id = None
    ssh_key = None
    if process.ok():
        mo = re.search("^\[OAR_GRIDSUB\] Grid reservation id = (\d+)\s*$", process.stdout(), re.MULTILINE)
        if mo != None:
            job_id = int(mo.group(1))
        mo = re.search("^\[OAR_GRIDSUB\] SSH KEY : (.*)\s*$", process.stdout(), re.MULTILINE)
        if mo != None:
            ssh_key = mo.group(1)
    if job_id != None:
        return (job_id, ssh_key)
    else:
        return (None, None)

def oargriddel(job_ids, frontend_connexion_params = None, timeout = False):
    """Delete oargrid jobs.

    Ignores any error, so you can delete inexistant jobs, already
    deleted jobs, or jobs that you don't own. Those deletions will be
    ignored.

    :param job_ids: iterable of oar grid job ids.

    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.

    :param timeout: timeout for retrieving. Default is False, which
      means use ``g5k_configuration['default_timeout']``. None means no
      timeout.
    """
    if timeout == False:
        timeout = g5k_configuration['default_timeout']
    processes = []
    for job_id in job_ids:
        oargriddel_cmdline = "oargriddel %i" % (job_id,)
        if g5k_configuration['no_ssh_for_local_frontend'] == True:
            processes.append(Process(oargriddel_cmdline,
                                     timeout = timeout,
                                     ignore_exit_code = True,
                                     pty = True))
        else:
            processes.append(SshProcess(Host(local_site),
                                        oargriddel_cmdline,
                                        connexion_params = _get_frontend_connexion_params(frontend_connexion_params),
                                        timeout = timeout,
                                        ignore_exit_code = True,
                                        pty = True))
    for process in processes: process.start()
    for process in processes: process.wait()

def get_current_oar_jobs(sites = None,
                         start_between = None,
                         end_between = None,
                         frontend_connexion_params = None,
                         timeout = False,
                         abort_on_error = False):
    """Return a list of current active oar job ids.

    The list contains tuples (oarjob id, site).

    :param sites: an iterable of sites to connect to. A site with
      value None means local site. If sites == None, means get current
      oar jobs only for local site.

    :param start_between: a tuple (low, high) of endpoints. Filters
      and returns only jobs whose start date is in between these
      endpoints.
        
    :param end_between: a tuple (low, high) of endpoints. Filters and
      returns only jobs whose end date is in between these endpoints.
        
    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.
    
    :param timeout: timeout for retrieving. Default is False, which
      means use ``g5k_configuration['default_timeout']``. None means no
      timeout.

    :param abort_on_error: default False. If True, raises an exception
      on any error. If False, will returned the list of job got, even
      if incomplete (some sites may have failed to answer).
    """
    if timeout == False:
        timeout = g5k_configuration['default_timeout']
    if start_between: start_between = map(get_unixts, start_between)
    if end_between: end_between = map(get_unixts, end_between)
    processes = []
    if sites == None:
        sites = [ None ]
    cmd = "oarstat -u"
    for site in sites:
        if site == None:
            site = local_site
        if g5k_configuration['no_ssh_for_local_frontend'] == True and site == local_site:
            p = Process(cmd,
                        timeout = timeout,
                        pty = True)
            p.site = site
            processes.append(p)
        else:
            p = SshProcess(Host(site),
                           cmd,
                           connexion_params = _get_frontend_connexion_params(frontend_connexion_params),
                           timeout = timeout,
                           pty = True)
            p.site = site
            processes.append(p)
    oar_job_ids = []
    if len(processes) == 0:
        return oar_job_ids
    for process in processes: process.start()
    for process in processes: process.wait()
    if reduce(operator.and_, [ p.ok() for p in processes ]) or not abort_on_error:
        for process in processes:
            if process.ok():
                jobs = re.findall("^(\d+)\s", process.stdout(), re.MULTILINE)
                oar_job_ids.extend([ (int(jobid), process.site) for jobid in jobs ])
        if start_between or end_between:
            filtered_job_ids = []
            for jobsite in oar_job_ids:
                info = get_oar_job_info(jobsite[0], jobsite[1], connexion_params, timeout)
                if (_date_in_range(info['start_date'], start_between)
                    and _date_in_range(info['start_date'] + info['walltime'], end_between)):
                    filtered_job_ids.append(jobsite)
            oar_job_ids = filtered_job_ids
        return oar_job_ids
    raise Exception, "error, list of current oar jobs: %s" % (processes,)

def get_current_oargrid_jobs(start_between = None,
                             end_between = None,
                             frontend_connexion_params = None,
                             timeout = False):
    """Return a list of current active oargrid job ids.

    :param start_between: a tuple (low, high) of endpoints. Filters
      and returns only jobs whose start date is in between these
      endpoints.
        
    :param end_between: a tuple (low, high) of endpoints. Filters and
      returns only jobs whose end date is in between these endpoints.
        
    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.

    :param timeout: timeout for retrieving. Default is False, which
      means use ``g5k_configuration['default_timeout']``. None means no
      timeout.
    """
    if timeout == False:
        timeout = g5k_configuration['default_timeout']
    if start_between: start_between = map(get_unixts, start_between)
    if end_between: end_between = map(get_unixts, end_between)
    cmd = "oargridstat"
    if g5k_configuration['no_ssh_for_local_frontend'] == True:
        process = Process(cmd,
                          timeout = timeout,
                          pty = True).run()
    else:
        process = SshProcess(Host(local_site),
                             cmd,
                             connexion_params = _get_frontend_connexion_params(frontend_connexion_params),
                             timeout = timeout,
                             pty = True).run()
    if process.ok():
        jobs = re.findall("Reservation # (\d+):", process.stdout(), re.MULTILINE)
        oargrid_job_ids = map(int, jobs)
        if start_between or end_between:
            filtered_job_ids = []
            for job in oargrid_job_ids:
                info = get_oargrid_job_info(job, timeout)
                if (_date_in_range(info['start_date'], start_between)
                    and _date_in_range(info['start_date'] + info['walltime'], end_between)):
                    filtered_job_ids.append(job)
            oargrid_job_ids = filtered_job_ids
        return oargrid_job_ids
    raise Exception, "error, list of current oargrid jobs: %s" % (process,)

def get_oar_job_info(oar_job_id = None, site = None, frontend_connexion_params = None, timeout = False):
    """Return a dict with informations about an oar job.

    :param oar_job_id: the oar job id. If None given, will try to get
      it from ``OAR_JOB_ID`` environment variable.
      
    :param site: the Grid5000 site of the oar job. If None given,
      assume local oar job (only works if run on the local frontend).
        
    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.

    :param timeout: timeout for retrieving. Default is False, which
      means use ``g5k_configuration['default_timeout']``. None means no
      timeout.
    
    Hash returned may contain these keys:

    - ``start_date``: unix timestamp of job's start date

    - ``walltime``: job's walltime (seconds)

    - ``scheduled_start``: unix timestamp of job's start prediction
      (may change between invocations)

    - ``state``: job state

    But no info may be available as long as the job is not scheduled.
    """
    if timeout == False:
        timeout = g5k_configuration['default_timeout']
    if oar_job_id == None:
        if os.environ.has_key('OAR_JOB_ID'):
            oar_job_id = os.environ['OAR_JOB_ID']
        else:
            raise ValueError, "no oar job id given and no OAR_JOB_ID environment variable found"
    cmd = "oarstat -fj %i" % (oar_job_id,)
    if site == None:
        site = local_site
    if g5k_configuration['no_ssh_for_local_frontend'] == True and site == local_site:
        process = Process(cmd,
                          timeout = timeout,
                          pty = True)
    else:
        process = SshProcess(Host(site),
                             cmd,
                             connexion_params = _get_frontend_connexion_params(frontend_connexion_params),
                             timeout = timeout,
                             pty = True)
    process.run()
    job_info = dict()
    if process.ok():
        start_date_result = re.search("^\s*startTime = (\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d)\s*$", process.stdout(), re.MULTILINE)
        if start_date_result:
            start_date = oar_date_to_unixts(start_date_result.group(1))
            job_info['start_date'] = start_date
        walltime_result = re.search("^\s*walltime = (\d+:\d?\d:\d?\d)\s*$", process.stdout(), re.MULTILINE)
        if walltime_result:
            walltime = oar_duration_to_seconds(walltime_result.group(1))
            job_info['walltime'] = walltime
        scheduled_start_result = re.search("^\s*scheduledStart = (\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d)\s*$", process.stdout(), re.MULTILINE)
        if scheduled_start_result:
            scheduled_start = oar_date_to_unixts(scheduled_start_result.group(1))
            job_info['scheduled_start'] = scheduled_start
        state_result = re.search("^\s*state = (\w*)\s*$", process.stdout(), re.MULTILINE)
        if state_result:
            job_info['state'] = state_result.group(1)
    return job_info

def wait_oar_job_start(oar_job_id = None, site = None,
                       frontend_connexion_params = None,
                       timeout = None,
                       prediction_callback = None):
    """Sleep until an oar job's start time.

    As long as the job isn't scheduled, wait_oar_job_start will sleep
    / poll every `g5k_configuration['polling_interval']` seconds until
    it is scheduled. Then, knowing its start date, it will sleep the
    amount of time necessary to wait for the job start.

    returns True if wait was successful, False otherwise (job
    cancelled, error)

    :param oar_job_id: the oar job id. If None given, will try to get
      it from ``OAR_JOB_ID`` environment variable.

    :param site: the Grid5000 site of the oar job. If None given,
      assume local oar job (only works if run on the local frontend).

    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.
    
    :param timeout: timeout for retrieving. Default is None (no
      timeout).

    :param prediction_callback: function taking a unix timestamp as
      parameter. This function will be called each time oar job start
      prediction changes.
    """

    prediction = None
    def check_prediction_changed(prediction, infos, key):
        old_prediction = prediction
        prediction = infos[key]
        if old_prediction == None or prediction != old_prediction:
            if prediction_callback != None:
                prediction_callback(prediction)
        return prediction

    def mymin(a, b):
        if a == None: return b
        if b == None: return a
        return min(a, b)

    countdown = Timer(timeout)
    while countdown.remaining() == None or countdown.remaining() > 0:
        infos = get_oar_job_info(oar_job_id, site, frontend_connexion_params, countdown.remaining())
        now = time.time()
        if infos.has_key('state'):
            if infos['state'] == "Terminated" or infos['state'] == "Error":
                return False
            if infos['state'] == "Running":
                return True
        if infos.has_key('start_date'):
            if now >= infos['start_date']:
                sleep(mymin(g5k_configuration['tiny_polling_interval'], countdown.remaining()))
                continue
            prediction = check_prediction_changed(prediction, infos, 'start_date')
            if infos['start_date'] < now + g5k_configuration['polling_interval']:
                sleep(until = mymin(infos['start_date'], now + countdown.remaining() if countdown.remaining() != None else None))
                continue
        elif infos.has_key('scheduled_start'):
            prediction = check_prediction_changed(prediction, infos, 'scheduled_start')
            if infos['scheduled_start'] < now + g5k_configuration['polling_interval']:
                sleep(until = mymin(infos['scheduled_start'], countdown.remaining()))
                continue
        sleep(mymin(g5k_configuration['polling_interval'], countdown.remaining()))
    
def get_oargrid_job_info(oargrid_job_id = None, frontend_connexion_params = None, timeout = False):
    """Return a dict with informations about an oargrid job.

    :param oargrid_job_id: the oargrid job id.

    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.

    :param timeout: timeout for retrieving. Default is False, which
      means use ``g5k_configuration['default_timeout']``. None means no
      timeout.

    Hash returned contains these keys:

    - ``start_date``: unix timestamp of job's start date

    - ``walltime``: job's walltime in seconds
    """
    if timeout == False:
        timeout = g5k_configuration['default_timeout']
    cmd = "oargridstat %i" % oargrid_job_id
    if g5k_configuration['no_ssh_for_local_frontend'] == True:
        process = Process(cmd,
                          timeout = timeout,
                          pty = True)
    else:
        process = SshProcess(Host(local_site),
                             cmd,
                             connexion_params = _get_frontend_connexion_params(frontend_connexion_params),
                             timeout = timeout,
                             pty = True)
    process.run()
    if process.ok():
        job_info = dict()
        start_date_result = re.search("start date : (\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d)", process.stdout(), re.MULTILINE)
        if start_date_result:
            start_date = oar_date_to_unixts(start_date_result.group(1))
            job_info['start_date'] = start_date
        walltime_result = re.search("walltime : (\d+:\d?\d:\d?\d)", process.stdout(), re.MULTILINE)
        if walltime_result:
            walltime = oar_duration_to_seconds(walltime_result.group(1))
            job_info['walltime'] = walltime
        return job_info
    raise Exception, "error retrieving info for oargrid job %i: %s" % (oargrid_job_id, process)

def wait_oargrid_job_start(oargrid_job_id = None, frontend_connexion_params = None, timeout = False):
    """Sleep until an oargrid job's start time.

    :param oargrid_job_id: the oargrid job id.

    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.

    :param timeout: timeout for retrieving. Default is False, which
      means use ``g5k_configuration['default_timeout']``. None means no
      timeout.
    """
    sleep(until = get_oargrid_job_info(oargrid_job_id, frontend_connexion_params, timeout)['start_date'])

def get_oar_job_nodes(oar_job_id = None, site = None, frontend_connexion_params = None, timeout = False):
    """Return an iterable of `Host` containing the hosts of an oar job.

    :param oar_job_id: the oar job id. If None given, will try to get
      it from ``OAR_JOB_ID`` environment variable.

    :param site: the Grid5000 site of the oar job. If None given,
      assume local oar job (only works if run on the local frontend).

    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.

    :param timeout: timeout for retrieving. Default is False, which
      means use ``g5k_configuration['default_timeout']``. None means no
      timeout.
    """
    if timeout == False:
        timeout = g5k_configuration['default_timeout']
    if oar_job_id == None:
        if os.environ.has_key('OAR_JOB_ID'):
            oar_job_id = os.environ['OAR_JOB_ID']
        else:
            raise ValueError, "no oar job id given and no OAR_JOB_ID environment variable found"
    countdown = Timer(timeout)
    wait_oar_job_start(oar_job_id, site, frontend_connexion_params, countdown.remaining())
    cmd = "(oarstat -sj %(oar_job_id)i | grep Running) > /dev/null 2>&1 && oarstat -pj %(oar_job_id)i | oarprint host -f -" % {'oar_job_id': oar_job_id}
    if site == None:
        site = local_site
    if g5k_configuration['no_ssh_for_local_frontend'] == True and site == local_site:
        process = Process(cmd,
                          timeout = countdown.remaining(),
                          pty = True)
    else:
        process = SshProcess(Host(site),
                             cmd,
                             connexion_params = _get_frontend_connexion_params(frontend_connexion_params),
                             timeout = countdown.remaining(),
                             pty = True)
    process.run()
    if process.ok():
        host_addresses = re.findall("(\S+)", process.stdout(), re.MULTILINE)
        return [ Host(host_address) for host_address in host_addresses ]
    raise Exception, "error retrieving nodes list for oar job %i on site %s: %s" % (oar_job_id, site, process)
    
def get_oar_job_subnets(oar_job_id = None, site = None, frontend_connexion_params = None, timeout = False):
    """Return an iterable of IP addresses that OAR assigned to your reservation.

    :param oar_job_id: the oar job id. If None given, will try to get
      it from ``OAR_JOB_ID`` environment variable.

    :param site: the Grid5000 site of the oar job. If None given,
      assume local oar job (only works if run on the local frontend).

    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.

    :param timeout: timeout for retrieving. Default is False, which
      means use ``g5k_configuration['default_timeout']``. None means no
      timeout.
    """
    if timeout == False:
        timeout = g5k_configuration['default_timeout']
    if oar_job_id == None:
        if os.environ.has_key('OAR_JOB_ID'):
            oar_job_id = os.environ['OAR_JOB_ID']
        else:
            raise ValueError, "no oar job id given and no OAR_JOB_ID environment variable found"
    countdown = Timer(timeout)
    wait_oar_job_start(oar_job_id, site, frontend_connexion_params, countdown.remaining())
    # g5k-subnets -i -j $OAR_JOB_ID
    cmd = "(oarstat -sj %(oar_job_id)i | grep Running) > /dev/null 2>&1 && g5k-subnets -i -j %(oar_job_id)i" % {'oar_job_id': oar_job_id}
    if site == None:
        site = local_site
    if g5k_configuration['no_ssh_for_local_frontend'] == True and site == _local_site:
        process = Process(cmd,
                          timeout = countdown.remaining(),
                          pty = True)
    else:
        process = SshProcess(Host(site),
                             cmd,
                             connexion_params = _get_frontend_connexion_params(frontend_connexion_params),
                             timeout = countdown.remaining(),
                             pty = True)
    process.run()
    if process.ok():
        subnet_addresses = re.findall("(\S+)", process.stdout(), re.MULTILINE)
        return subnet_addresses
    raise Exception, "error retrieving IPs list for oar job %i on site %s: %s" % (oar_job_id, site, process)

def get_oargrid_job_nodes(oargrid_job_id, frontend_connexion_params = None, timeout = False):
    """Return an iterable of `Host` containing the hosts of an oargrid job.

    :param oargrid_job_id: the oargrid job id.

    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.

    :param timeout: timeout for retrieving. Default is False, which
      means use ``g5k_configuration['default_timeout']``. None means no
      timeout.
    """
    if timeout == False:
        timeout = g5k_configuration['default_timeout']
    cmd = "oargridstat -wl %i" % oargrid_job_id
    if g5k_configuration['no_ssh_for_local_frontend'] == True:
        process = Process(cmd,
                          timeout = timeout,
                          pty = True)
    else:
        process = SshProcess(Host(local_site,
                                  cmd,
                                  connexion_params = _get_frontend_connexion_params(frontend_connexion_params),
                                  timeout = timeout,
                                  pty = True))
    process.run()
    if process.ok():
        host_addresses = re.findall("(\S+)", process.stdout(), re.MULTILINE)
        return [ Host(host_address) for host_address in host_addresses ]
    raise Exception, "error retrieving nodes list for oargrid job %i: %s" % (oargrid_job_id, process)

def kadeploy(deployment, out = False, frontend_connexion_params = None, timeout = None):
    """Deploy hosts with kadeploy3.

    :param deployment: instance of Deployment class describing the
      intended kadeployment.

    :param out: if True, output kadeploy stdout / stderr to stdout.

    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.

    :param timeout: deployment timeout. None (which is the default
      value) means no timeout.

    Returns a tuple (iterable of `Host` containing the deployed host,
    iterable of `Host` containing the nodes not deployed).
    """
    kadeployer = Kadeployer(deployment,
                            out = out,
                            frontend_connexion_params = frontend_connexion_params,
                            timeout = timeout).run()
    if kadeployer.error():
        logoutput = style("deployment failed:", 'emph') + " %s\n" % (kadeployer,) + style("kadeploy processes:\n", 'emph')
        for p in kadeployer.processes():
            logoutput += "%s\n" % (p,)
            logoutput += style("stdout:", 'emph') + "\n%s\n" % (p.stdout())
            logoutput += style("stderr:", 'emph') + "\n%s\n" % (p.stderr())
        logger.error(logoutput)
    return (kadeployer.get_deployed_hosts(), kadeployer.get_error_hosts())

def deploy(deployment,
           check_deployed_command = True,
           node_connexion_params = None,
           num_tries = 2,
           check_enough_func = None,
           out = False,
           frontend_connexion_params = None,
           deploy_timeout = None,
           check_timeout = 30,
           timeout = False):
    """Deploy nodes, many times if needed, checking which of these nodes are already deployed with a user-supplied command. If no command given for checking if nodes deployed, rely on kadeploy to know which nodes are deployed.

    - loop `num_tries` times:

      - if `check_deployed_command` given, try to connect to these
        hosts using the supplied `connexion_params` (or the default
        ones), and to execute `check_deployed_command`. If connexion
        succeeds and the command returns 0, the host is assumed to be
        deployed, else it is assumed to be undeployed.

      - optionnaly call user-supplied ``check_enough_func``, passing
        to it the list of deployed and undeployed hosts, to let user
        code decide if enough nodes deployed. Otherwise, try as long
        as there are undeployed nodes.

      - deploy the undeployed nodes

    returns a tuple with the list of deployed hosts and the list of
    undeployed hosts.

    :param deployment: instance of Deployment class describing the
      intended kadeployment.

    :param check_deployed_command: command to perform remotely to
      check node deployement. May be a String, True, False or None. If
      String: the actual command to be used (This command should
      return 0 if the node is correctly deployed, or another value
      otherwise). If True, the default command value will be used
      (from `g5k_configuration`). If None or False, no check is made
      and deployed/undeployed status will be taken from kadeploy's
      output.

    :param node_connexion_params: a dict similar to
      `execo.default_connexion_params` whose values will override
      those in `execo.default_connexion_params` when connecting to
      check node deployment with ``check_deployed_command`` (see
      below).

    :param num_tries: number of deploy tries

    :param check_enough_func: a function taking as parameter a list of
      deployed hosts and a list of undeployed hosts, which will be
      called at each deployment iteration end, and that should return
      a boolean indicating if there is already enough nodes (in this
      case, no further deployement will be attempted).

    :param out: if True, output kadeploy stdout / stderr to stdout.

    :param frontend_connexion_params: connexion params for connecting
      to sites' frontends if needed. Values override those in
      `default_frontend_connexion_params`.

    :param deploy_timeout: timeout for deployement. Default is None,
      which means no timeout.

    :param check_timeout: timeout for node deployment checks. Default
      is 30 seconds.

    :param timeout: timeout for g5k operations, except deployment.
      Default is False, which means use
      ``g5k_configuration['default_timeout']``. None means no timeout.
    """

    if timeout == False:
        timeout = g5k_configuration['default_timeout']

    if check_enough_func == None:
        check_enough_func = lambda deployed, undeployed: len(undeployed) == 0

    if check_deployed_command == True:
        check_deployed_command = g5k_configuration['check_deployed_command']

    def check_update_deployed(deployed_hosts, undeployed_hosts, check_deployed_command, node_connexion_params):
        logger.info(style("check which hosts are already deployed among:", 'emph') + " %s" % (undeployed_hosts,))
        deployed_check = Remote(undeployed_hosts,
                                check_deployed_command,
                                connexion_params = node_connexion_params,
                                ignore_exit_code = True,
                                ignore_timeout = True,
                                ignore_error = True,
                                timeout = check_timeout)
        deployed_check.run()
        newly_deployed = list()
        for process in deployed_check.processes():
            logger.debug(style("check on %s:" % (process.host(),), 'emph')
                         + " %s\n" % (process,)
                         + style("stdout:", 'emph') + "\n%s\n" % (process.stdout())
                         + style("stderr:", 'emph') + "\n%s\n" % (process.stderr()))
            if (process.exit_code() == 0
                and process.error() == False
                and process.timeouted() == False):
                newly_deployed.append(process.host())
                logger.info("OK %s" % process.host())
            else:
                logger.info("KO %s" % process.host())
        return newly_deployed

    start_time = time.time()
    deployed_hosts = set()
    undeployed_hosts = get_hosts_set(deployment.hosts)
    my_newly_deployed = None
    if check_deployed_command:
        my_newly_deployed = check_update_deployed(deployed_hosts, undeployed_hosts, check_deployed_command, node_connexion_params)
        deployed_hosts.update(my_newly_deployed)
        undeployed_hosts.difference_update(my_newly_deployed)
    num_tries_done = 0
    elapsed = time.time() - start_time
    last_time = time.time()
    deploy_stats = list() # contains tuples ( timestamp,
                          #                   num attempted deploys,
                          #                   len(kadeploy_newly_deployed),
                          #                   len(my_newly_deployed),
                          #                   len(deployed_hosts),
                          #                   len(undeployed_hosts )
    deploy_stats.append((elapsed, None, None, len(my_newly_deployed), len(deployed_hosts), len(undeployed_hosts)))
    while (not check_enough_func(deployed_hosts, undeployed_hosts)
           and num_tries_done < num_tries):
        num_tries_done += 1
        logger.info(style("try %i, deploying on:" % (num_tries_done,), 'emph') + " %s" % (undeployed_hosts,))
        tmp_deployment = copy.copy(deployment)
        tmp_deployment.hosts = undeployed_hosts
        (kadeploy_newly_deployed, kadeploy_error_hosts) = kadeploy(tmp_deployment,
                                                                   out = out,
                                                                   frontend_connexion_params = frontend_connexion_params,
                                                                   timeout = deploy_timeout)
        my_newly_deployed = None
        if check_deployed_command:
            my_newly_deployed = check_update_deployed(deployed_hosts, undeployed_hosts, check_deployed_command, node_connexion_params)
            deployed_hosts.update(my_newly_deployed)
            undeployed_hosts.difference_update(my_newly_deployed)
        else:
            deployed_hosts.update(kadeploy_newly_deployed)
            undeployed_hosts.difference_update(kadeploy_newly_deployed)
        logger.info(style("kadeploy reported newly deployed hosts:", 'emph') + "   %s" % (kadeploy_newly_deployed,))
        logger.info(style("check reported newly deployed hosts:", 'emph') + "   %s" % (my_newly_deployed,))
        logger.info(style("all deployed hosts:", 'emph') + "     %s" % (deployed_hosts,))
        logger.info(style("still undeployed hosts:", 'emph') + " %s" % (undeployed_hosts,))
        elapsed = time.time() - last_time
        last_time = time.time()
        deploy_stats.append((elapsed,
                             len(tmp_deployment.hosts),
                             len(kadeploy_newly_deployed),
                             len(my_newly_deployed),
                             len(deployed_hosts),
                             len(undeployed_hosts)))

    logger.info(style("deploy finished", 'emph') + " in %i tries, %s" % (num_tries_done, format_seconds(time.time() - start_time)))
    logger.info("deploy  duration  attempted  deployed     deployed     total     total")
    logger.info("                  deploys    as reported  as reported  already   still")
    logger.info("                             by kadeploy  by check     deployed  undeployed")
    logger.info("---------------------------------------------------------------------------")
    for (deploy_index, deploy_stat) in enumerate(deploy_stats):
        logger.info("#%-5.5s  %-8.8s  %-9.9s  %-11.11s  %-11.11s  %-8.8s  %-10.10s" % (deploy_index,
                                                                                       format_seconds(deploy_stat[0]),
                                                                                       deploy_stat[1],
                                                                                       deploy_stat[2],
                                                                                       deploy_stat[3],
                                                                                       deploy_stat[4],
                                                                                       deploy_stat[5]))
    logger.info(style("deployed hosts:", 'emph') + " %s" % (deployed_hosts,))
    logger.info(style("undeployed hosts:", 'emph') + " %s" % (undeployed_hosts,))

    return (deployed_hosts, undeployed_hosts)
