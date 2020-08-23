import numpy as np

class initial_conditions:
    def __init__(self,**kwargs):
        self.pi = kwargs.pop('pi', None)
        self.woc = kwargs.pop('woc',None)
        self.goc = kwargs.pop('goc', None)
        self.cap_press_init = kwargs.pop('cap_press_init', True)

    #properties

    @property
    def pi(self):
        return self.pi 

    @pi.setter 
    def pi(self,value):
        assert isinstance(value, (int, float,np.float64, np.int64))
        self._pi = value

    @property
    def woc(self):
        return self.woc 

    @woc.setter 
    def woc(self,value):
        if value is not None:
            assert isinstance(value, (int, float,np.float64, np.int64))
        self._woc = value

    @property
    def goc(self):
        return self.goc 

    @goc.setter 
    def goc(self,value):
        if value is not None:
            assert isinstance(value, (int, float,np.float64, np.int64))
        self._goc = value
    
    @property
    def cap_press_init(self):
        return self.cap_press_init 

    @cap_press_init.setter 
    def cap_press_init(self,value):
        assert isinstance(value, bool)
        self._cap_press_init = value
