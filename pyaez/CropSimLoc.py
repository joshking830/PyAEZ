"""
PyAEZ version 2.1.0 (June 2023)
This CropSimulation Class simulates all the possible crop cycles to find 
the best crop cycle that produces maximum yield for a particular grid
2020: N. Lakmal Deshapriya
2022/2023: Swun Wunna Htet, Kittiphon Boonma
"""

import numpy as np
import pandas as pd
try:
    import gdal
except:
    from osgeo import gdal

from pyaez import UtilitiesCalc,BioMassCalc,ETOCalc,CropWatCalc,ThermalScreening, LGPCalc

class CropSimLoc(object):

    def __init__(self):
        """Initiate a Class instance
        """        
        self.set_mask = False
        self.set_tclimate_screening = False
        self.set_lgpt_screening = False
        self.set_Tsum_screening = False
        self.set_Permafrost_screening = False  
        self.set_adjustment = False 
        self.setTypeBConstraint = False
        self.set_monthly = False

    def setMonthlyClimateData(self, min_temp, max_temp, precipitation, short_rad, wind_speed, rel_humidity):
        """Load MONTHLY climate data into the Class and calculate the Reference Evapotranspiration (ETo)

        Args:
            min_temp (3D NumPy): Monthly minimum temperature [Celcius]
            max_temp (3D NumPy): Monthly maximum temperature [Celcius]
            precipitation (3D NumPy): Monthly total precipitation [mm/day]
            short_rad (3D NumPy): Monthly solar radiation [W/m2]
            wind_speed (3D NumPy): Monthly windspeed at 2m altitude [m/s]
            rel_humidity (3D NumPy): Monthly relative humidity [percentage decimal, 0-1]
        """
        rel_humidity[rel_humidity > 0.99] = 0.99
        rel_humidity[rel_humidity < 0.05] = 0.05
        short_rad[short_rad < 0] = 0
        wind_speed[wind_speed < 0] = 0
        self.minT_monthly = min_temp
        self.maxT_monthly = max_temp
        self.totalPrec_monthly = precipitation
        self.shortRad_monthly = short_rad
        self.wind2m_monthly = wind_speed
        self.rel_humidity_monthly = rel_humidity
        self.meanT_daily = np.zeros((self.im_height, self.im_width, 365))
        self.totalPrec_daily = np.zeros((self.im_height, self.im_width, 365))
        self.pet_daily = np.zeros((self.im_height, self.im_width, 365))
        self.minT_daily = np.zeros((self.im_height, self.im_width, 365))
        self.maxT_daily = np.zeros((self.im_height, self.im_width, 365))

        # Interpolate monthly to daily data
        obj_utilities = UtilitiesCalc.UtilitiesCalc()

        self.meanT_monthly = 0.5*(min_temp+max_temp)

        for i_row in range(self.im_height):
            for i_col in range(self.im_width):

                if self.set_mask:
                    if self.im_mask[i_row, i_col] == self.nodata_val:
                        continue

                self.meanT_daily[i_row, i_col, :] = obj_utilities.interpMonthlyToDaily(
                    self.meanT_monthly[i_row, i_col, :], 1, 365)
                self.totalPrec_daily[i_row, i_col, :] = obj_utilities.interpMonthlyToDaily(
                    precipitation[i_row, i_col, :], 1, 365, no_minus_values=True)
                self.minT_daily[i_row, i_col, :] = obj_utilities.interpMonthlyToDaily(
                    min_temp[i_row, i_col, :], 1, 365)
                self.maxT_daily[i_row, i_col, :] = obj_utilities.interpMonthlyToDaily(
                    max_temp[i_row, i_col, :], 1, 365)
                radiation_daily = obj_utilities.interpMonthlyToDaily(
                    short_rad[i_row, i_col, :], 1, 365, no_minus_values=True)
                wind_daily = obj_utilities.interpMonthlyToDaily(
                    wind_speed[i_row, i_col, :], 1, 365, no_minus_values=True)
                rel_humidity_daily = obj_utilities.interpMonthlyToDaily(
                    rel_humidity[i_row, i_col, :], 1, 365, no_minus_values=True)

                # calculation of reference evapotranspiration (ETo)
                obj_eto = ETOCalc.ETOCalc(
                    1, 365, self.latitude[i_row, i_col], self.elevation[i_row, i_col])
                # convert w/m2 to MJ/m2/day
                shortrad_daily_MJm2day = (radiation_daily*3600*24)/1000000
                obj_eto.setClimateData(
                    self.minT_daily[i_row, i_col, :], self.maxT_daily[i_row, i_col, :], wind_daily, shortrad_daily_MJm2day, rel_humidity_daily)
                self.pet_daily[i_row, i_col, :] = obj_eto.calculateETO()

        # Sea-level adjusted mean temperature
        self.meanT_daily_sealevel = self.meanT_daily + \
            np.tile(np.reshape(self.elevation/100*0.55,
                    (self.im_height, self.im_width, 1)), (1, 1, 365))
        # P over PET ratio(to eliminate nan in the result, nan is replaced with zero)
        self.P_by_PET_daily = np.divide(
            self.totalPrec_daily, self.pet_daily, out=np.zeros_like(self.totalPrec_daily), where=(self.pet_daily != 0))

        self.set_monthly=True

    def setDailyClimateData(self, min_temp, max_temp, precipitation, short_rad, wind_speed, rel_humidity):
        """Load DAILY climate data into the Class and calculate the Reference Evapotranspiration (ETo)

        Args:
            min_temp (3D NumPy): Daily minimum temperature [Celcius]
            max_temp (3D NumPy): Daily maximum temperature [Celcius]
            precipitation (3D NumPy): Daily total precipitation [mm/day]
            short_rad (3D NumPy): Daily solar radiation [W/m2]
            wind_speed (3D NumPy): Daily windspeed at 2m altitude [m/s]
            rel_humidity (3D NumPy): Daily relative humidity [percentage decimal, 0-1]
        """

        rel_humidity[rel_humidity > 0.99] = 0.99
        rel_humidity[rel_humidity < 0.05] = 0.05
        short_rad[short_rad < 0] = 0
        self.minT_daily = min_temp
        self.maxT_daily = max_temp
        self.totalPrec_daily = precipitation
        self.shortRad_daily = short_rad
        self.wind2m_daily = wind_speed
        self.rel_humidity_daily = rel_humidity

        self.meanT_daily = np.zeros((self.im_height, self.im_width, 365))
        self.totalPrec_daily = np.zeros((self.im_height, self.im_width, 365))
        self.pet_daily = np.zeros((self.im_height, self.im_width, 365))


        for i_row in range(self.im_height):
            for i_col in range(self.im_width):

                if self.set_mask:
                    if self.im_mask[i_row, i_col] == self.nodata_val:
                        continue

                self.meanT_daily[i_row, i_col, :] = 0.5 * \
                    (min_temp[i_row, i_col, :]+max_temp[i_row, i_col, :])
                self.totalPrec_daily[i_row, i_col,:] = precipitation[i_row, i_col, :]

                # calculation of reference evapotranspiration (ETo)
                obj_eto = ETOCalc.ETOCalc(
                    1, 365, self.latitude[i_row, i_col], self.elevation[i_row, i_col])
                # convert w/m2 to MJ/m2/day
                shortrad_daily_MJm2day = (
                    short_rad[i_row, i_col, :]*3600*24)/1000000
                obj_eto.setClimateData(min_temp[i_row, i_col, :], max_temp[i_row, i_col, :],
                                       wind_speed[i_row, i_col, :], shortrad_daily_MJm2day, rel_humidity[i_row, i_col, :])
                self.pet_daily[i_row, i_col, :] = obj_eto.calculateETO()

        # sea level temperature
        self.meanT_daily_sealevel = self.meanT_daily + \
            np.tile(np.reshape(self.elevation/100*0.55,
                    (self.im_height, self.im_width, 1)), (1, 1, 365))
        # P over PET ratio (to eliminate nan in the result, nan is replaced with zero)
        self.P_by_PET_daily = np.nan_to_num(self.totalPrec_daily / self.pet_daily)
        self.set_monthly = False

    def setLocationTerrainData(self, lat_min, lat_max, elevation):
        """Load geographical extents and elevation data in to the Class, 
           and create a latitude map

        Args:
            lat_min (float): the minimum latitude of the AOI in decimal degrees
            lat_max (float): the maximum latitude of the AOI in decimal degrees
            elevation (2D NumPy): elevation map in metres
        """
        self.elevation = elevation
        self.im_height = elevation.shape[0]
        self.im_width = elevation.shape[1]
        self.latitude = UtilitiesCalc.UtilitiesCalc().generateLatitudeMap(lat_min, lat_max, self.im_height, self.im_width)
    
    # Minimum and maximum cycle length, and crop height logic included.
    def readCropandCropCycleParameters(self, file_path, crop_name):
        """
        Mandatory function to import the excel sheet of crop-specific parameters,
        crop water requirements, management info, perennial adjustment parameters,
        and TSUM screening thresholds.

        Parameters
        ----------
        file_path : String.
            The file path of the external excel sheet in xlsx.
        crop_name : String.
            Unique name of crop for crop simulation.

        Returns
        -------
        None.

        """

        self.crop_name = crop_name
        df = pd.read_excel(file_path)

        crop_df_index = df.index[df['Crop_name'] == crop_name].tolist()[0]
        crop_df = df.loc[df['Crop_name'] == crop_name]

        self.setCropParameters(LAI=crop_df['LAI'][crop_df_index], HI=crop_df['HI'][crop_df_index], legume=crop_df['legume'][crop_df_index], adaptability=int(crop_df['adaptability'][crop_df_index]), cycle_len=int(crop_df['cycle_len'][crop_df_index]), D1=crop_df['D1']
                               [crop_df_index], D2=crop_df['D2'][crop_df_index], min_temp=crop_df['min_temp'][crop_df_index], aLAI=crop_df['aLAI'][crop_df_index], bLAI=crop_df['bLAI'][crop_df_index], aHI=crop_df['aHI'][crop_df_index], bHI=crop_df['bHI'][crop_df_index],
                               min_cycle_len=crop_df['min_cycle_len'][crop_df_index], max_cycle_len=crop_df['max_cycle_len'][crop_df_index], plant_height = crop_df['height'][crop_df_index])
        self.setCropCycleParameters(stage_per=[crop_df['stage_per_1'][crop_df_index], crop_df['stage_per_2'][crop_df_index], crop_df['stage_per_3'][crop_df_index], crop_df['stage_per_4'][crop_df_index]], kc=[crop_df['kc_0'][crop_df_index], crop_df['kc_1'][crop_df_index], crop_df['kc_2']
                                    [crop_df_index]], kc_all=crop_df['kc_all'][crop_df_index], yloss_f=[crop_df['yloss_f0'][crop_df_index], crop_df['yloss_f1'][crop_df_index], crop_df['yloss_f2'][crop_df_index], crop_df['yloss_f3'][crop_df_index]], yloss_f_all=crop_df['yloss_f_all'][crop_df_index])

        # perennial = 1, annual = 0
        if crop_df['annual/perennial flag'][crop_df_index] == 1:
            self.perennial = True
        else:
            self.perennial = False

        # If users provide all TSUM thresholds, TSUM screening
        if np.all([crop_df['LnS'][crop_df_index] != np.nan, crop_df['LsO'][crop_df_index] != np.nan, crop_df['LO'][crop_df_index] != np.nan, crop_df['HnS'][crop_df_index] != np.nan, crop_df['HsO'][crop_df_index] != np.nan, crop_df['HO'][crop_df_index] != np.nan]):
            self.setTSumScreening(LnS=crop_df['LnS'][crop_df_index], LsO=crop_df['LsO'][crop_df_index], LO=crop_df['LO'][crop_df_index],
                                  HnS=crop_df['HnS'][crop_df_index], HsO=crop_df['HsO'][crop_df_index], HO=crop_df['HO'][crop_df_index])

        # releasing memory
        del (crop_df_index, crop_df)


    def setSoilWaterParameters(self, Sa, pc):
        """This function allow user to set up the parameters related to the soil water storage.

        Args:
            Sa (float or 2D numpy): Available  soil moisture holding capacity
            pc (float): Soil water depletion fraction below which ETa<ETo
        """        
        self.Sa = Sa  # available soil moisture holding capacity (mm/m) , assumption
        self.pc = pc  # soil water depletion fraction below which ETa < ETo (from literature)

    
    
    """Supporting functions nested within the mandatory functions"""
    # Yield formation period logic included.
    def setCropParameters(self, LAI, HI, legume, adaptability, cycle_len, D1, D2, min_temp, aLAI, bLAI, aHI, bHI, min_cycle_len, max_cycle_len, plant_height):
        """This function allows users to set up the main crop parameters necessary for PyAEZ.

        Args:
            LAI (float): Leaf Area Index
            HI (float): Harvest Index
            legume (binary, yes=1, no=0): Is the crop legume?
            adaptability (int): Crop adaptability clases (1-4)
            cycle_len (int): Length of crop cycle
            D1 (float): Rooting depth at the beginning of the crop cycle [m]
            D2 (float): Rooting depth after crop maturity [m]
        """
        self.LAi = LAI  # leaf area index
        self.HI = HI  # harvest index
        self.legume = legume  # binary value
        self.adaptability = adaptability  # one of [1,2,3,4] classes
        self.cycle_len = cycle_len  # length of growing period
        self.D1 = D1  # rooting depth 1 (m)
        self.D2 = D2  # rooting depth 2 (m)
        self.min_temp = min_temp  # minimum temperature
        self.aLAI = aLAI
        self.bLAI = bLAI
        self.aHI = aHI
        self.bHI = bHI
        self.min_cycle_len = min_cycle_len
        self.max_cycle_len = max_cycle_len
        self.plant_height= plant_height

    def setCropCycleParameters(self, stage_per, kc, kc_all, yloss_f, yloss_f_all):
        self.d_per = stage_per  # Percentage for D1, D2, D3, D4 stages
        self.kc = kc  # 3 crop water requirements for initial, reproductive, the end of the maturation stages
        self.kc_all = kc_all  # crop water requirements for entire growth cycle
        self.yloss_f = yloss_f  # yield loss for D1, D2, D3, D4
        self.yloss_f_all = yloss_f_all  # yield loss for entire growth cycle

    
    
    '''Additional optional functions'''

    # set mask of study area, this is optional
    def setStudyAreaMask(self, admin_mask, no_data_value):
        """Set clipping mask of the area of interest (optional)

        Args:
            admin_mask (2D NumPy/Binary): mask to extract only region of interest
            no_data_value (int): pixels with this value will be omitted during PyAEZ calculations
        """
        self.im_mask = admin_mask
        self.nodata_val = no_data_value
        self.set_mask = True

    def getThermalClimate(self):
        """Classification of rainfall and temperature seasonality into thermal climate classes

        Returns:
            2D NumPy: Thermal Climate classification
        """
        # Note that currently, this thermal climate is designed only for the northern hemisphere, southern hemisphere is not implemented yet.
        thermal_climate = np.zeros(
            (self.im_height, self.im_width), dtype=np.int8)

        for i_row in range(self.im_height):
            for i_col in range(self.im_width):

                if self.set_mask:
                    if self.im_mask[i_row, i_col] == self.nodata_val:
                        continue

                # converting daily to monthly
                obj_utilities = UtilitiesCalc.UtilitiesCalc()
                meanT_monthly_sealevel = obj_utilities.averageDailyToMonthly(
                    self.meanT_daily_sealevel[i_row, i_col, :])
                meanT_monthly = obj_utilities.averageDailyToMonthly(
                    self.meanT_daily[i_row, i_col, :])
                P_by_PET_monthly = obj_utilities.averageDailyToMonthly(
                    self.P_by_PET_daily[i_row, i_col, :])

                if self.set_mask:
                    if self.im_mask[i_row, i_col] == self.nodata_val:
                        continue

                # Seasonal parameters
                summer_PET0 = np.sum(P_by_PET_monthly[3:9])
                winter_PET0 = np.sum(
                    [P_by_PET_monthly[9::], P_by_PET_monthly[0:3]])
                Ta_diff = np.max(meanT_monthly_sealevel) - \
                    np.min(meanT_monthly_sealevel)

                # Tropics
                if np.min(meanT_monthly_sealevel) >= 18. and Ta_diff < 15.:
                    if np.mean(meanT_monthly) < 20.:
                        thermal_climate[i_row, i_col] = 2  # Tropical highland
                    else:
                        thermal_climate[i_row, i_col] = 1  # Tropical lowland

                # SubTropic
                elif np.min(meanT_monthly_sealevel) >= 5. and np.sum(meanT_monthly_sealevel >= 10) >= 8:
                    if np.sum(self.totalPrec_daily[i_row, i_col, :]) < 250:
                        # 'Subtropics Low Rainfall
                        thermal_climate[i_row, i_col] = 3
                    elif self.latitude[i_row, i_col] >= 0:
                        if summer_PET0 >= winter_PET0:
                            # Subtropics Summer Rainfall
                            thermal_climate[i_row, i_col] = 4
                        else:
                            # Subtropics Winter Rainfall
                            thermal_climate[i_row, i_col] = 5
                    else:
                        if summer_PET0 >= winter_PET0:
                            # Subtropics Winter Rainfall
                            thermal_climate[i_row, i_col] = 5
                        else:
                            # Subtropics Summer Rainfall
                            thermal_climate[i_row, i_col] = 4

                # Temperate
                elif np.sum(meanT_monthly_sealevel >= 10) >= 4:
                    if Ta_diff <= 20:
                        # Oceanic Temperate
                        thermal_climate[i_row, i_col] = 6
                    elif Ta_diff <= 35:
                        # Sub-Continental Temperate
                        thermal_climate[i_row, i_col] = 7
                    else:
                        # Continental Temperate
                        thermal_climate[i_row, i_col] = 8

                elif np.sum(meanT_monthly_sealevel >= 10) >= 1:
                    # Boreal
                    if Ta_diff <= 20:
                        # Oceanic Boreal
                        thermal_climate[i_row, i_col] = 9
                    elif Ta_diff <= 35:
                        # Sub-Continental Boreal
                        thermal_climate[i_row, i_col] = 10
                    else:
                        # Continental Boreal
                        thermal_climate[i_row, i_col] = 11
                else:
                    # Arctic
                    thermal_climate[i_row, i_col] = 12

        if self.set_mask:
            return np.where(self.im_mask, thermal_climate, np.nan)
        else:
            return thermal_climate
    
    def getThermalLGP5(self):
        """Calculate Thermal Length of Growing Period (LGPt) with 
        temperature threshold of 5 degree Celcius

        Returns:
            2D numpy: The accumulated number of days with daily mean 
                      temperature is above 5 degree Celcius
        """
        lgpt5 = np.sum(self.meanT_daily >= 5, axis=2)
        if self.set_mask:
            lgpt5 = np.where(self.im_mask, lgpt5, np.nan)

        self.lgpt5 = lgpt5.copy()
        return lgpt5

    def getThermalLGP10(self):
        """Calculate Thermal Length of Growing Period (LGPt) with
        temperature threshold of 10 degree Celcius

        Returns:
            2D numpy: The accumulated number of days with daily mean
                      temperature is above 10 degree Celcius
        """

        lgpt10 = np.sum(self.meanT_daily >= 10, axis=2)
        if self.set_mask:
            lgpt10 = np.where(self.im_mask, lgpt10, np.nan)

        self.lgpt10 = lgpt10.copy()
        return lgpt10
    
    def getLGP(self, Sa=100., D=1.):
        """Calculate length of growing period (LGP)

        Args:
            Sa (float, optional): Available soil moisture holding capacity [mm/m]. Defaults to 100..
            D (float, optional): Rooting depth. Defaults to 1..

        Returns:
           2D NumPy: Length of Growing Period
        """
        # ============================
        kc_list = np.array([0.0, 0.1, 0.2, 0.5, 1.0])
        # ============================
        Txsnm = 0.  # Txsnm - snow melt temperature threshold
        Fsnm = 5.5  # Fsnm - snow melting coefficient
        Sb_old = 0.
        Wb_old = 0.
        # ============================
        Tx365 = self.maxT_daily.copy()
        Ta365 = self.meanT_daily.copy()
        Pcp365 = self.totalPrec_daily.copy()
        self.Eto365 = self.pet_daily.copy()  # Eto
        self.Etm365 = np.zeros(Tx365.shape)
        self.Eta365 = np.zeros(Tx365.shape)
        self.Sb365 = np.zeros(Tx365.shape)
        self.Wb365 = np.zeros(Tx365.shape)
        self.Wx365 = np.zeros(Tx365.shape)
        self.kc365 = np.zeros(Tx365.shape)
        meanT_daily_new = np.zeros(Tx365.shape)
        self.maxT_daily_new = np.zeros(Tx365.shape)
        lgp_tot = np.zeros((self.im_height, self.im_width))
        # ============================
        for i_row in range(self.im_height):
            for i_col in range(self.im_width):

                lgpt5_point = self.lgpt5[i_row, i_col]

                totalPrec_monthly = UtilitiesCalc.UtilitiesCalc().averageDailyToMonthly(
                    self.totalPrec_daily[i_row, i_col, :])
                meanT_daily_point = Ta365[i_row, i_col, :]
                istart0, istart1 = LGPCalc.rainPeak(
                    totalPrec_monthly, meanT_daily_point, lgpt5_point)
                # ----------------------------------
                if self.set_mask:
                    if self.im_mask[i_row, i_col] == self.nodata_val:
                        continue

                for doy in range(0, 365):
                    p = LGPCalc.psh(
                        0., self.Eto365[i_row, i_col, doy])
                    Eta_new, Etm_new, Wb_new, Wx_new, Sb_new, kc_new = LGPCalc.EtaCalc(
                        np.float64(Tx365[i_row, i_col, doy]), np.float64(
                            Ta365[i_row, i_col, doy]),
                        # Ta365[i_row, i_col, doy]),
                        np.float64(Pcp365[i_row, i_col, doy]), Txsnm, Fsnm, np.float64(
                            self.Eto365[i_row, i_col, doy]),
                        Wb_old, Sb_old, doy, istart0, istart1,
                        Sa, D, p, kc_list, lgpt5_point)

                    if Eta_new < 0.:
                        Eta_new = 0.

                    self.Eta365[i_row, i_col, doy] = Eta_new
                    self.Etm365[i_row, i_col, doy] = Etm_new
                    self.Wb365[i_row, i_col, doy] = Wb_new
                    self.Wx365[i_row, i_col, doy] = Wx_new
                    self.Sb365[i_row, i_col, doy] = Sb_new
                    self.kc365[i_row, i_col, doy] = kc_new

                    Wb_old = Wb_new
                    Sb_old = Sb_new
        # ============================================
        for i_row in range(self.im_height):
            for i_col in range(self.im_width):
                if self.set_mask:
                    if self.im_mask[i_row, i_col] == self.nodata_val:
                        continue
                Etm365X = np.append(
                    self.Etm365[i_row, i_col, :], self.Etm365[i_row, i_col, :])
                Eta365X = np.append(
                    self.Eta365[i_row, i_col, :], self.Eta365[i_row, i_col, :])
                islgp = LGPCalc.islgpt(self.meanT_daily[i_row, i_col, :])
                xx = LGPCalc.val10day(Eta365X)
                yy = LGPCalc.val10day(Etm365X)
                lgp_whole = xx[:365]/yy[:365]
                count = 0
                for i in range(len(lgp_whole)):
                    if islgp[i] == 1 and lgp_whole[i] >= 0.4:
                        count = count+1

                lgp_tot[i_row, i_col] = count

        if self.set_mask:
            return np.where(self.im_mask, lgp_tot, np.nan)
        else:
            return lgp_tot

    def ImportLGPandLGPTforPerennial(self, lgp, lgpt5, lgpt10):
        """
        Mandatory step of input data required for perennial crop simulation.
        This function is run before the actual crop simulation.

        Parameters
        ----------
        lgp : 2-D numpy array
            Length of Growing Period.
        lgpt5 : 2-D numpy array
            Temperature Growing Period at 5℃ threshold.
        lgpt10 : 2-D numpy array
            Temperature Growing Period at 10℃ threshold.

        Returns
        -------
        None.

        """
        self.LGP = lgp
        self.LGPT5 = lgpt5
        self.LGPT10 = lgpt10

    def adjustForPerennialCrop(self,  cycle_len, aLAI, bLAI, aHI, bHI, rain_or_irr):
        """If a perennial crop is introduced, PyAEZ will perform adjustment 
        on the Leaf Area Index (LAI) and the Harvest Index (HI) based 
        on the effective growing period.

        Args:
            aLAI (int): alpha coefficient for LAI
            bLAI (int): beta coefficient for LAI
            aHI (int): alpha coefficient for HI
            bHI (int): beta coefficient for HI
        """        
        if rain_or_irr == 'rain':
            # leaf area index adjustment for perennial crops
            self.LAi_rain = self.LAi * ((cycle_len-aLAI)/bLAI)
            # harvest index adjustment for perennial crops
            self.HI_rain = self.HI * ((cycle_len-aHI)/bHI)

        if rain_or_irr == 'irr':
            # leaf area index adjustment for perennial crops
            self.LAi_irr = self.LAi * ((cycle_len-aLAI)/bLAI)
            # harvest index adjustment for perennial crops
            self.HI_irr = self.HI * ((cycle_len-aHI)/bHI)

    """ Thermal Screening functions (Optional)"""

    def setThermalClimateScreening(self, t_climate, no_t_climate):
        """
        The thermal screening function omit out user-specified thermal climate classes
        not suitable for a particular crop for crop simulation. Using this optional 
        function will activate application of thermal climate screening in crop cycle simulation.
    

        Parameters
        ----------
        t_climate : 2-D numpy array
            Thermal Climate.
        no_t_climate : list
            A list of thermal climate classes not suitable for crop simulation.

        Returns
        -------
        None.

        """
        self.t_climate = t_climate
        self.no_t_climate = no_t_climate  # list of unsuitable thermal climate

        self.set_tclimate_screening = True

    # set suitability screening, this is also optional
    def setLGPTScreening(self, no_lgpt, optm_lgpt):
        """Set screening parameters for thermal growing period (LGPt)

        Args:
            no_lgpt (3-item list): 3 'not suitable' LGPt conditions
            optm_lgpt (3-item list): 3 'optimum' LGPt conditions
        """        
        self.no_lgpt = no_lgpt
        self.optm_lgpt = optm_lgpt

        self.set_lgpt_screening = True

    def setTSumScreening(self, LnS, LsO, LO, HnS, HsO, HO):
        """
        This thermal screening corresponds to Type A constraint (TSUM Screeing) of GAEZ which
        uses six TSUM thresholds for optimal, sub-optimal and not suitable conditions. Using 
        this optional function will activate application of TSUM screening in crop cycle simulation.
        

        Parameters
        ----------
        LnS : Integer
            Lower boundary of not-suitable accumulated heat unit range.
        LsO : Integer
            Lower boundary of sub-optimal accumulated heat unit range.
        LO : Integer
            Lower boundary of optimal accumulated heat unit range.
        HnS : Integer
            Upper boundary of not-suitable accumulated heat range.
        HsO : Integer
            Upper boundary of sub-optimal accumulated heat range.
        HO : Integer
            Upper boundary of not-suitable accumulated heat range.

        Returns
        -------
        None.

        """
        self.LnS = int(LnS)  # Lower boundary/ not suitable
        self.LsO = int(LsO)  # Lower boundary/ sub optimal
        self.LO = int(LO)  # Lower boundary / optimal
        self.HnS = int(HnS)  # Upper boundary/ not suitable
        self.HsO = int(HsO)  # Upper boundary / sub-optimal
        self.HO = int(HO)  # Upper boundary / optimal
        self.set_Tsum_screening = True

    def setPermafrostScreening(self, permafrost_class):

        self.permafrost_class = permafrost_class  # permafrost class 2D numpy array
        self.set_Permafrost_screening = True

    def setupTypeBConstraint(self, file_path, crop_name):
        """
        Optional function initiates the type B constraint (Temperature Profile 
        Constraint) on the existing crop based on user-specified constraint rules.

        Parameters
        ----------
        file_path : xlsx
            The file path of excel sheet where the Type B constraint rules are provided.
        crop_name : String
            Unique name of crop to consider. The name must be the same provided in excel sheet.


        Returns
        -------
        None.

        """

        data = pd.read_excel(file_path)
        self.crop_name = crop_name

        self.data = data.loc[data['Crop'] == self.crop_name]

        self.setTypeBConstraint = True

        # releasing data
        del (data)

    """ The main functions of MODULE II: Crop Simulation"""

    def getEstimatedYieldRainfed(self):
        """Estimation of Maximum Yield for Rainfed scenario

        Returns:
        2D NumPy: the maximum attainable yield under the provided climate conditions, 
                    under rain-fed conditions [kg/ha]
        """        
        return self.final_yield_rainfed

    def getEstimatedYieldIrrigated(self):
        """Estimation of Maximum Yield for Irrigated scenario

        Returns:
            2D NumPy: the maximum attainable yield under the provided climate conditions, 
                      under irrigated conditions [kg/ha]
        """
        return self.final_yield_irrig

    def getOptimumCycleStartDateIrrigated(self):
        """
        Function for optimum starting date for irrigated condition.

        Returns
        -------
        TYPE: 2-D numpy array.
            Optimum starting date for irrigated condition.

        """
        return self.crop_calender_irr

    def getOptimumCycleStartDateRainfed(self):
        """
        Function for optimum starting date for rainfed condition.

        Returns
        -------
        TYPE: 2-D numpy array.
            Optimum starting date for rainfed condition.

        """
        return self.crop_calender_rain

    def getThermalReductionFactor(self):
        """
        Function for thermal reduction factor (fc1) map. For perennial crop,
        the function produces a list of fc1 maps for both conditions. Only one 
        fc1 map is produced for non-perennial crops, representing both rainfed 
        and irrigated conditions

        Returns
        -------
        TYPE: A python list of 2-D numpy arrays: [fc1 rainfed, fc1 irrigated] 
        or a 2-D numpy array.
            Thermal reduction factor map (fc1) for corresponding conditions.

        """
        return [self.fc1_rain, self.fc1_irr]

    def getMoistureReductionFactor(self):
        """
        Function for reduction factor map due to moisture deficit (fc2) for 
        rainfed condition. Only fc2 map is produced for non-perennial crops.
        
        Returns
        -------
        TYPE: 2-D numpy array
            Reduction factor due to moisture deficit (fc2).

        """

        return self.fc2


#----------------- End of file -------------------------#

    def simulateCropCycleOne(self, i_row, i_col, start_doy=1, end_doy=365, step_doy=1, leap_year=False):
        """Running the crop cycle calculation/simulation for a particular pixel location

        Args:
            start_doy (int, optional): Starting Julian day for simulating period. Defaults to 1.
            end_doy (int, optional): Ending Julian day for simulating period. Defaults to 365.
            step_doy (int, optional): Spacing (in days) between 2 adjacent crop simulations. Defaults to 1.
            leap_year (bool, optional): whether or not the simulating year is a leap year. Defaults to False.

        """        

        # just a counter to keep track of progress

        # this stores final result
        final_yield_rainfed = 0.
        final_yield_irrig = 0.
        crop_calender_irr = 0
        crop_calender_rain = 0
        fc2 = 0.
        fc1_rain = 0.
        fc1_irr = 0.

        # check current location (pixel) is outside of study area or not. if it's outside of study area goes to next location (pixel)
        # Those unsuitable
        if self.set_mask:
            if self.im_mask[i_row, i_col] == self.nodata_val:
                print('Pixel outside of AOI')

        # 2. Permafrost screening
        if self.set_Permafrost_screening:
            if np.logical_or(self.permafrost_class[i_row, i_col] == 1, self.permafrost_class[i_row, i_col] == 2):
                print('Permafrost screening not met. Class{}'.format(self.permafrost_class[i_row, i_col]))

        # Thermal Climate Screening
        if self.set_tclimate_screening:
            if self.t_climate[i_row, i_col] in self.no_t_climate:
                print('Thermal Climate screening not met. Class{}'.format(self.t_climate[i_row, i_col]))

        """Cycle length checking for rainfed and irrigated annuals.
            Concerns with LGPt5 (irrigated) and LGP (rainfed)"""
        if not self.perennial:

            "Harvest Index and Leaf Area Index are not adjusted."
            self.LAi_rain = self.LAi
            self.HI_rain = self.HI

            self.LAi_irr = self.LAi
            self.HI_irr = self.HI
            
            # for irrigated conditions
            # In real simulation, this pixel would be omitted out
            if int(self.LGPT5[i_row, i_col]) < self.min_cycle_len:
                print('Irrigated cycle length does not meet minimum cycle length requirement. LGPT5_{}_min_cyc_len_{}'.format(int(self.LGPT5[i_row, i_col]), self.min_cycle_len))
                self.cycle_len_irr = -9
            else:
                self.cycle_len_irr = self.cycle_len
            
            # for rainfed condition
            # In real simulation, this pixel would be omitted out for 
            if int(self.LGP[i_row, i_col]) < self.min_cycle_len:
                print('Rainfed cycle length does not meet minimum cycle length requirement. LGP_{}_min_cyc_len_{}'.format(int(self.LGP[i_row, i_col]), self.min_cycle_len))
                self.cycle_len_rain = -9
            else:
                self.cycle_len_rain = self.cycle_len
              
        else:
            """Adjustment of cycle length, LAI and HI for Perennials"""
            self.set_adjustment = True

            """ Adjustment for RAINFED conditions"""
            # effective cycle length will be our cycle length
            self.cycle_len_rain = min(int(self.LGP[i_row, i_col]), self.max_cycle_len)

            self.adjustForPerennialCrop(
                    self.cycle_len_rain, aLAI=self.aLAI, bLAI=self.bLAI, aHI=self.aHI, bHI=self.bHI, rain_or_irr='rain')
            
            if self.cycle_len_rain < self.min_cycle_len:
                print('Rainfed cycle length does not meet minimu cycle length requirement. LGP_{}_min_cyc_len_{}'.format(int(self.LGP[i_row, i_col]), self.min_cycle_len))
                self.cycle_len_rain = -10
                        
        
            """ Adjustment for IRRIGATED conditions"""
            """Use LGPT5 for minimum temperatures less than 8. Use LGPT10 for temperature greater than 8."""
            # effective cycle length will be our cycle length
            if self.min_temp <= 8:
                self.cycle_len_irr = min(int(self.LGPT5[i_row, i_col]), self.max_cycle_len)
            elif self.min_temp >8:
                self.cycle_len_irr = min(int(self.LGPT10[i_row, i_col]), self.max_cycle_len)
            
            self.adjustForPerennialCrop(
                    self.cycle_len_irr , aLAI=self.aLAI, bLAI=self.bLAI, aHI=self.aHI, bHI=self.bHI, rain_or_irr='irr')
            
            if self.cycle_len_irr < self.min_cycle_len:
                print('Irrigated cycle length does not meet minimu cycle length requirement. LGPT5_{}_min_cyc_len_{}'.format(int(self.LGPT5[i_row, i_col]), self.min_cycle_len))
                self.cycle_len_irr = -10
                
        # this allows handing leap and non-leap year differently. This is only relevant for monthly data because this value will be used in interpolations.
        # In case of daily data, length of vector will be taken as number of days in  a year.
        if leap_year:
            days_in_year = 366
        else:
            days_in_year = 365

        # extract climate data for particular location. And if climate data are monthly data, they are interpolated as daily data
        if self.set_monthly:
            obj_utilities = UtilitiesCalc.UtilitiesCalc()

            minT_daily_point = obj_utilities.interpMonthlyToDaily(
                self.minT_monthly[i_row, i_col, :], 1, days_in_year)
            maxT_daily_point = obj_utilities.interpMonthlyToDaily(
                self.maxT_monthly[i_row, i_col, :], 1, days_in_year)
            shortRad_daily_point = obj_utilities.interpMonthlyToDaily(
                self.shortRad_monthly[i_row, i_col, :],  1, days_in_year, no_minus_values=True)
            wind2m_daily_point = obj_utilities.interpMonthlyToDaily(
                self.wind2m_monthly[i_row, i_col, :],  1, days_in_year, no_minus_values=True)
            totalPrec_daily_point = obj_utilities.interpMonthlyToDaily(
                self.totalPrec_monthly[i_row, i_col, :],  1, days_in_year, no_minus_values=True)
            rel_humidity_daily_point = obj_utilities.interpMonthlyToDaily(
                self.rel_humidity_monthly[i_row, i_col, :],  1, days_in_year, no_minus_values=True)
        else:
            minT_daily_point = self.minT_daily[i_row, i_col, :]
            maxT_daily_point = self.maxT_daily[i_row, i_col, :]
            shortRad_daily_point = self.shortRad_daily[i_row, i_col, :]
            wind2m_daily_point = self.wind2m_daily[i_row, i_col, :]
            totalPrec_daily_point = self.totalPrec_daily[i_row, i_col, :]
            rel_humidity_daily_point = self.rel_humidity_daily[i_row, i_col, :]
            

        # calculate ETO for full year for particular location (pixel) 7#
        obj_eto = ETOCalc.ETOCalc(
            1, minT_daily_point.shape[0], self.latitude[i_row, i_col], self.elevation[i_row, i_col])

        # 7. New Modification
        shortRad_daily_point_MJm2day = (shortRad_daily_point*3600*24)/1000000 # convert w/m2 to MJ/m2/day (Correct)

        # 7. Minor change for validation purposes: shortRad_daily_point is replaced in shortRad_dailyy_point_MJm2day. (Sunshine hour data for KB Etocalc)
        obj_eto.setClimateData(minT_daily_point, maxT_daily_point,
                                wind2m_daily_point, shortRad_daily_point_MJm2day, rel_humidity_daily_point)
        pet_daily_point = obj_eto.calculateETO()


        # Empty arrays that stores yield estimations and fc1 and fc2 of all cycles per particular location (pixel)
        yield_of_all_crop_cycles_rainfed = np.empty(0, dtype= np.float16)
        yield_of_all_crop_cycles_irrig = np.empty(0, dtype= np.float16)

        fc1_rain_lst = np.empty(0, dtype= np.float16)
        fc1_irr_lst = np.empty(0, dtype= np.float16)

        fc2_lst = np.empty(0, dtype= np.float16)

        hi_result = np.empty(0, dtype= np.float16)
        lai_result = np.empty(0, dtype= np.float16)

        # Error list
        err_list = np.zeros(365, dtype = int)

        climate = {
            'Minimum temperature (Deg C)': minT_daily_point,
            'Maximum temperature (Deg C)': maxT_daily_point,
            'Mean temperature (Deg C)': (minT_daily_point + maxT_daily_point) /2,
            'Shortwave Radiation (W/m2)': shortRad_daily_point,
            'Shortwave radiation (MJ/m2/day)': shortRad_daily_point_MJm2day,
            'Precipitation (mm/day)': totalPrec_daily_point,
            'Relative Humidity (decimal)':rel_humidity_daily_point,
            'ETo (mm/day)': pet_daily_point
            
        }
        
        general = {
            'row':i_row,
            'col':i_col,
            'latitude(decimal deg)': self.latitude[i_row, i_col],
            'Elevation(m)':self.elevation[i_row, i_col],
            'permafrost class':self.permafrost_class[i_row, i_col],
            'thermal climate class':self.t_climate[i_row, i_col],
            'Annual_meanT': np.round(np.mean(self.meanT_daily[i_row, i_col,:]), 0),
            'perennial-flag':self.perennial,
            'cycle_len_rain':self.cycle_len_rain,
            'cycle_len_irr':self.cycle_len_irr,
            'LAI_rain':self.LAi_rain,
            'LAI_irr':self.LAi_irr,
            'HI_rain':self.HI_rain,
            'HI_irr':self.HI_irr,
            'LGP': self.LGP[i_row, i_col],
            'LGPt5': self.LGPT5[i_row, i_col],
            'LGPt10':self.LGPT10[i_row, i_col],

        }

        """ Calculation of each individual day's yield for rainfed and irrigated conditions"""
        print('Cycle No.\tfc1_irr\tfc1_rain\tfc2\tyld_irr\tyld_rain\terr_flag\n')
        print('---------------------------------------------------------------------------')

        for i_cycle in range(start_doy-1, end_doy, step_doy):

            """Repeat the climate data two times and concatenate for computational convenience. If perennial, the cycle length
            will be different for separate conditions"""
            

            
            """Check if the first day of a cycle meets minimum temperature requirement. If not, all outputs will be zero.
               And iterates to next cycle."""
            if (minT_daily_point[i_cycle]+maxT_daily_point[i_cycle])/2 < self.min_temp:
                est_yield_moisture_limited = 0.
                fc1_rain = 0.
                fc1_irr =0.
                fc2_value = 0.
                est_yield_irrigated = 0.
                error = -1
                err_list[i_cycle] = error

                yield_of_all_crop_cycles_rainfed = np.append(yield_of_all_crop_cycles_rainfed, 0.)
                yield_of_all_crop_cycles_irrig = np.append(yield_of_all_crop_cycles_irrig, 0.)
                fc1_rain_lst = np.append(fc1_rain_lst, 0.)
                fc1_irr_lst = np.append(fc1_irr_lst, 0.)
                fc2_lst = np.append(fc2_lst, 0.)
                print('{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format(i_cycle,fc1_irr,fc1_rain,fc2_value,est_yield_irrigated,est_yield_moisture_limited, error))
                continue

            """ Time slicing tiled climate data with corresponding cycle lengths for rainfed and irrigated conditions"""
            """For rainfed"""

            
            if self.cycle_len_rain in [-9, -10]:
                est_yield_moisture_limited = 0.
                fc1_rain = 0.
                fc2_value = 0.
                error =-2
            else:
                error = 0
                minT_daily_2year = np.tile(minT_daily_point, 2)
                maxT_daily_2year = np.tile(maxT_daily_point, 2)
                shortRad_daily_2year = np.tile(shortRad_daily_point, 2)
                totalPrec_daily_2year = np.tile(totalPrec_daily_point, 2)
                pet_daily_2year = np.tile(pet_daily_point, 2)

                # extract climate data within the season to pass in to calculation classes
                minT_daily_season_rain = minT_daily_2year[i_cycle: i_cycle +
                                                            int(self.cycle_len_rain)-1]
                maxT_daily_season_rain = maxT_daily_2year[i_cycle: i_cycle +
                                                            int(self.cycle_len_rain)-1]
                shortRad_daily_season_rain = shortRad_daily_2year[
                    i_cycle: i_cycle+int(self.cycle_len_rain)-1]
                pet_daily_season_rain = pet_daily_2year[
                    i_cycle: i_cycle+int(self.cycle_len_rain)-1]
                totalPrec_daily_season_rain = totalPrec_daily_2year[
                    i_cycle: i_cycle+int(self.cycle_len_rain)-1]
                wind_sp_daily_season_rain = wind2m_daily_point[
                    i_cycle: i_cycle+int(self.cycle_len_rain)-1]
                
                """Creating Thermal Screening object classes for perennial RAINFED conditions"""
                obj_screening_rain = ThermalScreening.ThermalScreening()
                
                """ For Perennials, 365 days of climate data will be used for Thermal Screening.
                For Annuals, climate data within crop-specific cycle length will be used for Thermal Screening."""
                if self.perennial:
                    obj_screening_rain.setClimateData(
                        minT_daily_2year[i_cycle: i_cycle+365-1], maxT_daily_2year[i_cycle: i_cycle+365-1])
                else:
                    obj_screening_rain.setClimateData(
                        minT_daily_season_rain, maxT_daily_season_rain)

                if self.set_lgpt_screening:
                    obj_screening_rain.setLGPTScreening(
                        no_lgpt=self.no_lgpt, optm_lgpt=self.optm_lgpt)

                # TSUM Screening
                if self.set_Tsum_screening:
                    obj_screening_rain.setTSumScreening(
                        LnS=self.LnS, LsO=self.LsO, LO=self.LO, HnS=self.HnS, HsO=self.HsO, HO=self.HO)

                # Crop-Specific Rule Screening
                if self.setTypeBConstraint:
                    obj_screening_rain.applyTypeBConstraint(
                        data=self.data, input_temp_profile=obj_screening_rain.tprofile, perennial_flag= self.perennial)

                # Initial set up value for fc1 RAINFED
                fc1_rain = 1.

                fc1_rain = obj_screening_rain.getReductionFactor2()  # fc1 for rainfed condition
                # fc1_rain_lst = np.append(fc1_rain_lst, fc1_rain)

                    
                if fc1_rain == 0.:
                    est_yield_moisture_limited = 0.
                    fc1_rain = 0.
                    fc2_value = 0.
                else:

                    """If fc1 RAINFED IS NOT ZERO >>> BIOMASS RAINFED STARTS"""
                    obj_maxyield_rain = BioMassCalc.BioMassCalc(
                        i_cycle+1, i_cycle+1+self.cycle_len_rain-1, self.latitude[i_row, i_col])
                    obj_maxyield_rain.setClimateData(
                        minT_daily_season_rain, maxT_daily_season_rain, shortRad_daily_season_rain)
                    obj_maxyield_rain.setCropParameters(
                        self.LAi_rain, self.HI_rain, self.legume, self.adaptability)
                    obj_maxyield_rain.calculateBioMass()
                    est_yield_rainfed = obj_maxyield_rain.calculateYield()

                    # reduce thermal screening factor
                    est_yield_rainfed = est_yield_rainfed * fc1_rain

                    """ For Annual RAINFED, crop water requirements are calculated in full procedures.
                        For Perennial RAINFED, procedures related with yield loss factors are omitted out.
                        For Irrigated Annuals and Perennials, crop water requirements are not applied due to
                        constant water supply."""
                    fc2_value = 1.
                    
                    obj_cropwat = CropWatCalc.CropWatCalc(
                        i_cycle+1, i_cycle+1+self.cycle_len_rain-1, perennial_flag = self.perennial)
                    obj_cropwat.setClimateData(
                        pet_daily_season_rain, totalPrec_daily_season_rain, wind_sp_daily_season_rain, 
                        minT_daily_season_rain, maxT_daily_season_rain)
                    
                    # check Sa is a raster or single value and extract Sa value accordingly
                    if len(np.array(self.Sa).shape) == 2:
                        Sa_temp = self.Sa[i_row, i_col]
                    else:
                        Sa_temp = self.Sa
                    obj_cropwat.setCropParameters(self.d_per, self.kc, self.kc_all, self.yloss_f,
                                                    self.yloss_f_all, est_yield_rainfed, self.D1, self.D2, Sa_temp, self.pc, self.plant_height)
                    est_yield_moisture_limited = obj_cropwat.calculateMoistureLimitedYield()

                    fc2_value = obj_cropwat.getfc2factormap()


            yield_of_all_crop_cycles_rainfed = np.append(yield_of_all_crop_cycles_rainfed, est_yield_moisture_limited)
            fc2_lst = np.append(fc2_lst, fc2_value)
            fc1_rain_lst = np.append(fc1_rain_lst, fc1_rain)
            

            """Error checking code snippet"""
            if est_yield_moisture_limited == None or est_yield_moisture_limited == np.nan:
                raise Exception('Crop Water Yield not returned. Row_{}_col_{}_Cycle_{}'.format(i_row, i_col, i_cycle))
            if fc2_value == None or fc2_value == np.nan:
                raise Exception('fc2 value not returned. Row_{}_col_{}_Cycle_{}'.format(i_row, i_col, i_cycle))
            if len(fc1_rain_lst) != i_cycle+1 or fc1_rain == None or fc1_rain == np.nan:
                raise Exception('Fc1 rain not properly appended. Row_{}_col_{}_Cycle_{}'.format(i_row, i_col, i_cycle))
            if len(yield_of_all_crop_cycles_rainfed) != i_cycle+1:
                raise Exception('Rainfed yield list not properly appended') 
            if len(fc2_lst) != i_cycle+1:
                raise Exception('Fc2 list not appended properly. Row_{}_col_{}_Cycle_{}'.format(i_row, i_col, i_cycle))

            
                ###################################
            if self.cycle_len_irr in [-9, -10]:
                est_yield_irrigated = 0.
                fc1_irr = 0.
                if error ==-2:
                    error = -4
                else:
                    error = -3
            else:
                """For irrigated"""
                # extract climate data within the season to pass in to calculation classes
                minT_daily_season_irr = minT_daily_2year[i_cycle: i_cycle +
                                                            int(self.cycle_len_irr)-1]
                maxT_daily_season_irr = maxT_daily_2year[i_cycle: i_cycle +
                                                            int(self.cycle_len_irr)-1]
                shortRad_daily_season_irr = shortRad_daily_2year[
                    i_cycle: i_cycle+int(self.cycle_len_irr)-1]
                pet_daily_season_irr = pet_daily_2year[
                    i_cycle: i_cycle+int(self.cycle_len_irr)-1]
                totalPrec_daily_season_irr = totalPrec_daily_2year[
                    i_cycle: i_cycle+int(self.cycle_len_irr)-1]
                
                """Creating Thermal Screening object classes for perennial RAINFED conditions"""
                obj_screening_irr = ThermalScreening.ThermalScreening()
                
                """ For Perennials, 365 days of climate data will be used for Thermal Screening.
                For Annuals, climate data within crop-specific cycle length will be used for Thermal Screening."""
                if self.perennial:
                    obj_screening_irr.setClimateData(
                        minT_daily_2year[i_cycle: i_cycle+365-1], maxT_daily_2year[i_cycle: i_cycle+365-1])
                else:
                    obj_screening_irr.setClimateData(
                        minT_daily_season_irr, maxT_daily_season_irr)

                if self.set_lgpt_screening:
                    obj_screening_irr.setLGPTScreening(
                        no_lgpt=self.no_lgpt, optm_lgpt=self.optm_lgpt)

                # TSUM Screening
                if self.set_Tsum_screening:
                    obj_screening_irr.setTSumScreening(
                        LnS=self.LnS, LsO=self.LsO, LO=self.LO, HnS=self.HnS, HsO=self.HsO, HO=self.HO)

                # Crop-Specific Rule Screening
                if self.setTypeBConstraint:
                    obj_screening_irr.applyTypeBConstraint(
                        data=self.data, input_temp_profile=obj_screening_rain.tprofile, perennial_flag= self.perennial)

                # Initial set up value for fc1 RAINFED
                fc1_irr = 1.

                fc1_irr = obj_screening_irr.getReductionFactor2()  # fc1 for rainfed condition

        
                if fc1_irr == 0.:
                    est_yield_irrigated = 0.
                else:
                    """If fc1 IRRIGATED IS NOT ZERO >>> BIOMASS IRRIGATED STARTS"""
                    obj_maxyield_irr = BioMassCalc.BioMassCalc(
                        i_cycle+1, i_cycle+1+self.cycle_len_irr-1, self.latitude[i_row, i_col])
                    obj_maxyield_irr.setClimateData(
                        minT_daily_season_irr, maxT_daily_season_irr, shortRad_daily_season_irr)
                    obj_maxyield_irr.setCropParameters(
                        self.LAi_irr, self.HI_irr, self.legume, self.adaptability)
                    obj_maxyield_irr.calculateBioMass()
                    est_yield_irrigated = obj_maxyield_irr.calculateYield()

                    # reduce thermal screening factor
                    est_yield_irrigated = est_yield_irrigated * fc1_irr

            yield_of_all_crop_cycles_irrig = np.append(yield_of_all_crop_cycles_irrig, est_yield_irrigated)
            fc1_irr_lst = np.append(fc1_irr_lst, fc1_irr)
            err_list[i_cycle] = error

            if est_yield_irrigated == None or est_yield_irrigated== np.nan:
                raise Exception('Biomass Yield for irrigated not returned. Row_{}_col_{}_Cycle_{}'.format(i_row, i_col, i_cycle))

            if len(yield_of_all_crop_cycles_irrig) != i_cycle+1:
                raise Exception('Irrigated yield list not properly appended. Row_{}_col_{}_Cycle_{}'.format(i_row, i_col, i_cycle))
                        
            if len(fc1_irr_lst) != i_cycle+1 or fc1_irr == None or fc1_irr == np.nan:
                raise Exception('Fc1 irr not properly appended. Row_{}_col_{}_Cycle_{}'.format(i_row, i_col, i_cycle))
            
            if len(fc1_irr_lst)!= i_cycle+1 or fc1_rain == None or fc1_rain == np.nan:
                raise Exception('Fc1 irr not properly appended. Row_{}_col_{}_Cycle_{}'.format(i_row, i_col, i_cycle))
            
            print('{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format(i_cycle,fc1_irr,fc1_rain,fc2_value,est_yield_irrigated,est_yield_moisture_limited, error))


        ########################################
        """Getting Maximum Attainable Yield from the list for irrigated and rainfed conditions and the Crop Calendar"""

        # get agro-climatic yield and crop calendar for IRRIGATED condition
        if np.logical_and(len(yield_of_all_crop_cycles_irrig) == len(fc1_irr_lst), len(yield_of_all_crop_cycles_irrig) == len(fc1_irr_lst)):

            final_yield_irrig = np.max(yield_of_all_crop_cycles_irrig) # Maximum attainable yield

            # Array index where maximum yield is obtained
            i = np.where(yield_of_all_crop_cycles_irrig == np.max(yield_of_all_crop_cycles_irrig))[0][0] # index of maximum yield

            crop_calender_irr = int(i+1)*step_doy # Crop calendar for irrigated condition

            fc1_irr = fc1_irr_lst[i] # fc1 irrigated for the specific crop calendar DOY

        # get agro-climatic yield and crop calendar for RAINFED condition
        if np.logical_and(len(yield_of_all_crop_cycles_rainfed) == len(fc1_rain_lst), len(yield_of_all_crop_cycles_rainfed) == len(fc1_rain_lst)):
            final_yield_rainfed = np.max(yield_of_all_crop_cycles_rainfed) # Maximum attainable yield

            i1 = np.where(yield_of_all_crop_cycles_rainfed == np.max(yield_of_all_crop_cycles_rainfed))[0][0] # index of maximum yield
            
            crop_calender_rain = int(i1+1) * step_doy # Crop calendar for rainfed condition
            
            fc1_rain = fc1_rain_lst[i1]
            
            # if not self.perennial:
            fc2 = fc2_lst[i1]

        final_result = {
            'Crop Calendar Rainfed':[crop_calender_rain],
            'Crop Calendar Irrigated':[crop_calender_irr],
            'Maximum Attainable Yield (rainfed)':[final_yield_rainfed],
            'Maximum Attainable Yield (Irrigated)':[final_yield_irrig],
            'fc1_rainfed':[fc1_rain],
            'fc1_irrigated':[fc1_irr],
            'fc2_rainfed':[fc2],
        }
        simulation ={
            'DOY': np.arange(1,366),
            'Yield_rain':yield_of_all_crop_cycles_rainfed,
            'Yield_irr':yield_of_all_crop_cycles_irrig,
            'fc1_rain': fc1_rain_lst,
            'fc1_irr':fc1_irr_lst,
            'fc2_rain':fc2_lst,
            'Error':err_list
        }
        err_des = {
            0: 'Pass',
            -1: 'First DOY of mean temperature does not meet minimum temperature requirement',
            -2: 'Only rainfed cycle length does not meet minimum cycle requirement',
            -3: 'Only irrigated cycle length does not meet minimum cycle requirement',
            -4: 'Minimum temperature requirement met but minimum cycle length requirement does not meet (Rainfed + Irrigated)'
        }
    
    
        print('\nSimulations Completed !')
        return [general, climate, final_result, simulation, err_des]
    
    
    # New function of kc factor adjustments for local climate (FORTRAN routine)
    