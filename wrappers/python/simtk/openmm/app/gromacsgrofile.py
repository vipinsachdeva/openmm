"""
grofile.py: Used for loading Gromacs GRO files.

This is part of the OpenMM molecular simulation toolkit originating from
Simbios, the NIH National Center for Physics-Based Simulation of
Biological Structures at Stanford, funded under the NIH Roadmap for
Medical Research, grant U54 GM072970. See https://simtk.org.

Portions copyright (c) 2012 Stanford University and the Authors.
Authors: Lee-Ping Wang, Peter Eastman
Contributors:

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS, CONTRIBUTORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
__author__ = "Lee-Ping Wang"
__version__ = "1.0"

import os
import sys
from simtk.openmm import Vec3
from re import sub, match
from simtk.unit import nanometers, angstroms, Quantity
import element as elem
try:
    import numpy
except:
    pass

def _isint(word):
    """ONLY matches integers! If you have a decimal point? None shall pass!

    @param[in] word String (for instance, '123', '153.0', '2.', '-354')
    @return answer Boolean which specifies whether the string is an integer (only +/- sign followed by digits)

    """
    return match('^[-+]?[0-9]+$',word)

def _isfloat(word):
    """Matches ANY number; it can be a decimal, scientific notation, what have you
    CAUTION - this will also match an integer.

    @param[in] word String (for instance, '123', '153.0', '2.', '-354')
    @return answer Boolean which specifies whether the string is any number

    """
    return match('^[-+]?[0-9]*\.?[0-9]*([eEdD][-+]?[0-9]+)?$',word)

def _is_gro_coord(line):
    """ Determines whether a line contains GROMACS data or not

    @param[in] line The line to be tested

    """
    sline = line.split()
    if len(sline) == 6 or len(sline) == 9:
        return all([_isint(sline[2]), _isfloat(sline[3]), _isfloat(sline[4]), _isfloat(sline[5])])
    elif len(sline) == 5 or len(sline) == 8:
        return all([_isint(line[15:20]), _isfloat(sline[2]), _isfloat(sline[3]), _isfloat(sline[4])])
    else:
        return 0

def _is_gro_box(line):
    """ Determines whether a line contains a GROMACS box vector or not

    @param[in] line The line to be tested

    """
    sline = line.split()
    if len(sline) == 9 and all([_isfloat(i) for i in sline]):
        return 1
    elif len(sline) == 3 and all([_isfloat(i) for i in sline]):
        return 1
    else:
        return 0

class GromacsGroFile(object):
    """GromacsGroFile parses a Gromacs .gro file and constructs a set of atom positions from it.

    A .gro file also contains some topological information, such as elements and residue names,
    but not enough to construct a full Topology object.  This information is recorded and stored
    in the object's public fields."""

    def __init__(self, file):
        """Load a .gro file.

        The atom positions can be retrieved by calling getPositions().

        Parameters:
         - file (string) the name of the file to load
        """

        xyzs     = []
        elements = [] # The element, most useful for quantum chemistry calculations
        atomname = [] # The atom name, for instance 'HW1'
        comms    = []
        resid    = []
        resname  = []
        boxes    = []
        xyz      = []
        ln       = 0
        frame    = 0
        for line in open(file):
            if ln == 0:
                comms.append(line.strip())
            elif ln == 1:
                na = int(line.strip())
            elif _is_gro_coord(line):
                if frame == 0: # Create the list of residues, atom names etc. only if it's the first frame.
                    (thisresnum, thisresname, thisatomname, thisatomnum) = [line[i*5:i*5+5].strip() for i in range(4)]
                    resname.append(thisresname)
                    resid.append(int(thisresnum))
                    atomname.append(thisatomname)
                    thiselem = thisatomname
                    if len(thiselem) > 1:
                        thiselem = thiselem[0] + sub('[A-Z0-9]','',thiselem[1:])
                        try:
                            elements.append(elem.get_by_symbol(thiselem))
                        except KeyError:
                            elements.append(None)
                pos = [float(line[20+i*8:28+i*8]) for i in range(3)]
                xyz.append(Vec3(pos[0], pos[1], pos[2]))
            elif _is_gro_box(line) and ln == na + 2:
                sline = line.split()
                boxes.append(tuple([float(i) for i in sline])*nanometers)
                xyzs.append(xyz*nanometers)
                xyz = []
                ln = -1
                frame += 1
            else:
                raise Exception("Unexpected line in .gro file: "+line)
            ln += 1

        ## The atom positions read from the file.  If the file contains multiple frames, these are the positions in the first frame.
        self.positions = xyzs[0]
        ## A list containing the element of each atom stored in the file
        self.elements = elements
        ## A list containing the name of each atom stored in the file
        self.atomNames = atomname
        ## A list containing the ID of the residue that each atom belongs to
        self.residueIds = resid
        ## A list containing the name of the residue that each atom belongs to
        self.residueNames = resname
        self._positions = xyzs
        self._unitCellDimensions = boxes
        self._numpyPositions = None

    def getNumFrames(self):
        """Get the number of frames stored in the file."""
        return len(self._positions)

    def getPositions(self, asNumpy=False, frame=0):
        """Get the atomic positions.

        Parameters:
         - asNumpy (boolean=False) if true, the values are returned as a numpy array instead of a list of Vec3s
         - frame (int=0) the index of the frame for which to get positions
         """
        if asNumpy:
            if self._numpyPositions is None:
                self._numpyPositions = [None]*len(self._positions)
            if self._numpyPositions[frame] is None:
                self._numpyPositions[frame] = Quantity(numpy.array(self._positions[frame].value_in_unit(nanometers)), nanometers)
            return self._numpyPositions[frame]
        return self._positions[frame]

    def getUnitCellDimensions(self, frame=0):
        """Get the dimensions of the crystallographic unit cell.

        Parameters:
         - frame (int=0) the index of the frame for which to get the unit cell dimensions
        """
        return self._unitCellDimensions[frame]
