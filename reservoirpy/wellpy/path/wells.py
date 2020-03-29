import pandas as pd 
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from .mincurve import min_curve_method
from .interpolate import interpolate_deviation, interpolate_position
from scipy.interpolate import interp1d
from ...welllogspy.log import log


class perforations(gpd.GeoDataFrame):

    def __init__(self, *args, **kwargs):                                                                                                                                   
        super(perforations, self).__init__(*args, **kwargs)
    
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
        super(tops, self).__init__(*args, **kwargs)     
    
    @property
    def _constructor(self):
        return tops
  
    
class well:
    def __init__(self,**kwargs):
        self.name = kwargs.pop("name", 'Well')
        assert isinstance(self.name,str)
        
        self.rte = kwargs.pop("rte", None)
        assert isinstance(self.rte,(int,float)) or self.rte is None
        
        self.surf_coord = kwargs.pop("surf_coord", None)
        assert isinstance(self.surf_coord, Point) or self.surf_coord is None
        
        self.perforations = kwargs.pop("perforations", None)
        assert isinstance(self.perforations, perforations) or self.perforations is None

        self.tops = kwargs.pop("tops", None)
        assert isinstance(self.tops, tops) or self.tops is None

        self.masterlog = kwargs.pop('masterlog', None)
        assert isinstance(self.masterlog, log) or self.masterlog is None

        self.openlog = kwargs.pop('openlog', None)
        assert isinstance(self.openlog, log) or self.openlog is None

        self.caselog = kwargs.pop('caselog', None)
        assert isinstance(self.caselog, log) or self.caselog is None
        
        self.crs = kwargs.pop("crs", None)        
        _deviation = kwargs.pop("deviation",None)
        
        if _deviation is not None:
            _survey = min_curve_method(_deviation['md'],_deviation['inc'],
                                       _deviation['azi'],
                                       surface_easting=self.surf_coord.x, 
                                       surface_northing=self.surf_coord.y, 
                                       kbe=self.rte)
        
            self.survey = gpd.GeoDataFrame(_survey,
                         geometry=gpd.points_from_xy(_survey.easting, 
                                                     _survey.northing),crs=self.crs)
            self._tvd_int = interp1d(self.survey.index,self.survey['tvd'])
            self._tvdss_int = interp1d(self.survey.index,self.survey['tvdss'])
            self._northing_int = interp1d(self.survey['tvd'],self.survey.geometry.y)
            self._easting_int = interp1d(self.survey['tvd'],self.survey.geometry.x)
        else:
            self.survey=None

        if self.perforations is not None:
            self.perforations['md_tick'] = self.perforations['md_bottom'] - self.perforations['md_top']
            
    def sample_deviation(self,step=100):
        if self.survey is not None:
            new_dev = interpolate_deviation(self.survey.index, 
                                            self.survey['inc'], 
                                            self.survey['azi'], md_step=step)
        else:
            raise ValueError("No survey has been set")
        return new_dev

    def sample_position(self,step=100):
        if self.survey is not None:
            new_pos = interpolate_position(self.survey['tvd'], 
                                            self.survey['easting'], 
                                            self.survey['northing'], 
                                            tvd_step=step)
            new_pos_gpd = gpd.GeoDataFrame(new_pos,geometry=gpd.points_from_xy(new_pos.new_easting,new_pos.new_northing),crs=self.crs)
        else:
            raise ValueError("No survey has been set")
        return new_pos_gpd
    
    def to_tvd(self,md:(int,float)=None,which:list=None, ss:bool=False):
        if self.survey is not None:
            r=[]
            if md is not None:
                if ss==True:
                    _tvdss = self._tvdss_int(md)
                    r.append(_tvdss)
                else:
                    _tvd = self._tvd_int(md)
                    r.append(_tvd)
                
            if which is not None:
                if 'perforations' in which:
                    if self.perforations is not None:
                        if ss==True:
                            self.perforations['tvdss_top']=self.perforations['md_top'].apply(self._tvdss_int)
                            self.perforations['tvdss_bottom']=self.perforations['md_bottom'].apply(self._tvdss_int)
                        else:
                            self.perforations['tvd_top']=self.perforations['md_top'].apply(self._tvd_int)
                            self.perforations['tvd_bottom']=self.perforations['md_bottom'].apply(self._tvd_int)
                            self.perforations['tvd_tick'] = self.perforations['tvd_bottom'] - self.perforations['tvd_top']
                        r.append(self.perforations)
                    else:
                        raise ValueError("No perforations have been set")


                if 'tops' in which:
                    if self.tops is not None:
                        if ss==True:
                            self.tops['tvdss_top']=self.tops['md_top'].apply(self._tvdss_int)
                            self.tops['tvdss_bottom']=self.tops['md_bottom'].apply(self._tvdss_int)
                        else:
                            self.tops['tvd_top']=self.tops['md_top'].apply(self._tvd_int)
                            self.tops['tvd_bottom']=self.tops['md_bottom'].apply(self._tvd_int)
                            self.tops['tvd_tick'] = self.tops['tvd_bottom'] - self.tops['tvd_top']
                        r.append(self.tops)
                    else:
                        raise ValueError("No tops have been set")

        else:
            raise ValueError("No survey has been set")
        return r
    

    
    def to_coord(self,md:(int,float)=None,which:list=None):
        if self.survey is not None:  
            r=[]
            if md is not None:
                _tvd = self._tvd_int(md)
                _northing = self._northing_int(_tvd)
                _easting = self._easting_int(_tvd)
                coord = Point(_easting,_northing)
                r.append(coord)
                
            if which is not None:
                if 'perforations' in which:
                    if self.perforations is not None:
                        try:
                            self.perforations['northing'] = self.perforations['tvd_top'].apply(self._northing_int)
                            self.perforations['easting'] = self.perforations['tvd_bottom'].apply(self._easting_int)
                            self.perforations['geometry'] = self.perforations[['northing', 'easting']].apply(lambda x: Point(x['easting'],x['northing']),axis=1)
                            r.append(self.perforations)
                        except:
                            ValueError("No tvd has been set")
                    else:
                        raise ValueError("No perforations have been set")
                        
                if 'tops' in which:
                    if self.tops is not None:
                        try:
                            self.tops['northing'] = self.tops['tvd_top'].apply(self._northing_int)
                            self.tops['easting'] = self.tops['tvd_bottom'].apply(self._easting_int)
                            self.tops['geometry'] = self.tops[['northing', 'easting']].apply(lambda x: Point(x['easting'],x['northing']),axis=1)
                            r.append(self.tops)
                        except:
                            ValueError("No tvd has been set")
                    else:
                        raise ValueError("No tops have been set")
        else:
            raise ValueError("No survey has been set")
        return r

    def tops_to_logs(self,which:list=None):
        if self.tops is None:
            raise ValueError("No tops have been set")
        else:
            if which is None:
                raise ValueError("No log specification")
            else:
                if ('masterlog' in which) & (self.masterlog is not None):
                    _d = self.masterlog.df().index
                    _m = pd.DataFrame(index=_d)
                    for i in self.tops.iterrows():
                        _m.loc[(_m.index>=i[1]['md_top'])&(_m.index<=i[1]['md_bottom']),'formation'] = i[1]['formation']
                    self.masterlog.add_curve('formation',_m['formation'].values,descr='formations')
                if ('openlog' in which) & (self.openlog is not None):
                    _d = self.openlog.df().index
                    _m = pd.DataFrame(index=_d)
                    for i in self.tops.iterrows():
                        _m.loc[(_m.index>=i[1]['md_top'])&(_m.index<=i[1]['md_bottom']),'formation'] = i[1]['formation']
                    self.openlog.add_curve('formation',_m['formation'].values,descr='formations')
                if ('caselog' in which) & (self.caselog is not None):
                    _d = self.caselog.df().index
                    _m = pd.DataFrame(index=_d)
                    for i in self.tops.iterrows():
                        _m.loc[(_m.index>=i[1]['md_top'])&(_m.index<=i[1]['md_bottom']),'formation'] = i[1]['formation']
                    self.caselog.add_curve('formation',_m['formation'].values,descr='formations')

    def add_to_logs(self,df):
        if self.openlog is None:
            raise ValueError("openlog has not been added")
        else:
            #col_exist = self.openlog.df().columns
            col_add = df.columns[~df.columns.isin(np.intersect1d(df.columns, self.openlog.df().columns))]
            df_merge = self.openlog.df().merge(df[col_add], how='left', left_index=True,right_index=True)

            for i in df_merge[col_add].iteritems():
                self.openlog.add_curve(i[0],i[1])

    def interval_attributes(self,perforations:bool=False, 
                            intervals:perforations=None, 
                            curves:list = None,
                            aggfunc = ['min','max','mean']):
        if perforations == True :
            p = self.perforations
        else:
            p = intervals 
          
        curves.append('inter')
        log_appended = pd.DataFrame()
        #add column to identify the interval
        for i,c in p.iterrows():
            logdf = self.openlog.df().copy()
            logdf.loc[(logdf.index >= c['md_top'])&(logdf.index<=c['md_bottom']),'inter']=i
            
            #filter all the intervals
            logdf = logdf[~logdf['inter'].isnull()]

            #Group and aggregate functions
            log_grp = logdf[curves].groupby('inter').agg(aggfunc)
            log_appended = log_appended.append(log_grp)
        p_result = pd.concat([p,log_appended],axis=1)
        if perforations ==True:
            self.perforations = p_result 
            
        return p_result
            

        
        return p_result
        
