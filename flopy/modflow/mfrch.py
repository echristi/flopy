"""
mfrch module.  Contains the ModflowRch class. Note that the user can access
the ModflowRch class as `flopy.modflow.ModflowRch`.

Additional information for this MODFLOW package can be found at the `Online
MODFLOW Guide
<http://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/index.html?rch.htm>`_.

"""

import sys
import numpy as np
from flopy.mbase import Package
from flopy.utils import util_2d
from flopy.utils.util_array import transient_2d
from flopy.modflow.mfparbc import ModflowParBc as mfparbc

class ModflowRch(Package):
    """
    MODFLOW Recharge Package Class.

    Parameters
    ----------
    model : model object
        The model object (of type :class:`flopy.modflow.mf.Modflow`) to which
        this package will be added.
    ipakcb : int
        is a flag and a unit number. (the default is 0).
    nrchop : int
        is the recharge option code. 
        1: Recharge to top grid layer only
        2: Recharge to layer defined in irch
        3: Recharge to highest active cell (default is 3).
    rech : float or array of floats (nrow, ncol)
        is the recharge flux. (default is 1.e-3).
    irch : int or array of ints (nrow, ncol)
        is the layer to which recharge is applied in each vertical
        column (only used when nrchop=2). (default is 0).
    extension : string
        Filename extension (default is 'rch')
    unitnumber : int
        File unit number (default is 19).

    Attributes
    ----------

    Methods
    -------

    See Also
    --------

    Notes
    -----
    Parameters are supported in Flopy only when reading in existing models.
    Parameter values are converted to native values in Flopy and the
    connection to "parameters" is thus nonexistent.

    Examples
    --------

    >>> import flopy
    >>> m = flopy.modflow.Modflow()
    >>> rch = flopy.modflow.ModflowRch(m, nrchop=3, rech=1.2e-4)

    """
    def __init__(self, model, nrchop=3, ipakcb=0, rech=1e-3, irch=0,
                 extension ='rch', unitnumber=19):
        """
        Package constructor.

        """
        # Call parent init to set self.parent, extension, name and unit number
        Package.__init__(self, model, extension, 'RCH', unitnumber)
        nrow, ncol, nlay, nper = self.parent.nrow_ncol_nlay_nper
        self.heading = '# RCH for MODFLOW, generated by Flopy.'
        self.url = 'rch.htm'
        self.nrchop = nrchop
        self.ipakcb = ipakcb
        self.rech = transient_2d(model, (nrow, ncol), np.float32,
                                 rech, name = "rech_")
        if self.nrchop == 2:
            self.irch = transient_2d(model, (nrow, ncol), np.int,
                                     irch+1, name = "irch_")  # irch+1, as irch is zero based
        else:
            self.irch = None
        self.np = 0
        self.parent.add_package(self)

    def __repr__( self ):
        return 'Recharge class'

    def ncells( self):
        # Returns the  maximum number of cells that have recharge (developed for MT3DMS SSM package)
        nrow, ncol, nlay, nper = self.parent.nrow_ncol_nlay_nper
        return (nrow * ncol)

    def write_file(self):
        """
        Write the file.

        """
        nrow, ncol, nlay, nper = self.parent.nrow_ncol_nlay_nper
        # Open file for writing
        f_rch = open(self.fn_path, 'w')
        f_rch.write('{0:s}\n'.format(self.heading))
        f_rch.write('{0:10d}{1:10d}\n'.format(self.nrchop,self.ipakcb))
        for kper in range(nper):
            inrech, file_entry_rech = self.rech.get_kper_entry(kper)
            if self.nrchop == 2:
                inirch, file_entry_irch = self.irch.get_kper_entry(kper)
            else:
                inirch = -1
            f_rch.write('{0:10d}{1:10d} # {2:s}\n'.format(inrech, 
                        inirch, "Stress period " + str(kper + 1)))
            if (inrech >= 0):
                f_rch.write(file_entry_rech)
            if self.nrchop == 2:
                if inirch >= 0:
                    f_rch.write(file_entry_irch)
        f_rch.close()

    @staticmethod
    def load(f, model, nper=None, ext_unit_dict=None):
        """
        Load an existing package.

        Parameters
        ----------
        f : filename or file handle
            File to load.
        model : model object
            The model object (of type :class:`flopy.modflow.mf.Modflow`) to
            which this package will be added.
        nper : int
            The number of stress periods.  If nper is None, then nper will be
            obtained from the model object. (default is None).
        ext_unit_dict : dictionary, optional
            If the arrays in the file are specified using EXTERNAL,
            or older style array control records, then `f` should be a file
            handle.  In this case ext_unit_dict is required, which can be
            constructed using the function
            :class:`flopy.utils.mfreadnam.parsenamefile`.

        Returns
        -------
        rch : ModflowRch object
            ModflowRch object.

        Examples
        --------

        >>> import flopy
        >>> m = flopy.modflow.Modflow()
        >>> rch = flopy.modflow.ModflowRch.load('test.rch', m)

        """
        if model.verbose:
            sys.stdout.write('loading rch package file...\n')

        if not hasattr(f, 'read'):
            filename = f
            f = open(filename, 'r')
        #dataset 0 -- header
        while True:
            line = f.readline()
            if line[0] != '#':
                break
        npar = 0
        if "parameter" in line.lower():
            raw = line.strip().split()
            npar = np.int(raw[1])
            if npar > 0:
                if model.verbose:
                    print('   Parameters detected. Number of parameters = ', npar)
            line = f.readline()
        #dataset 2
        t = line.strip().split()
        nrchop = int(t[0])
        ipakcb = 0
        try:
            if int(t[1]) != 0:
                model.add_pop_key_list(int(t[1]))
                ipakcb = 53
        except:
            pass

        #--dataset 3 and 4 - parameters data
        pak_parms = None
        if npar > 0:
            pak_parms = mfparbc.loadarray(f, npar, model.verbose)

        if nper is None:
            nrow, ncol, nlay, nper = model.get_nrow_ncol_nlay_nper()
        #read data for every stress period
        rech = {}
        irch = None
        if nrchop == 2:
            irch = {}
        current_rech = []
        current_irch = []
        for iper in range(nper):
            line = f.readline()
            t = line.strip().split()
            inrech = int(t[0])
            if nrchop == 2:
                inirch = int(t[1])
            if inrech >= 0:
                if npar == 0:
                    if model.verbose:
                        print('   loading rech stress period {0:3d}...'.format(iper+1))
                    t = util_2d.load(f, model, (nrow, ncol), np.float32, 'rech', ext_unit_dict)
                else:
                    parm_dict = {}
                    for ipar in range(inrech):
                        line = f.readline()
                        t = line.strip().split()
                        pname = t[0].lower()
                        try:
                            c = t[1].lower()
                            instance_dict = pak_parms.bc_parms[pname][1]
                            if c in instance_dict:
                                iname = c
                            else:
                                iname = 'static'
                        except:
                            iname = 'static'
                        parm_dict[pname] = iname
                    t = mfparbc.parameter_bcfill(model, (nrow, ncol), parm_dict, pak_parms)

                current_rech = t
            rech[iper] = current_rech
            if nrchop == 2:
                if inirch >= 0:
                    if model.verbose:
                        print('   loading irch stress period {0:3d}...'.format(
                            iper+1))
                    t = util_2d.load(f, model, (nrow,ncol), np.int, 'irch',
                                     ext_unit_dict)
                    current_irch = t
                irch[iper] = current_irch
        rch = ModflowRch(model, nrchop=nrchop, ipakcb=ipakcb, rech=rech,
                         irch=irch)
        return rch

