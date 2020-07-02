import pandas as pd 
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from .mincurve import min_curve_method
from .mincurve import survey
from .interpolate import interpolate_deviation, interpolate_position
from .projection import unit_vector, projection_1d
from scipy.interpolate import interp1d
from scipy.spatial import distance_matrix
from pyproj import Proj, transform


class perforations(gpd.GeoDataFrame):

    def __init__(self, *args, **kwargs):
        prod_ind = kwargs.pop("pi", None)
        is_open = kwargs.pop('is_open',None)                                                                                                                                 
        super(perforations, self).__init__(*args, **kwargs)

        if prod_ind is not None:
            assert isinstance(prod_ind,list) 
            assert all(isinstance(i,(int,float)) for i in prod_ind)
            self['pi'] = prod_ind
        elif 'pi' in self.columns:
            assert all(isinstance(i,(int,float)) for i in self['pi'].tolist())

        if is_open is not None:
            assert isinstance(is_open,list)
            assert all(isinstance(i,bool) for i in is_open)
            self['is_open'] = is_open
        elif 'is_open' in self.columns:
            assert all(isinstance(i,bool) for i in self['is_open'].tolist())


    def open_perf(self):
        return self[self['is_open']==True]

    def get_tick(self):
        try:
            self['md_tick'] = self['md_bottom'] - self['md_top']
        except:
            pass

        try:
            self['tvd_tick'] = self['tvd_bottom'] - self['tvd_top']
        except:
            pass
        
        return self
    
    def get_mid_point(self):
        try:
            self['md_mid_point'] = (self['md_bottom'] + self['md_top'])*0.5
        except:
            pass

        try:
            self['tvd_mid_point'] = (self['tvd_bottom'] + self['tvd_top'])*0.5
        except:
            pass
    
        try:
            self['tvdss_mid_point'] = (self['tvdss_bottom'] + self['tvdss_top'])*0.5
        except:
            pass
        return self
        
    
    @property
    def _constructor(self):
        return perforations
    
class tops(gpd.GeoDataFrame):

    def __init__(self, *args, **kwargs):    
        formation = kwargs.pop("formation", None)                                                                                                                               
        super(tops, self).__init__(*args, **kwargs)  

        if formation is not None:
            formation = np.atleast_1d(formation)
            self['formation'] = formation
            self.set_index('formation',inplace=True)
        elif 'formation' in self.columns:
            self.set_index('formation',inplace=True)

    def get_tick(self):
        try:
            self['md_tick'] = self['md_bottom'] - self['md_top']
        except:
            pass

        try:
            self['tvd_tick'] = self['tvd_bottom'] - self['tvd_top']
        except:
            pass
        
        return self
    
    def get_mid_point(self):
        try:
            self['md_mid_point'] = (self['md_bottom'] + self['md_top'])*0.5
        except:
            pass

        try:
            self['tvd_mid_point'] = (self['tvd_bottom'] + self['tvd_top'])*0.5
        except:
            pass
    
        try:
            self['tvdss_mid_point'] = (self['tvdss_bottom'] + self['tvdss_top'])*0.5
        except:
            pass
        return self 
    
    @property
    def _constructor(self):
        return tops

   
class well:
    def __init__(self, **kwargs):

        self.name = kwargs.pop('name', None)
        self.rte = kwargs.pop('rte', None)
        self.surf_coord = kwargs.pop('surf_coord', None)
        self.crs = kwargs.pop('crs', None)
        self.perforations = kwargs.pop('perforations', None)
        self.tops = kwargs.pop('tops', None)
        self.td = kwargs.pop('td',None)  # First set td before survey
        self.survey = kwargs.pop('survey', None)
        self.pi = kwargs.pop('pi',None)


#####################################################
############## Properties ###########################

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self,value):
        assert isinstance(value,(str,type(None))), f'{type(value)} not accepted. Name must be str'
        self._name = value

    @property
    def rte(self):
        return self._rte

    @rte.setter
    def rte(self,value):
        assert isinstance(value,(int,float,type(None))), f'{type(value)} not accepted. Name must be number'
        self._rte = value

    @property
    def surf_coord(self):
        return self._surf_coord

    @surf_coord.setter
    def surf_coord(self,value):
        assert isinstance(value,(list,Point,type(None))), f'{type(value)} not accepted. Name must be shapely.geometry.Point or list [x,y,z]'
        if isinstance(value,Point):
            self._surf_coord = value
        elif isinstance(value,list):
            assert len(value) <= 3 and len(value) >= 2
            if len(value)==3:
                self._surf_coord = Point(value[0],value[1],value[2])
            elif len(value)==2:
                self._surf_coord = Point(value[0],value[1])


    @property
    def crs(self):
        return self._crs

    @crs.setter
    def crs(self,value):
        assert isinstance(value,(int,str,type(None))), f"{type(value)} not accepted. Name must be str. Example 'EPSG:3117'"
        
        if isinstance(value,int):
            value = f'EPSG:{value}'
        elif isinstance(value,str):
            assert value.startswith('EPSG:'), 'if crs is string must starts with EPSG:. If integer must be the Coordinate system reference number EPSG http://epsg.io/'
        self._crs = value

    @property
    def perforations(self):
        return self._perforations

    @perforations.setter
    def perforations(self,value):
        assert isinstance(value,(perforations,type(None))), f'{type(value)} not accepted. Name must be reservoirpy.wellpy.path.perforations'
        if self.crs is not None and value is not None:
            value.crs = self.crs
        self._perforations = value

    @property
    def tops(self):
        return self._tops

    @tops.setter
    def tops(self,value):
        assert isinstance(value,(tops,type(None))), f'{type(value)} not accepted. Name must be reservoirpy.wellpy.path.tops'
        if self.crs is not None and value is not None:
            value.crs = self.crs
        self._tops = value    


    @property
    def survey(self):
        return self._survey

    @survey.setter
    def survey(self,value):
        if isinstance(value,survey):
            self._survey = value
        elif isinstance(value,pd.DataFrame):
            assert all(i in value.columns for i in ['md','inc','azi'])
            _survey = min_curve_method(
                value['md'],
                value['inc'],
                value['azi'],
                surface_easting=self._surf_coord.x, 
                surface_northing=self._surf_coord.y, 
                kbe=self._rte,
                crs=self._crs)
            self._survey = _survey
        elif isinstance(value,type(None)):
            _survey = min_curve_method(
                np.array([0,self.td]),
                np.zeros(2),
                np.zeros(2),
                surface_easting=self._surf_coord.x, 
                surface_northing=self._surf_coord.y, 
                kbe=self._rte,
                crs=self._crs)
            self._survey = _survey

    @property
    def td(self):
        return self._td

    @td.setter
    def td(self,value):
        if value is None:
            self._td = 10000
        else:
            assert isinstance(value,(int,float))
            self._td = value

    @property
    def pi(self):
        return self._pi 

    @pi.setter 
    def pi(self,value):
        assert isinstance(value,(type(None),dict)), "Pi must be a dictionary indexed by formation (Key)"
        if isinstance(value,dict):
            assert all(isinstance(value[i],(int,float)) for i in value)
        self._pi = value

#####################################################
############## methods ###########################

    def sample_deviation(self,step=100):
        if self._survey is not None:
            _survey = self.survey
            new_dev = interpolate_deviation(_survey.index, 
                                            _survey['inc'], 
                                            _survey['azi'], md_step=step)
        else:
            raise ValueError("No survey has been set")
        return new_dev

    def sample_position(self,step=100):
        if self._survey is not None:
            _survey = self.survey
            new_pos = interpolate_position(_survey['tvd'], 
                                            _survey['easting'], 
                                            _survey['northing'], 
                                            tvd_step=step)
            new_pos_gpd = gpd.GeoDataFrame(new_pos,geometry=gpd.points_from_xy(new_pos.new_easting,new_pos.new_northing),crs=self._crs)
        else:
            raise ValueError("No survey has been set")
        return new_pos_gpd

    """
            #Set the depth interpolators
            self._tvd_int = interp1d(self.survey.index,self.survey['tvd'])
            self._tvdss_int = interp1d(self.survey.index,self.survey['tvdss'])
            self._northing_int = interp1d(self.survey['tvd'],self.survey.geometry.y)
            self._easting_int = interp1d(self.survey['tvd'],self.survey.geometry.x)
        else:
            self.survey=None
"""

    def to_tvd(self,md:(int,float)=None,which:list=None, ss:bool=False,tick=True):
        if self._survey is not None:
            r = None
            _survey=self.survey
            _tvd_int = interp1d(_survey.index,_survey['tvd'],fill_value='extrapolate')
            _tvdss_int = interp1d(_survey.index,_survey['tvdss'],fill_value='extrapolate')

            if md is not None:
                if ss==True:
                    _tvdss = _tvdss_int(md)
                    r = _tvdss
                else:
                    _tvd = _tvd_int(md)
                    r = _tvd
                
            if which is not None:
                if 'perforations' in which:
                    if self._perforations is not None:
                        if ss==True:
                            if 'md_top' in self._perforations.columns:
                                self._perforations['tvdss_top']=self._perforations['md_top'].apply(_tvdss_int)
                            if 'md_bottom' in self._perforations.columns:
                                self._perforations['tvdss_bottom']=self._perforations['md_bottom'].apply(_tvdss_int)
                        else:
                            if 'md_top' in self._perforations.columns:
                                self._perforations['tvd_top']=self._perforations['md_top'].apply(_tvd_int)
                            if 'md_bottom' in self._perforations.columns:
                                self._perforations['tvd_bottom']=self._perforations['md_bottom'].apply(_tvd_int)
                            if 'tvd_bottom' in self._perforations.columns and 'tvd_bottom' in self._perforations.columns and tick==True:
                                self._perforations['tvd_tick'] = self._perforations['tvd_bottom'] - self._perforations['tvd_top']
                    else:
                        raise ValueError("No perforations have been set")


                if 'tops' in which:
                    if self._tops is not None:
                        if ss==True:
                            if 'md_top' in self._tops.columns:
                                self._tops['tvdss_top']=self._tops['md_top'].apply(_tvdss_int)
                            if 'md_bottom' in self._tops.columns:
                                self._tops['tvdss_bottom']=self._tops['md_bottom'].apply(_tvdss_int)
                        else:
                            if 'md_top' in self._tops.columns:
                                self._tops['tvd_top']=self._tops['md_top'].apply(_tvd_int)
                            if 'md_bottom' in self._tops.columns:
                                self._tops['tvd_bottom']=self._tops['md_bottom'].apply(_tvd_int)
                            if 'tvd_bottom' in self._tops.columns and 'tvd_bottom' in self._tops.columns and tick==True:
                                self._tops['tvd_tick'] = self._tops['tvd_bottom'] - self._tops['tvd_top']
                    else:
                        raise ValueError("No tops have been set")
                
        else:
            raise ValueError("No survey has been set")
        return r
  

    
    def to_coord(self,md:(int,float)=None,which:list=None):
        if self._survey is not None:
            r=None
            _survey=self.survey
            _northing_int = interp1d(_survey['tvd'],_survey.geometry.y,fill_value='extrapolate')
            _easting_int = interp1d(_survey['tvd'],_survey.geometry.x,fill_value='extrapolate')
            _tvd_int = interp1d(_survey.index,_survey['tvd'],fill_value='extrapolate')
            if md is not None:
                _tvd = _tvd_int(md)
                _northing = _northing_int(_tvd)
                _easting = _easting_int(_tvd)
                coord = Point(_easting,_northing)
                r = coord
                
            if which is not None:
                if 'perforations' in which:
                    if self._perforations is not None:
                        try:
                            self._perforations['northing'] = self._perforations['tvd_top'].apply(_northing_int)
                            self._perforations['easting'] = self._perforations['tvd_top'].apply(_easting_int)
                            self._perforations['geometry'] = self._perforations[['northing', 'easting']].apply(lambda x: Point(x['easting'],x['northing']),axis=1)
                        except:
                            ValueError("No tvd has been set")
                    else:
                        raise ValueError("No perforations have been set")
                        
                if 'tops' in which:
                    if self._tops is not None:
                        try:
                            self._tops['northing'] = self._tops['tvd_top'].apply(_northing_int)
                            self._tops['easting'] = self._tops['tvd_top'].apply(_easting_int)
                            self._tops['geometry'] = self._tops[['northing', 'easting']].apply(lambda x: Point(x['easting'],x['northing']),axis=1)
                        except:
                            ValueError("No tvd has been set")
                    else:
                        raise ValueError("No tops have been set")
        else:
            raise ValueError("No survey has been set")
        return r


    def get_pi_from_perforations(self,is_open=False, inplace=True):
        """
        Estimate the Productivity Index by formation with the self.perforations attribute.

        The self.perforations attribute must have a column 'pi' with the Productivity Index for 
        the interval. If the column 'is_open' is present and the keyword 'is_open' is true the 
        productivity Index is calculated for the Open Formations.

        Productivity index is grouped by formation and sum.

        If the column 'formation' is not present a single item dictionary is calculated

        Input:
            is_open -> (bool, False).
        Return:
            pi -> (dict) Dictionary with the productivity index by formation
        """
        assert self.perforations is not None, 'To estimate Pi from Perf, perf must be defined'
        _perf = self.perforations
        _keys = ['formation','pi','fluid']
        assert all(i in _perf.columns for i in _keys)

        # If is_open only take the opene.reset_index().set_index('fm')d intervals
        if is_open and 'is_open' in _perf.columns:
            _perf = _perf[_perf['is_open']==True]

        #Group by and sum aggregate
        _pi_df = _perf.groupby(['fluid','formation']).agg({'pi':'sum'}).to_dict()['pi']
        _pi_dict = _pi_df.reset_index().set_index('formation').to_dict(orient='index')

        if inplace:
            self._pi = _pi_dict

        return _pi_dict
        
class wells_group:
    def __init__(self,*args):
        _well_list = []

        if args is not None:
            for i in args:
                _well_list.append(i)
        
        self.wells = _well_list 

    @property
    def wells(self):
        return self._wells

    @wells.setter 
    def wells(self,value):
        assert isinstance(value,list)
        if not value:
            self._wells = {}
        else:
            assert all(isinstance(i,well) for i in value)
            w_dict={}
            for i in value:
                w_dict[i.name] = i
            self._wells = w_dict

    def add_well(self,*args):
        _add_well = []

        if args is not None:
            for i in args:
                _add_well.append(i)

        assert all(isinstance(i,well) for i in _add_well)

        _wells_dict = self.wells.copy()

        for i in _add_well:
            _wells_dict[i.name] = i
        self._wells = _wells_dict

    # Methods

    def describe(self):
        """
        Get a dataframe describing the attributes of each well

        Return:
            df -> (gpd.GeoDataFrame) 
        """
        gdf = gpd.GeoDataFrame()

        for well in self.wells:
            dict_attr = {
                'rte':[self.wells[well].rte],
                'surf_coord':[self.wells[well].surf_coord],
                'crs':[self.wells[well].crs],
                'survey': [False if self.wells[well].survey is None else True],
                'perforations': [False if self.wells[well].perforations is None else True],
                'tops': [False if self.wells[well].tops is None else True],
                'openlog': [False if self.wells[well].openlog is None else True],
                'masterlog': [False if self.wells[well].masterlog is None else True],
                'caselog': [False if self.wells[well].caselog is None else True],
                }
            _well_gpd = gpd.GeoDataFrame(dict_attr, index=[well])
            gdf = gdf.append(_well_gpd)

        gdf = gdf.set_geometry('surf_coord')

        return gdf

    def wells_tops(self, wells:list=None, formations:list=None, projection1d = False, azi=90, center=None):
        """
        Get a DataFrame with the wells formations tops
        Input:
            wells ->  (list, None) List of wells in the Group to show
                    If None, all wells in the group will be selected
            formations ->  (list, None) List of formation in the Group to show 
                    If None, all formations in the group will be selected
            projection1d ->  (bool, default False) If true it adds a column with a 1d projection of coordinates 
            azi -> (int, float, np.ndarray, default 90) Azimuth direction for projection
            center -> (list, np.nd.ndarray)  Center for the projection

        Return:
            tops -> (gpd.GeoDataFrame) GeoDataFrame with tops indexed by well
        """        
        assert isinstance(wells,(list,type(None)))
        assert isinstance(formations,(list,type(None)))
        assert isinstance(center,(list,np.ndarray, type(None)))
        assert isinstance(azi,(int,float,np.ndarray))
        # Define which wells for the distance matrix will be shown    
        if wells is None:
            _well_list = []
            for key in self.wells:
                _well_list.append(key)
        else:
            _well_list = wells

        _wells_tops = gpd.GeoDataFrame()

        for well in _well_list:
            if self.wells[well].tops is None:
                continue
            else:
                if self.wells[well].survey is not None:
                    self.wells[well].to_tvd(which=['tops'])
                    self.wells[well].to_tvd(which=['tops'],ss=True)
                    self.wells[well].to_coord(which=['tops'])
                else:
                    assert projection1d == False, 'If projection1d is True surveys must be set'
                _tops = self.wells[well].tops.copy()
                _tops['well'] = well
                _wells_tops = _wells_tops.append(_tops, ignore_index=False)
        
        if formations is not None:
            _wells_tops = _wells_tops.loc[formations]

        _wells_tops = _wells_tops.reset_index()
        
        if projection1d == True:
            _pr,c = projection_1d(_wells_tops[['easting','northing']].values, azi, center=center)
            _wells_tops['projection'] = _pr
            r=[_wells_tops,c]
        else:
            r=_wells_tops

        return r

    def wells_surveys(self, wells:list=None, projection1d = False, azi=90, center=None):
        """
        Get a DataFrame with the wells surveys
        Input:
            wells ->  (list, None) List of wells in the Group to show
                    If None, all wells in the group will be selected
            formations ->  (list, None) List of formation in the Group to show 
                    If None, all formations in the group will be selected
        Return:
            tops -> (gpd.GeoDataFrame) GeoDataFrame with tops indexed by well
        """    
        assert isinstance(wells,(list,type(None)))
        assert isinstance(center,(list,np.ndarray, type(None)))
        assert isinstance(azi,(int,float,np.ndarray))
        # Define which wells for the distance matrix will be shown    
        if wells is None:
            _well_list = []
            for key in self.wells:
                _well_list.append(key)
        else:
            _well_list = wells

        _wells_survey = gpd.GeoDataFrame()

        for well in _well_list:
            if self.wells[well].survey is None:
                continue
            else:
                _s = self.wells[well].survey.copy()
                _s['well'] = well 
                _s = _s.reset_index()
                _wells_survey = _wells_survey.append(gpd.GeoDataFrame(_s))

        if projection1d == True:
            _pr,c = projection_1d(_wells_survey[['easting','northing']].values, azi, center=center)
            _wells_survey['projection'] = _pr
            r=[_wells_survey,c]
        else:
            r=_wells_survey

        return r

    def wells_perforations(self, wells:list=None):
        """
        Get a DataFrame with the wells perforations
        Input:
            wells ->  (list, None) List of wells in the Group to show
                    If None, all wells in the group will be selected
            formations ->  (list, None) List of formation in the Group to show 
                    If None, all formations in the group will be selected
        Return:
            tops -> (gpd.GeoDataFrame) GeoDataFrame with tops indexed by well
        """    
        assert isinstance(wells,(list,type(None)))

        # Define which wells for the distance matrix will be shown    
        if wells is None:
            _well_list = []
            for key in self.wells:
                _well_list.append(key)
        else:
            _well_list = wells

        _wells_survey = gpd.GeoDataFrame()

        for well in _well_list:
            if self.wells[well].perforations is None:
                continue
            else:
                _s = self.wells[well].perforations.copy()
                _s['well'] = well 
                _s = _s.reset_index()
                _wells_survey = _wells_survey.append(gpd.GeoDataFrame(_s))

        return _wells_survey


    def wells_coordinates(self, wells:list=None, z_unit='ft', to_crs='EPSG:4326'):
        """
        Get a DataFrame with the wells surface coordinates
        Input:
            wells ->  (list, None) List of wells in the Group to show the matrix. 
                    If None, all wells in the group will be selected
        Return:
            wells_coord -> (gpd.GeoDataFrame) GeoDataFrame with wells coords
        """
        assert isinstance(wells,(list,type(None)))

        # Define which wells for the distance matrix will be shown    
        if wells is None:
            _well_list = []
            for key in self.wells:
                _well_list.append(key)
        else:
            _well_list = wells

        #Create coordinates dataframe
        _coord = gpd.GeoDataFrame()

        z_coef = 0.3048 if z_unit=='ft' else 1

        for well in _well_list:
            x_coord = self.wells[well].surf_coord.x
            y_coord = self.wells[well].surf_coord.y
            z_coord = self.wells[well].surf_coord.z*z_coef if self.wells[well].surf_coord.has_z==True else self.wells[well].rte*z_coef
            shape = self.wells[well].surf_coord
            crs = self.wells[well].crs
            _w = gpd.GeoDataFrame({'x':[x_coord],'y':[y_coord],'z':[z_coord],'geometry':[shape]}, index=[well])
            _w.crs = crs
            _w = _w.to_crs(to_crs)
            _w['lon'] = _w['geometry'].x
            _w['lat'] = _w['geometry'].y
            _coord = _coord.append(_w)

        return _coord


    def wells_distance(self,wells:list=None, dims:list=['x','y','z'], z_unit:str='ft'):
        """
        Calculate a distance matrix for the surface coordinates of the wells

        Input:
            wells ->  (list, None) List of wells in the Group to show the matrix. 
                    If None, all wells in the group will be selected
            z ->  (Bool, default False). Take into account the z component. Z must be in the same
                    units of x, y coord
            z_unit -> (str, default 'ft') Indicate the units of the z coord. 
                    If 'ft' the z is multiplied by 0.3028 otherwise by 1

        Return:
            dist_matrix -> (pd.DataFrame) Distance matrix with index and column of wells
        """
        
        assert isinstance(wells,(list,type(None)))

        _coord = self.wells_coordinates(wells=wells, z_unit=z_unit)

        dist_array = distance_matrix(_coord[dims].values,_coord[dims].values)
        dist_matrix = pd.DataFrame(dist_array,index=_coord.index, columns=_coord.index)

        return dist_matrix

    def formation_distance(self, wells:list=None, formation:str=None, dims:list=['easting','northing','tvdss_top'], z_unit='ft'):
        """
        Calculate a distance matrix for the formation of interest

        Input:
            wells ->  (list, None) List of wells in the Group to show the matrix. 
                    If None, all wells in the group will be selected
            formation -> (str) Formation of interest. The attributes tops and survey must be set on each well
        Return:
            dist_matrix -> (pd.DataFrame) Distance matrix with index and column of wells
        """
        assert isinstance(wells,(list,type(None)))

        # Define which wells for the distance matrix will be shown    
        if wells is None:
            _well_list = []
            for key in self.wells:
                _well_list.append(key)
        else:
            _well_list = wells

        z_coef = 0.3048 if z_unit=='ft' else 1

        _fm_df = gpd.GeoDataFrame()
        for key in _well_list:
            has_survey = self.wells[key].survey is not None
            has_tops = self.wells[key].tops is not None
            if all([has_tops,has_survey]):
                assert formation in self.wells[key].tops.index.tolist()
                if 'tvdss_top' not in self.wells[key].tops.columns:
                    self.wells[key].to_tvd(which=['tops'])
                    self.wells[key].to_tvd(which=['tops'],ss=True)
                if 'geometry' not in self.wells[key].tops.columns:
                    self.wells[key].to_coord(which=['tops'])
                _df = self.wells[key].tops.loc[[formation],['easting','northing','tvdss_top']].reset_index()
                _df['well'] = key
                _df['tvdss_top'] = _df['tvdss_top']*z_coef
                #print(_df)
                _fm_df = _fm_df.append(_df, ignore_index=True)
                
        
        dist_array = distance_matrix(_fm_df[dims].values,_fm_df[dims].values)
        dist_matrix = pd.DataFrame(dist_array,index=_fm_df['well'], columns=_fm_df['well'])

        return dist_matrix
















        


        




    

