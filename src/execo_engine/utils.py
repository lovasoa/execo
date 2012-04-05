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

import itertools, threading, os, cPickle
from log import logger

class HashableDict(dict):

    """Hashable dictionnary. Beware: must not mutate it after its first use as a key."""

    def __key(self):
        return tuple((k,self[k]) for k in sorted(self))

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return other and self.__key() == other.__key()

class sweeps(object):
    
    """Iterable over all possible combinations of parameters.
    
    Given a a directory associating parameters and the list of their
    values, will iterate over the cartesian product of all parameters
    combinations. For example:
    
    >>> ps = sweeps({
    ...   "param1": [ 0, 1 ],
    ...   "param2": [ "a", "b", "c" ]
    ...   })
    >>> list(ps)
    [{'param2': 'a', 'param1': 0}, {'param2': 'a', 'param1': 1}, {'param2': 'b', 'param1': 0}, {'param2': 'b', 'param1': 1}, {'param2': 'c', 'param1': 0}, {'param2': 'c', 'param1': 1}]
    """

    def __init__(self, parameters):
        self.parameters = parameters

    def __iter__(self):
        return ( HashableDict(zip(self.parameters.keys(), values)) for
                 values in itertools.product(*self.parameters.values()) )

class ParamSweeper(object):

    """Threadsafe and persistent iteration over parameter combinations."""

    def __init__(self, persistence_file, name = None):
        self.__lock = threading.RLock()
        self.__done = set()
        self.__inprogress = set()
        self.__done_file = persistence_file
        self.__name = name
        if not self.__name:
            self.__name = os.path.basename(self.__done_file)
        if os.path.isfile(self.__done_file):
            with open(self.__done_file, "r") as done_file:
                self.__done = cPickle.load(done_file)

    def __remaining(self, parameters):
        return frozenset(sweeps(parameters)).difference(self.__done).difference(self.__inprogress)

    def get_next(self, parameters):
        with self.__lock:
            try:
                xp = iter(self.__remaining(parameters)).next()
                self.__inprogress.add(xp)
                logger.info(
                    "%s new xp: %s. %i remaining, %i in progress, %i total",
                        self.__name, xp,
                        self.num_remaining(parameters),
                        len(self.__inprogress),
                        len(list(sweeps(parameters))))
                return xp
            except StopIteration:
                logger.info(
                    "%s no new xp. %i remaining, %i in progress, %i total",
                        self.__name,
                        self.num_remaining(parameters),
                        len(self.__inprogress),
                        len(list(sweeps(parameters))))
                return None

    def done(self, xp):
        with self.__lock:
            self.__done.add(xp)
            self.__inprogress.discard(xp)
            logger.info("%s xp done: %s",
                self.__name, xp)
            with open(self.__done_file, "w") as done_file:
                cPickle.dump(self.__done, done_file)

    def reset(self):
        with self.__lock:
            logger.info("%s reset", self.__name)
            self.__inprogress.clear()

    def num_remaining(self, parameters):
        with self.__lock:
            return len(self.__remaining(parameters))

    def num_total(self, parameters):
        return len(ParamSweeper(parameters))
