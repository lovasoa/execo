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
from tempfile import mkstemp
from execo import logger, SshProcess, Process, Put
from execo.log import style


def munin_server(server, clients, plugins = [ 'cpu', 'memory', 'iostat']):
    """Install the monitoring service munin. Must be executed inside Grid'5000
    to be able to resolve the server and clients IP.
    
    :param server: a execo.Host
    
    :param clients: a list of execo.Hosts
    
    :param plugins: a list of munin plugins
    
    """
    logger.info('Munin monitoring service installation, server = %s, clients = \n %s',
                server.address, [host.address for host in clients])
    
    logger.debug('Creating configuration files for server')
    _, server_conf = mkstemp(dir = '/tmp/', prefix='munin-nodes_')
    f = open(server_conf, 'w')
    for host in clients:
        get_ip = Process('host '+host.address).run()
        ip =  get_ip.stdout.strip().split(' ')[3]
        f.write('['+host.address+']\n    address '+ip+'\n   use_node_name yes\n\n')
    f.close()
            
    logger.debug('Configuring munin server %s', style.host('server'))
    cmd = 'export DEBIAN_MASTER=noninteractive ; apt-get update && apt-get install -y munin'
    inst_munin_server = SshProcess(cmd, server).run()


def get_munin_stats(server, destination_directory = '.'):
    """Retrieve the munin statistics """
    logger.error('Not implemented')
    
    
def add_munin_plugin(plugin, host):
    """ """