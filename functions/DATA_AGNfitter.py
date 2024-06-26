"""%%%%%%%%%%%%%%%%%

        DATA_AGNFitter.py

%%%%%%%%%%%%%%%%%%

This script contains the class DATA, 
which administrate the catalog properties given by the user props(). 
It also helps transporting
the main information on the dictionaries (DICTS).
"""
import sys,os
import numpy as np
import pandas as pd
from math import pi, sqrt
from scipy.interpolate import interp1d
from astropy import units as u
from astropy.table import Table
import functions.MODEL_AGNfitter as model  
import decimal


class DATA_all:

    """
    Class DATA_all
    ---------------
    Object with data info for the total catalog.
    It reads and processes all information about the catalog.
    It returns arrays with all important values (sourcenames, redhisft, etc)
    and gives it to the class DATA, which administrates it for each sourceline.
    
    input: catalogname

    """

    def __init__(self, cat, filters):
        self.cat = cat
        self.filters = filters
        self.catalog = cat['filename']
        if not os.path.lexists(cat['filename']):
            print ('ERROR: Catalog does not exist under this name '+cat['filename'])
            sys.exit(1)
        self.path = cat['path']
        self.output_folder = cat['output_folder']

    def PROPS(self):

        if self.cat['filetype'] == 'ASCII': 

            ### read catalog columns
            # It's necessary to read redshift as decimal.Decimal object because of the representation as a binary floating point number 
            # (python add digits to some values of z)
            column = pd.read_csv(self.catalog, sep='\s+', decimal=".", skiprows = 0, converters = {'z':decimal.Decimal}) 

            ### properties
            self.name = column.iloc[:, self.cat['name']]
            self.z = [float(i) for i in column.iloc[:, self.cat['redshift']]]
            self.dlum = np.array(model.z2Dlum(self.z))
            
            if self.cat['use_central_wavelength']:
                ### If central wavelengths are *not* given in catalog and need to be extracted automatically from chosen filters. 

                ### read all wavelengths, fluxes, fluerrors, flags                
                names = np.loadtxt(self.cat['path'] + 'models/FILTERS/ALL_FILTERS_info.dat', delimiter = '|', usecols=[1], skiprows = 1, dtype=str)
                centralwls = np.loadtxt(self.cat['path'] + 'models/FILTERS/ALL_FILTERS_info.dat', delimiter = '|', usecols=[3], skiprows = 1)

                dictionary = self.filters.copy()
                
                del dictionary['dict_zarray'];
                del dictionary['add_filters_dict'];
                del dictionary['add_filters'];
                del dictionary['path'];

                list_centralwls = []
                for i in range(len(list(dictionary.keys()))):

                    for j in range(len(names)):
                        try:
                            ### The filter dictionary need to have to entries [True/False, column_number]
                            if list(dictionary.keys())[i] == names[j] and dictionary[list(dictionary.keys())[i]][0]:
                                list_centralwls.append([ dictionary[list(dictionary.keys())[i]][1], centralwls[j]])
                        except:
                            print (list(dictionary.keys())[i], 'not in list')

                def getkeynumber(item):
                    return item[0]

                sortedwl = sorted(list_centralwls, key=getkeynumber)
                sortedwl = np.asarray(sortedwl)
                centr_wl = sortedwl[:,1]
                if self.cat['freq/wl_format'] == 'wavelength':
                    ### given in log freq but inverse order (wavelength order)
                    freq_wl_cat_ALL = centr_wl 
                elif self.cat['freq/wl_format'] == 'frequency':
                    freq_wl_cat_ALL = centr_wl[::-1]
            else:
                ### If central wavelengths are given in catalog with itw own order
                freq_wl_cat_ALL = \
                    np.array([column.iloc[:, c] for c in self.cat['freq/wl_list']])* self.cat['freq/wl_unit'] 
            
            flux_cat_ALL =\
                np.array(column.iloc[:, self.cat['flux_list']]).astype(float) *self.cat['flux_unit']
            fluxerr_cat_ALL = \
                np.array(column.iloc[:, self.cat['fluxerr_list']]).astype(float)*self.cat['flux_unit']
            if self.cat['ndflag_bool'] == True: 
                ndflag_cat_ALL = np.array(column.iloc[:, self.cat['ndflag_list']])

            nus_l=[]
            fluxes_l=[]
            fluxerrs_l=[]
            ndflag_l=[]
            nRADdata_l = []
            nXRaysdata_l = []

            nrSOURCES, nrBANDS= np.shape(flux_cat_ALL)
            
            self.cat['nsources'] = nrSOURCES

            ##Convert to right units but give back just values
            for j in range(nrSOURCES):
                
                if self.cat['use_central_wavelength']:
                    freq_wl_cat = freq_wl_cat_ALL                    
                
                else:
                    freq_wl_cat = freq_wl_cat_ALL[:,j]
                
                flux_cat= flux_cat_ALL[j]
                fluxerr_cat= fluxerr_cat_ALL[j]

                if self.cat['use_central_wavelength']:
                    nus0 = freq_wl_cat
                    
                else:
                    if self.cat['freq/wl_format']== 'frequency' :
                        nus0 = np.log10(freq_wl_cat.to(u.Hz).value)
                    if self.cat['freq/wl_format']== 'wavelength' :
                        nus0 = np.log10(freq_wl_cat.to(u.Hz, equivalencies=u.spectral()).value)

                fluxes0 = np.array(flux_cat.to(u.erg/ u.s/ (u.cm)**2 / u.Hz).value)
                fluxerrs0 = np.array(fluxerr_cat.to(u.erg/ u.s/(u.cm)**2/u.Hz).value)
                
                ## If columns with flags exist
                if self.cat['ndflag_bool'] == True: 
                    ndflag_cat0 = ndflag_cat_ALL[:,j]     
                    # If fluxerrs0 are not given (-99), we assume flux is an upper limit for a non detection.
                    # Upper limit flux is then represented for the fitting
                    # with a data point at uppflux/2, and an error of +- uppflux/2
                    # implying an uncertanty that ranges from [0,uppflux]  
                    units_flags = self.cat['flux_unit'].value
                    ndflag_cat0[fluxerr_cat.value/units_flags<=-99]= 0.                                 
                    fluxes0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]= \
                             fluxes0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]*0.5
                    fluxerrs0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]= \
                               fluxes0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]

                ## If NO columns with flags exist
                elif self.cat['ndflag_bool'] == False:
                    ndflag_cat0 = np.ones(np.shape(fluxes0))
                    # If fluxerrs0 are not given (-99), we assume flux is an upper limit for a non detection.
                    # Upper limit flux is then represented for the fitting
                    # with a data point at uppflux/2, and an error of +- uppflux/2
                    # implying an uncertanty that ranges from [0,uppflux]
                    units_flags = self.cat['flux_unit'].value
                    ndflag_cat0[fluxerr_cat.value/units_flags<=-99]= 0.
                    fluxes0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]=\
                             fluxes0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]*0.5
                    fluxerrs0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]= \
                              fluxes0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]
                    # If neither fluxes and fluxerrs are given (both -99), 
                    # these are considered as a non existant data point.

                if self.cat['err+10%flux_moreflex'] == True:  
                    ## It's a option to add in quadrature a 10% of the flux to the measurement error in order to increase the flexibility of the fit
                    fluxerrs0[ndflag_cat0 != 0] = np.sqrt(fluxerrs0[ndflag_cat0 != 0]**2 + (fluxes0[ndflag_cat0 != 0]*0.1)**2)


                ## Sort in order of frequency
                nus_l.append(nus0[nus0.argsort()])
                fluxes_l.append(fluxes0[nus0.argsort()])
                fluxerrs_l.append(fluxerrs0[nus0.argsort()])
                ndflag_l.append(ndflag_cat0[nus0.argsort()])

                ## Evaluate the number of valid radio data. This information will be important to choose a AGN radio model
                RADdata_pos = nus0[nus0.argsort()] < (10.5-np.log10(1+self.z[j]))        # < 30 GHz rest frame
                RADdata = fluxes0[nus0.argsort()][(RADdata_pos == True) & (ndflag_cat0[nus0.argsort()] > 0)]
                nRADdata_l.append(len(RADdata))

                ## Evaluate the number of valid Xrays data. This information will be important to choose the model
                XRdata_pos = nus0[nus0.argsort()] > (16.685-np.log10(1+self.z[j]))        # > 0.2 keV rest frame
                XRdata = fluxes0[nus0.argsort()][(XRdata_pos == True) & (ndflag_cat0[nus0.argsort()] > 0)]
                nXRaysdata_l.append(len(XRdata))

            self.nus = np.array(nus_l)
            self.fluxes = np.array(fluxes_l)
            self.fluxerrs = np.array(fluxerrs_l)
            self.ndflag = np.array(ndflag_l)
            self.nRADdata = np.array(nRADdata_l)
            self.nXRaysdata = np.array(nXRaysdata_l)

        elif self.cat['filetype'] == 'FITS': 

            #read all columns
            fitstable = Table.read(self.catalog)

            #properties
            self.name = fitstable[self.cat['name']].astype(int)
            self.z = fitstable[self.cat['redshift']].astype(float)
            self.dlum = np.array([model.z2Dlum(z) for z in self.z])

            if self.cat['use_central_wavelength']:
                ### If central wavelengths are *not* given in catalog and need to be extracted automatically from chosen filters. 

                ### read all wavelengths, fluxes, fluerrors, flags                
                names = np.loadtxt(self.cat['path'] + 'models/FILTERS/ALL_FILTERS_info.dat', delimiter = '|', usecols=[1], skiprows = 1, dtype=str)
                centralwls = np.loadtxt(self.cat['path'] + 'models/FILTERS/ALL_FILTERS_info.dat', delimiter = '|', usecols=[3], skiprows = 1)

                dictionary = self.filters.copy()
                
                del dictionary['dict_zarray'];
                #del dictionary['order'];
                del dictionary['add_filters_dict'];
                del dictionary['add_filters'];
                del dictionary['path'];

                list_centralwls = []
                for i in range(len(dictionary.keys())):

                    for j in range(len(names)):
                        try:
                            ### The filter dictionary need to have to entries [True/False, column_number]
                            if dictionary.keys()[i] == names[j] and dictionary[dictionary.keys()[i]][0]:
                                list_centralwls.append([ dictionary[dictionary.keys()[i]][1], centralwls[j]])
                        except:
                            print (dictionary.keys()[i], 'not in list')

                def getkeynumber(item):
                    return item[0]

                sortedwl = sorted(list_centralwls, key=getkeynumber)
                sortedwl = np.asarray(sortedwl)
                centr_wl = sortedwl[:,1]
                freq_wl_cat_ALL = centr_wl # These are in 10log frequency!

            else:

                #read all wavelengths, fluxes, fluerrors, flags
                colnames = fitstable.dtype.names
                wl_cols = [ c for c in colnames if self.cat['freq/wl_suffix'] in c]
                flux_cols = [ c for c in colnames if self.cat['flux_suffix'] in c]
                flux_err_cols = [ c for c in colnames if self.cat['fluxerr_suffix'] in c]

                freq_wl_cat_ALL = \
                                np.array([fitstable[c] for c in wl_cols])* self.cat['freq/wl_unit'] 
            flux_cat_ALL =\
                np.array([fitstable[ca] for ca in  flux_cols ]).astype(float)*self.cat['flux_unit']
            fluxerr_cat_ALL = \
                np.array([fitstable[ce] for ce in flux_err_cols ]).astype(float)*self.cat['flux_unit']
            if self.cat['ndflag_bool'] == True: 
                ndflag_cat_ALL = np.array(fitstable[self.cat['ndflag_list']])

            nus_l=[]
            fluxes_l=[]
            fluxerrs_l=[]
            ndflag_l=[]
            nRADdata_l = []

            nrBANDS, nrSOURCES= np.shape(flux_cat_ALL)

            self.cat['nsources'] = nrSOURCES
            
            ##Convert to right units but give back just values
            for j in range(nrSOURCES):
            
                freq_wl_cat= freq_wl_cat_ALL[:,j]
                flux_cat= flux_cat_ALL[:,j]
                fluxerr_cat= fluxerr_cat_ALL[:,j]

                if self.cat['freq/wl_format']== 'frequency' :
                    nus0 = np.log10(freq_wl_cat.to(u.Hz).value)
                if self.cat['freq/wl_format']== 'wavelength' :
                    nus0 = np.log10(freq_wl_cat.to(u.Hz, equivalencies=u.spectral()).value)

                fluxes0 = np.array(flux_cat.to(u.erg/ u.s/ (u.cm)**2 / u.Hz).value)
                fluxerrs0 = np.array(fluxerr_cat.to(u.erg/ u.s/(u.cm)**2/u.Hz).value)

                ## If columns with flags exist
                if self.cat['ndflag_bool'] == True: 
                    ndflag_cat0 = ndflag_cat_ALL[:,j]     
                    # If fluxerrs0 are not given (-99), we assume flux is an upper limit for a non detection.
                    # Upper limit flux is then represented for the fitting
                    # with a data point at uppflux/2, and an error of +- uppflux/2
                    # implying an uncertanty that ranges from [0,uppflux]  
                    units_flags = self.cat['flux_unit'].value
                    ndflag_cat0[flux_cat.value/units_flags<=-99]= 0.                                 
                    fluxes0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]=\
                            fluxes0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]*0.5
                    fluxerrs0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]=\
                            fluxes0 [(fluxerr_cat.value/units_flags<=-99)&(flux_cat/units_flags.value>-99)]

                ## If NO columns with flags exist
                elif self.cat['ndflag_bool'] == False:

                    ndflag_cat0 = np.ones(np.shape(fluxes0))
                    # If fluxerrs0 are not given (-99), we assume flux is an upper limit for a non detection.
                    # Upper limit flux is then represented for the fitting
                    # with a data point at uppflux/2, and an error of +- uppflux/2
                    # implying an uncertanty that ranges from [0,uppflux]  
                    units_flags = self.cat['flux_unit'].value
                    ndflag_cat0[flux_cat.value/units_flags<=-99]= 0.
                    fluxes0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]=\
                            fluxes0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]*0.5
                    fluxerrs0[(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]=\
                            fluxes0 [(fluxerr_cat.value/units_flags<=-99)&(flux_cat.value/units_flags>-99)]

                    # If neither fluxes and fluxerrs are given (both -99), 
                    # these are considered as a non existant data point.

                ## Sort in order of frequency
                nus_l.append(nus0[nus0.argsort()])
                fluxes_l.append(fluxes0[nus0.argsort()])
                fluxerrs_l.append(fluxerrs0[nus0.argsort()])
                ndflag_l.append(ndflag_cat0[nus0.argsort()])

                ## Evaluate the number of valid radio data. This information will be important to choose a AGN radio model
                RADdata_pos = nus0[nus0.argsort()] < (10.5-np.log10(1+self.z[j]))        # < 30 GHz rest frame
                RADdata = fluxes0[nus0.argsort()][(RADdata_pos == True) & (ndflag_cat0[nus0.argsort()] > 0)]
                nRADdata_l.append(len(RADdata))

                ## Evaluate the number of valid Xrays data. This information will be important to choose the model
                XRdata_pos = nus0[nus0.argsort()] < (16.685-np.log10(1+self.z[j]))        # > 0.2 keV rest frame
                XRdata = fluxes0[nus0.argsort()][(XRdata_pos == True) & (ndflag_cat0[nus0.argsort()] > 0)]
                nXRaysdata_l.append(len(XRdata))


            self.nus = np.array(nus_l)
            self.fluxes = np.array(fluxes_l)
            self.fluxerrs = np.array(fluxerrs_l)
            self.ndflag = np.array(ndflag_l)
            self.nRADdata = np.array(nRADdata_l)
            self.nXRaysdata = np.array(nXRaysdata_l)

class DATA():

    """
    Class DATA
    ----------
    Object with data info for once source.
    It recieves the catalog information obtained from 
    object from class DATA_all and administrates it for each sourceline.

    input: object of class DATA_all, sourceline

    """

    def __init__(self, data_all, line):

        catalog = data_all
        self.nus = catalog.nus[line]
        self.fluxes = catalog.fluxes[line]
        self.fluxerrs = catalog.fluxerrs[line]
        self.ndflag = catalog.ndflag[line]
        self.name = catalog.name[line]
        self.z =catalog.z[line]
        self.dlum = catalog.dlum[line]
        self.lumfactor = 4. * pi * catalog.dlum[line] **2.
        self.nRADdata = catalog.nRADdata[line]
        self.nXRaysdata = catalog.nXRaysdata[line]

        self.cat = catalog.cat
        #self.sourceline = sourceline
        self.catalog = catalog.cat['filename']
        if not os.path.lexists(catalog.cat['filename']):
            print ('Catalog does not exist under this name.')
        self.path = catalog.cat['path']
        self.output_folder = catalog.cat['output_folder']

