import numpy as np
import pandas as pd
from numpy.polynomial.polynomial import polyval
from scipy.interpolate import interp1d

#####################################################################################
#####################################################################################
############################ OIL CORRELATIONS #######################################

def api_to_sg(api):
    api = np.atleast_1d(api)
    sg = 141.5/(131.5+api)
    return sg

def sg_to_api(sg):
    sg = np.atleast_1d(sg)
    api = (141.5/sg)-131.5
    return api

#####################################################################################
# Bubble point Correlations

#Correction by Non-Hydrocarbon gases

#Correction by N2
def n2_correction(api=None,temp=None,y=0):
    if y==0:
        cn2 = 1
    else:
        cn2 = 1.0 + ((-2.65e-4 * api + 5.5e-3)*temp + (0.0931*api - 0.8295))*y + ((1.954e-11 * np.power(api,4.699)*temp)+(0.027*api - 2.366))*np.power(y,2)
    return cn2 

def co2_correction(y=0,temp=None):
    if y==0:
        cco2 = 1
    else:
        cco2 = 1.0 - 693.8*y*np.power(temp,-1.553)
    return cco2 

def h2s_correction(api=None,y=0,temp=None):
    if y==0:
        ch2s = 1
    else:
        ch2s = 1.0 - (0.9035 + 0.0015*api)*y + 0.019*(45-api)*np.power(y,2)
    return ch2s 

#Standing
def pb(rs=None,temp=None,sg_gas=None,api=None,method='standing', multiple=False, correction=True,**kwargs):
    """
    Estimate the bubble point pressure using Correlations

    Input: 
        rs -> (int,float,np.array) Solution Gas Ratio [scf/bbl]
        temp -> (int,float,np.array) Temperature [F]
        sg_gas -> (int,float,np.array) Specific Gravity gas (air=1)
        api -> (int,float,np.array) Oil API gravity [API]
        method -> (list, default 'standing')List of correlation methods
                  ['standing',laster,'vazquez_beggs','glaso']
        multiple->(bool, default False) Allow to return multiple result from multiple correlation
                  If true the 'method' must be a length equal to 1
        correction->(bool, default True) Apply correction factors for non-hydrocarbon elements
    
    Return:
        pb -> (pd.DataFrame) Bubble Point Pressure indexed by temperature

    Source: Correlaciones Numericas PVT - Carlos Banzer
    """
    assert isinstance(rs,(int,float,list,np.ndarray))
    rs = np.atleast_1d(rs)

    assert isinstance(temp,(int,float,list,np.ndarray))    
    temp = np.atleast_1d(temp)

    assert isinstance(sg_gas,(int,float,list,np.ndarray))    
    sg_gas = np.atleast_1d(sg_gas)

    assert isinstance(api,(int,float,list,np.ndarray))    
    api = np.atleast_1d(api)

    assert isinstance(method,(str,list))

    methods = []
     
    if isinstance(method,str):
        methods.append(method)
        multiple = False
    else:
        methods.extend(method)
        multiple = True

    #Corrections for non Hydrocarbon gases
    y_n2 = kwargs.pop('y_n2',0)
    y_co2 = kwargs.pop('y_co2',0)
    y_h2s = kwargs.pop('y_h2s',0)

    cn2 = n2_correction(y=y_n2,api=api,temp=temp) if correction==True else 1
    cco2 = co2_correction(y=y_co2,temp=temp) if correction==True else 1
    ch2s = h2s_correction(y=y_h2s,api=api,temp=temp) if correction==True else 1

    pb_dict = {}
     
    if 'standing' in methods:
        f = np.power(rs/sg_gas,0.83) * np.power(10,0.00091*temp - 0.0125*api)
        pb_standing = 18.2 * (f - 1.4)
        pb = pb_standing * cn2 * cco2 * ch2s
        pb_dict['pb_standing'] = pb

    if 'laster' in methods:
        #estimate oil effective molecular weight
        mo = np.zeros(api.shape)
        mo[api<=40] = 630-10*api[api<=40]
        mo[api>40] = 73110*np.power(api[api>40],-1.562)


        #estimate system gas molar fraction
        sg_oil = api_to_sg(api) 
        yg = ((rs/379.3))/((rs/379.3)+(350*sg_oil/mo))


        pb_factor = np.zeros(yg.shape)
        pb_factor[yg<=0.6] = 0.679*np.exp(2.786*yg[yg<=0.6])-0.323
        pb_factor[yg>0.6] = 8.26 * np.power(yg[yg>0.6],3.56) +1.95 

        temp_r = temp + 459.67
        pb_laster = pb_factor * temp_r/sg_gas

        pb = pb_laster * cn2 * cco2 * ch2s
        pb_dict['pb_laster'] = pb
    
    if 'vazquez_beggs' in methods:
        #Constants c1, c2, c3
        c1 = np.zeros(api.shape)
        c2 = np.zeros(api.shape)
        c3 = np.zeros(api.shape)

        c1[api<=30] = 0.0362
        c1[api>30] = 0.0178

        c2[api<=30] = 1.0937
        c2[api>30] = 1.1870

        c3[api<=30] = 25.724
        c3[api>30] = 23.931

        pb_vasquez = np.power(rs/(c1*sg_gas*np.exp((c3*api)/(temp+460))),1/c2)
        pb = pb_vasquez * cn2 * cco2 * ch2s
        pb_dict['pb_vazquez_beggs'] = pb

    if 'glaso' in methods:
        f = np.power(rs/sg_gas,0.816)*((np.power(temp,0.172))/(np.power(api,0.989)))

        pb_glaso = np.power(10,polyval(np.log10(f),[1.7669,1.7447,-0.30218]))
        pb = pb_glaso* cn2 * cco2 * ch2s
        pb_dict['pb_glaso'] = pb

    pb_df = pd.DataFrame(pb_dict,index=temp) if multiple==True else pd.DataFrame({'pb':pb},index=temp)
    pb_df.index.name='temp'
    return pb_df


#####################################################################################
# gas-Oil Ratio Correlations

def rs(p=None,pb=None,temp=None,api=None,sg_gas=None,rsb=None,method='standing',multiple=False,**kwargs):
    """
    Estimate the Gas-Oil Ratio using Standing Correlation

    Input: 
        p -> (int,float,np.array) Interest Pressure [psi]
        pb -> (int,float,np.array) Bubble Point [psi]
        temp -> (int,float,np.array)Temperature [F]
        api -> (int,float,np.array)Oil API gravity [API]
        sg_gas -> (int,float,np.array) Gas specifi gravity
        rsb -> (int,float,np.array) Gas oil ration at bubble point
        method -> (list, default 'standing')List of correlation methods
                  ['standing',laster,'vazquez_beggs','glaso','valarde']
                  * Valarde method builds rs below pb given rsb
        multiple->(bool, default False) Allow to return multiple result from multiple correlation
                  If true the 'method' must be a length equal to 1
    
    Return:
        rs -> (pd.DataFrame) Gas Oil Ratio indexed by pressure

    Source: Correlaciones Numericas PVT - Carlos Banzer
    """
    assert isinstance(p,(int,float,list,np.ndarray))
    p = np.atleast_1d(p)

    assert isinstance(pb,(int,float,list,np.ndarray))
    pb = np.atleast_1d(pb)

    assert isinstance(temp,(int,float,list,np.ndarray))   
    temp = np.atleast_1d(temp)

    assert isinstance(api,(int,float,list,np.ndarray))     
    api = np.atleast_1d(api)

    assert isinstance(sg_gas,(int,float,list,np.ndarray))
    sg_gas = np.atleast_1d(sg_gas)

    assert isinstance(rsb,(int,float,list,np.ndarray,type(None)))
    rsb = np.atleast_1d(rsb)

    assert isinstance(method,(str,list))

    methods = []
     
    if isinstance(method,str):
        methods.append(method)
        multiple = False
    else:
        methods.extend(method)
        multiple = True

    rs_dict = {}
    p_sat = np.zeros(p.shape)
    p_sat[p>=pb] = pb
    p_sat[p<pb] = p[p<pb]
     
    if 'standing' in methods:

        rs = sg_gas * np.power(((p_sat/18.2)+1.4)*np.power(10,0.0125*api-0.00091*temp),1.2048)
        rs_dict['rs_standing'] = rs

    if 'laster' in methods:
        array_shape = p_sat * sg_gas * temp * p
        mo = np.zeros(api.shape)
        mo[api<=40] = 630-10*api[api<=40]
        mo[api>40] = 73110*np.power(api[api>40],-1.562)

        pb_factor = (p_sat*sg_gas)/(temp + 459.67)

        #estimate yg
        
        yg = np.zeros(array_shape.shape)

        yg[pb_factor<3.29] = 0.359*np.log(1.473*pb_factor[pb_factor<3.29]+0.476)
        yg[pb_factor>=3.29] = np.power(0.121*pb_factor[pb_factor>=3.29] - 0.236,0.281)

        sg_oil = api_to_sg(api)
        rs = (132755*sg_oil*yg)/(mo*(1-yg))
        rs_dict['rs_laster'] = rs

    if 'vazquez_beggs' in methods:
        #Constants c1, c2, c3
        c1 = np.zeros(api.shape)
        c2 = np.zeros(api.shape)
        c3 = np.zeros(api.shape)

        c1[api<=30] = 0.0362
        c1[api>30] = 0.0178

        c2[api<=30] = 1.0937
        c2[api>30] = 1.1870

        c3[api<=30] = 25.724
        c3[api>30] = 23.931
        
        rs = c1*sg_gas*np.power(p_sat,c2)*np.exp((c3*api)/(temp+460))
        rs_dict['rs_vazquez_begss'] = rs

    if 'glaso' in methods:

        f = np.power(10,2.8869-np.power(14.1811-3.3093*np.log10(p_sat),0.5))
        rs = sg_gas*np.power(f*(np.power(api,0.989)/np.power(temp,0.172)),1.2255)
        rs_dict['rs_glaso'] = rs

    if 'valarde' in methods:
        """Method for build rs at pressures below pb by giving the rsb
        Correlation of Black Oil Properties at
        Pressures Below Bubble Point Pressure
        -A New Approach"""
        "https://wiki.pengtools.com/index.php?title=Velarde_correlation"
        A0 = 9.73e-7
        A1 = 1.672608
        A2 = 0.929870
        A3 = 0.247235
        A4 = 1.056052
        alpha_1 = A0 * np.power(sg_gas,A1)*np.power(api,A2)*np.power(temp,A3)*np.power(pb,A4)

        B0 = 0.022339
        B1 = -1.00475
        B2 = 0.337711
        B3 = 0.132795
        B4 = 0.302065
        alpha_2 = B0 * np.power(sg_gas,B1)*np.power(api,B2)*np.power(temp,B3)*np.power(pb,B4)

        C0 = 0.725167
        C1 = -1.48548
        C2 = -0.164741
        C3 = -0.09133
        C4 = 0.047094
        alpha_3 = C0 * np.power(sg_gas,C1)*np.power(api,C2)*np.power(temp,C3)*np.power(pb,C4)


        pr = p_sat/pb
        rsr = alpha_1*np.power(pr,alpha_2) + (1-alpha_1)*np.power(pr,alpha_3)
        rs = rsr*rsb
        rs_dict['rs_valarde'] = rs

    
    rs_df = pd.DataFrame(rs_dict,index=p) if multiple==True else pd.DataFrame({'rs':rs},index=p)
    rs_df.index.name='pressure'
    return rs_df

#####################################################################################
#Oil Volumetric Factor

def bo(p=None,rs=None,pb=None,temp=None,api=None,sg_gas=None,method='standing',**kwargs):
    """
    Estimate the Oil Volumetric Factor using Correlations

    Input: 
        p -> (int,float,np.array) Interest Pressure [psi]
        rs -> (int,float,np.array) Gas Oil Ratio scf/bbl
        pb -> (int,float,np.array) Bubble Point [psi]
        temp ->  (int,float,np.array) Temperature [F]
        api -> (int,float,np.array Oil API gravity [API]
        sg_gas -> Gas specifi gravity
        method -> (list, default 'standing')List of correlation methods
                  ['standing','vazquez_beggs','glaso']
        multiple->(bool, default False) Allow to return multiple result from multiple correlation
                  If true the 'method' must be a length equal to 1
    
    Return:
        bo -> (pd.DataFrame) Oil Volumetric Factor indexed by pressure

    Source: Correlaciones Numericas PVT - Carlos Banzer
    """
    assert isinstance(p,(int,float,list,np.ndarray))
    p = np.atleast_1d(p)

    assert isinstance(rs,(int,float,list,np.ndarray))
    rs = np.atleast_1d(rs)

    assert isinstance(pb,(int,float,list,np.ndarray))
    pb = np.atleast_1d(pb)

    assert isinstance(temp,(int,float,list,np.ndarray))    
    temp = np.atleast_1d(temp)

    assert isinstance(api,(int,float,list,np.ndarray))      
    api = np.atleast_1d(api)

    assert isinstance(sg_gas,(int,float,list,np.ndarray))
    sg_gas = np.atleast_1d(sg_gas)

    assert p.shape == rs.shape

    assert isinstance(method,(str,list))

    methods = []
     
    if isinstance(method,str):
        methods.append(method)
        multiple = False
    else:
        methods.extend(method)
        multiple = True

    bo_dict = {}

    if 'standing' in methods:
        sg_oil = api_to_sg(api)
        f = rs*np.sqrt(sg_gas/sg_oil)+1.25*temp
        bo = 0.9759+12e-5*np.power(f,1.2)
        bo_dict['bo_standing'] = bo

    if 'vazquez_beggs' in methods:
        #Constants c1, c2, c3
        c1 = np.zeros(api.shape)
        c2 = np.zeros(api.shape)
        c3 = np.zeros(api.shape)

        c1[api<=30] = 4.677e-4
        c1[api>30] = 4.670e-4

        c2[api<=30] = 1.751e-5
        c2[api>30] = 1.1e-5

        c3[api<=30] = -1.8106e-8
        c3[api>30] = 1.3370e-9

        bo = 1+ c1*rs + c2*(temp-60)*(api/sg_gas) + c3*rs*(temp-60)*(api/sg_gas)
        bo_dict['bo_vazquez_beggs'] = bo

    if 'glaso' in methods:
        sg_oil = api_to_sg(api)
        f = rs*np.power(sg_gas/sg_oil,0.526) + 0.968*temp
        bo = 1 + np.power(10,-6.58511 + 2.91329* np.log10(f) - 0.27683*np.power(np.log10(f),2))
        bo_dict['bo_glaso'] = bo

    bo_df = pd.DataFrame(bo_dict,index=p) if multiple==True else pd.DataFrame({'bo':bo},index=p)
    bo_df.index.name='pressure'
    return bo_df

#####################################################################################
#Oil Compressibility

def co(p=None,rs=None,pb=None, temp = None, sg_gas = None, api = None,bo=None,bg=None, 
        method_above_pb='vazquez_beggs',method_below_pb='mccain', **kwargs):
    """
    Estimate the Oil compresibility in 1/psi

    Input: 
        p -> (int,float,list,np.array) Interest Pressure [psi]
        rs -> (int,float,np.array) Gas Oil Ratio scf/bbl
        pb -> (int,float,np.array) Bubble Point [psi]
        temp ->  (int,float,np.array) Temperature [F]
        sg_gas -> (int,float,np.array) Gas specifi gravity
        api -> (int,float,np.array) Oil API gravity [API]
        bo -> (list,np.array) Oil Volumetric factor
        bg -> (list,np.array) Oil Volumetric factor
        method_above_pb -> (list, default 'vazquez_beggs') method to use above the bubble point
                            ['vazquez_beggs','petrosky','kartoatmodjo']
        method_below_pb -> (list, default 'mccain') method to use below the bubble point
                            ['mccain']
        multiple-> Only allows one method for each above and below pb 
    Return:
        rho -> (pd.DataFrame) Oil Density indexed by pressure

    Source: Correlaciones Numericas PVT - Carlos Banzer
    """
    assert isinstance(p,(int,float,list,np.ndarray))
    p = np.atleast_1d(p)

    assert isinstance(rs,(int,float,list,np.ndarray))
    rs = np.atleast_1d(rs)

    assert isinstance(pb,(int,float,list,np.ndarray))
    pb = np.atleast_1d(pb)

    assert isinstance(temp,(int,float,list,np.ndarray))   
    temp = np.atleast_1d(temp)

    assert isinstance(sg_gas,(int,float,list,np.ndarray))
    sg_gas = np.atleast_1d(sg_gas)

    assert isinstance(api,(int,float,list,np.ndarray))
    api = np.atleast_1d(api)

    assert isinstance(pb,(int,float,list,np.ndarray))
    bo = np.atleast_1d(bo)

    assert isinstance(pb,(int,float,list,np.ndarray))
    bg = np.atleast_1d(bg)
    
    assert p.shape == bo.shape == rs.shape == bo.shape == bg.shape 

    rs_int = interp1d(p,rs)
    rsb = rs_int(pb)

    co = np.zeros(p.shape)

    if 'vazquez_beggs' == method_above_pb:
        co[p>=pb] = (-1433+5*rs[p>=pb]+17.2*temp-1180*sg_gas +12.61*api)/(p[p>=pb]*np.power(10,5))
 
    elif 'petrosky' == method_above_pb:
        co[p>=pb] = 1.705e-7 * np.power(rs[p>=pb],0.69357) * np.power(sg_gas,0.1885) * np.power(api,0.3272) * np.power(temp,0.6729) * np.power(p[p>=pb],-0.5906)

    elif 'kartoatmodjo' == method_above_pb:
        co[p>=pb] = (6.8257*np.power(rs[p>=pb],0.5002)*np.power(api,0.3613)*np.power(temp,0.76606)*
                    np.power(sg_gas,0.35505))/(p[p>=pb]*np.power(10,6))
    else:
        raise ValueError('no method set')

    if 'mccain' == method_below_pb:
        co[p<pb] = 5.1414768e-4*np.power(p[p<pb],-1.450)*np.power(pb,-0.383)*np.power(temp,1.402)*np.power(api,0.256)*np.power(rsb,0.449)

    else:
        raise ValueError('no method set')
   
    co_df = pd.DataFrame({'co':co},index=p)
    co_df.index.name='pressure'
    return co_df

#####################################################################################
#Dead Oil Viscosity
def muod(temp=None,api=None, method='beal', **kwargs):
    """
    Estimate the Dead Oil Viscosity

    Input: 
        temp -> (int,float,list,np.array) Reservoir Temperature F
        api -> (int,float,list,np.array) API crude API
        methods-> (list,default 'beal') List of methods
                ['beal','beggs','glaso']
        multiple->(bool, default False) Allow to return multiple result from multiple correlation
                  If true the 'method' must be a length equal to 1

    Return:
        muod ->(pd.Dataframe) Dead Oil Viscosity [cP] indexed by temperatures

    Source: Correlaciones Numericas PVT - Carlos Banzer
    """
    assert isinstance(temp,(int,float,list,np.ndarray))
    temp = np.atleast_1d(temp)

    assert isinstance(api,(int,float,list,np.ndarray))
    api = np.atleast_1d(api)

    assert isinstance(method,(str,list))

    methods = []
     
    if isinstance(method,str):
        methods.append(method)
        multiple = False
    else:
        methods.extend(method)
        multiple = True

    muod_dict={}

    if 'beal' in methods:
        a = np.power(10,0.43+(8.33/api))
        muod = (0.32+(1.8e7/np.power(api,4.53)))*np.power(360/(temp+200),a)
        muod_dict['muod_beal'] = muod

    if 'beggs' in methods:
        z=3.0324-0.02023*api
        y=np.power(10,z)
        x=y*np.power(temp,-1.163)

        muod = np.power(10,x)-1
        muod_dict['muod_beggs'] = muod

    if 'glaso' in methods:
        muod = 3.141e10 * np.power(temp,-3.444) * np.power(np.log10(api),10.313*np.log10(temp)-36.447)
        muod_dict['muod_glaso'] = muod

    muod_df = pd.DataFrame(muod_dict,index=temp) if multiple==True else pd.DataFrame({'muod':muod},index=temp)
    muod_df.index.name='temp'
    return muod_df


#####################################################################################
#Live Oil Viscosity
def muo(p=None,rs=None, pb=pb,temp=None,api=None,
        method_below_pb='beggs',method_above_pb='vazquez_beggs',method_dead='beal', **kwargs):
    """
    Estimate the live Oil Viscosity

    Input: 
        p -> (int,float,list,np.array) interest Pressure [psi]
        rs -> (int,float,list,np.array)Gas Oil Ratio scf/bbl
        pb -> (int,float,list,np.array) Bubble Point psi
        method_below_pb -> (list, default 'beggs') method to use above the bubble point
                            ['chew','beggs','kartoatmodjo']
        method_above_pb -> (list, default 'vazquez_beggs') method to use below the bubble point
                            ['beal','vazquez_beggs','kartoatmodjo']
        method_dead -> (list, default 'beal') method estimate dead oil
                            ['beal','beggs','glaso']


    Return:
        mu -> (pd.DataFrame) Oil Viscosity [cP] indexed by pressure

    Source: Correlaciones Numericas PVT - Carlos Banzer
    """
    assert isinstance(p,(int,float,list,np.ndarray))
    p = np.atleast_1d(p)

    assert isinstance(temp,(int,float,list,np.ndarray))
    temp = np.atleast_1d(temp)

    assert isinstance(rs,(int,float,list,np.ndarray))
    rs = np.atleast_1d(rs)

    assert isinstance(pb,(int,float,list,np.ndarray))
    pb = np.atleast_1d(pb)

    assert isinstance(api,(int,float,list,np.ndarray))
    api = np.atleast_1d(api)
  
    assert p.shape == rs.shape, f'Not equal shape: {p.shape} != {rs.shape}'

    #Estimate the Dead oil Viscosity
    _muod = muod(temp=temp,api=api, methods=method_dead)
    _muod = _muod['muod'].values
    print(_muod)

    muo = np.zeros(p.shape)
    muob=np.zeros(1)

    rs_int = interp1d(p,rs)
    rsb = rs_int(pb)
    print(rsb)

    if 'chew' == method_below_pb:
        a = np.power(10,rs[p<=pb]*(2.2e-7*rs[p<=pb]-7.4e-4))
        b = (0.68/np.power(10,8.62e-5*rs[p<=pb]))+(0.25/np.power(10,1.1e-3*rs[p<=pb]))+(0.062/np.power(10,3.74e-3*rs[p<=pb])) 
        muo[p<=pb] = a*np.power(_muod,b)

        a_b=np.power(10,rsb*(2.2e-7*rsb-7.4e-4))
        b_b=(0.68/np.power(10,8.62e-5*rsb))+(0.25/np.power(10,1.1e-3*rsb))+(0.062/np.power(10,3.74e-3*rsb)) 
        muob = a_b*np.power(_muod,b_b)

    if 'beggs' == method_below_pb:
        a = 10.715*np.power(rs[p<=pb]+100,-0.515)
        b = 5.44*np.power(rs[p<=pb]+150,-0.338)
        muo[p<=pb] = a*np.power(_muod,b)

        a_b = 10.715*np.power(rsb+100,-0.515)
        b_b = 5.44*np.power(rsb+150,-0.338) 
        muob = a_b*np.power(_muod,b_b)
    
    if 'kartoatmodjo' == method_below_pb:
        b=np.power(10,-0.00081*rs[p<=pb])
        a=(0.2001 + 0.8428*np.power(10,-0.000845*rs[p<=pb]))*np.power(_muod,0.43+0.5165*b)
        muo[p<=pb]=-0.06821 + 0.9824*a + 40.34e-5*np.power(a,2)

        b_b = np.power(10,-0.00081*rsb)
        a_b = (0.2001 + 0.8428*np.power(10,-0.000845*rsb))*np.power(_muod,0.43+0.5165*b_b) 
        muob = -0.06821 + 0.9824*a_b + 40.34e-5*np.power(a_b,2)

    if 'beal' == method_above_pb:
        muo[p>pb]=(0.001*(p[p>pb]-pb))*(0.024*np.power(muob,1.6)+0.038*np.power(muob,0.56))+muob

    if 'vazquez_beggs' == method_above_pb:
        m = 2.6*np.power(p[p>pb],1.187)*np.exp(-11.513 - 8.98e-5*p[p>pb])
        muo[p>pb] = muob*np.power(p[p>pb]/pb,m)

    if 'kartoatmodjo' == method_above_pb:
        muo[p>pb] = 1.00081*muob + 1.127e-3*(p[p>pb]-pb)*(-65.17e-4*np.power(muob,1.8148)+0.038*np.power(muob,1.59))

    muo_df = pd.DataFrame({'muo':muo}, index=p)
    muo_df.index.name='pressure'
    return muo_df


#####################################################################################
#Oil density

def rho_oil(p=None,co=None,bo=None,rs=None,api=None,pb=None,method='banzer',**kwargs):
    """
    Estimate the Oil Density in lb/ft3

    Input: 
        p ->  (int,float,list,np.array) Interest Pressure [psi]
        co -> (int,float,list,np.array) Isotermic oil compressibility 1/psi
        bo -> (int,float,list,np.array) Oil Volumetric Factor
        rs -> (int,float,list,np.array) Gas Oil Ratio scf/bbl
        api -> (int,float,list,np.array) Oil API gravity [API]
        pb -> (int,float,list,np.array)Bubble Point [psi]
        method -> (list, default 'banzer') Correlation
          
    Return:
        rho -> (pd.DataFrame) Oil Density indexed by pressure

    Source: Correlaciones Numericas PVT - Carlos Banzer
    """
    assert isinstance(p,(int,float,list,np.ndarray))
    p = np.atleast_1d(p)

    assert isinstance(co,(int,float,list,np.ndarray))    
    co = np.atleast_1d(co)

    assert isinstance(bo,(int,float,list,np.ndarray))
    bo = np.atleast_1d(bo)

    assert isinstance(rs,(int,float,list,np.ndarray))
    rs = np.atleast_1d(rs)

    assert isinstance(api,(int,float,list,np.ndarray))      
    api = np.atleast_1d(api)

    assert isinstance(pb,(int,float,list,np.ndarray))
    pb = np.atleast_1d(pb)

    assert p.shape == bo.shape == rs.shape == co.shape

    assert isinstance(method,(str,list))

    methods = []
     
    if isinstance(method,str):
        methods.append(method)
        multiple = False
    else:
        methods.extend(method)
        multiple = True

    rho_oil_dict = {}

    if 'banzer' in methods:
        #Gas disolved specific gravity
        ygd = ((12.5+api)/50)-3.5715e-6*api*rs

        rho_oil = np.zeros(p.shape)
        p_sat = np.zeros(p.shape)
        p_sat[p>=pb] = pb
        p_sat[p<pb] = p[p<pb]

        sg_oil = api_to_sg(api)
        rho_oil[p<=pb] = (350*sg_oil+0.0764*ygd[p<=pb]*rs[p<=pb])/(5.615*bo[p<=pb])
        
        rs_int = interp1d(p,rs)
        bo_int = interp1d(p,bo)

        rho_ob = (350*sg_oil+0.0764*ygd[p>pb]*rs_int(pb))/(5.615*bo_int(pb))
        rho_oil[p>pb] = rho_ob*np.exp(co[p>pb]*(pb-p[p>pb]))
        rho_oil_dict['rho_banzer'] = rho_oil

    rho_df = pd.DataFrame(rho_oil_dict,index=p) if multiple==True else pd.DataFrame({'rhoo':rho_oil},index=p)
    rho_df.index.name='pressure'
    return rho_df


#####################################################################################
#####################################################################################
############################ WATER CORRELATIONS #####################################

def rsw(p=None,t=None,s=None,method='culberson'):
    """
    Estimate Water Gas solubility is 

    Input: 
        p ->  (int,float,list,np.array) Interest Pressure [psi]
        t ->  (int,float,list,np.array) Interest Temperature [F]

        method -> (str,list, default 'banzer') Correlation
          
    Return:
        rsw -> (pd.DataFrame) water solubility indexed by pressure

    Source: Correlaciones Numericas PVT - Carlos Banzer
    """
    assert isinstance(p,(int,float,list,np.ndarray))
    p = np.atleast_1d(p)

    assert isinstance(t,(int,float,list,np.ndarray))
    t = np.atleast_1d(t)

    assert isinstance(method,(str,list))

    methods = []
     
    if isinstance(method,str):
        methods.append(method)
        multiple = False
    else:
        methods.extend(method)
        multiple = True

    rsw_dict = {}

    if 'culberson' in methods:

        a = 8.15839 - 6.12265e-2*t + 1.91663e-4*np.power(t,2) - 2.1654e-7*np.power(t,3)
        b = 1.01021e-2 - 7.44241e-5*t + 3.05553e-7*np.power(t,2) - 2.94883e-10*np.power(t,3)
        c = (-9.02505 + 0.130237*t - 8.53425e-4*np.power(t,2) + 2.34122e-6*np.power(t,3) - 2.37049e-9*np.power(t,4))*1e-7
        rswp = a + b*p + c*np.power(p,2)

       # Convert p in ppm to percentage %
        per_s = s/1e4
        correction = np.power(10,-0.0840655*per_s*np.power(t,-0.285854))
        rsw = rswp * correction
        rsw_dict['rws_culberson'] = rsw

    if 'mccoy' in methods:

        a = 2.12 + 3.45e-3*t - 3.59e-5*np.power(t,2)
        b = 0.0107 - 5.26e-5*t + 1.48e-7*np.power(t,2)
        c = -8.75e-7 + 3.9e-9*t - 1.02e-11*np.power(t,2)
        rswp = a + b*p + c*np.power(p,2)
        # Convert p in ppm to percentage %
        per_s = s/1e4
        correction = (1 - (0.0753 - 1.73e-4*t)*per_s)
        rsw = rswp * correction
        rsw_dict['rsw_mccoy'] = rsw

    rsw_df = pd.DataFrame(rsw_dict,index=p) if multiple==True else pd.DataFrame({'rsw':rsw},index=p)
    rsw_df.index.name='pressure'
    return rsw_df

def bw(p=None, t=None, pb=0,cw=0,s = None, method='mccain'):
    """
    Estimate Water volumetric factor

    Input: 
        p ->  (int,float,list,np.array) Interest Pressure [psi]
        t ->  (int,float,list,np.array) Interest Temperature [F]
        pb ->  (int,float,list,np.array) Bubble point [psi]
        cw ->  (int,float,list,np.array) Water isothermal compressibility [1/psi]
        s ->  (int,float,list,np.array) Salinity [ppm]

        method -> (str,list, default 'banzer') Correlation
          
    Return:
        bw -> (pd.DataFrame) water volumetric factor indexed by pressure

    Source: Correlaciones Numericas PVT - Carlos Banzer
    """
    assert isinstance(p,(int,float,list,np.ndarray))
    p = np.atleast_1d(p)

    assert isinstance(t,(int,float,list,np.ndarray))
    t = np.atleast_1d(t)

    assert isinstance(pb,(int,float,list,np.ndarray))
    pb = np.atleast_1d(pb)

    assert isinstance(cw,(int,float,list,np.ndarray))
    cw = np.atleast_1d(cw)

    assert isinstance(s,(int,float,list,np.ndarray))
    s = np.atleast_1d(s)

    assert isinstance(method,(str,list))

    methods = []
     
    if isinstance(method,str):
        methods.append(method)
        multiple = False
    else:
        methods.extend(method)
        multiple = True
    bw_dict = {}

    if 'mccain' in methods:
        bwp = np.zeros(p.shape)
        delta_vw_t = np.zeros(p.shape)
        delta_vw_p = np.zeros(p.shape)
        correction = np.zeros(p.shape)

        delta_vw_t[p<pb] = -1.0001e-2 + 1.33391e-4*t + 5.50654e-7*np.power(t,2)
        delta_vw_t_pb = -1.0001e-2 + 1.33391e-4*t + 5.50654e-7*np.power(t,2)
        delta_vw_p[p<pb] = -1.95301e-9*p[p<=pb]*t - 1.72834e-13*np.power(p[p<=pb],2)*t - 3.58922e-7*p - 2.25341e-10*np.power(p[p<=pb],2)
        delta_vw_p_pb = -1.95301e-9*pb*t - 1.72834e-13*np.power(pb,2)*t - 3.58922e-7*p - 2.25341e-10*np.power(pb,2)
        
        bwp[p<=pb] = (1 + delta_vw_p)*(1+delta_vw_t)
        bwb = (1 + delta_vw_p_pb)*(1+delta_vw_t_pb)

        bwp[p>pb] = bwb * np.exp(cw*(pb-p))   

        # Convert p in ppm to percentage %
        per_s = s/1e4
        correction = 1 + per_s * (5.1e-8*p + (5.47e-6 - 1.95e-10*p)*(t-60)-(3.23e-8 - 8.5e-13*p)*(np.power(t-60,2)))
        bw = bwp * correction
        bw_dict['bw_mccain'] = bw

        print(delta_vw_t)
        print(delta_vw_p)
        print(correction)
        print(bwp)

    if 'mccoy' in methods:
        bwp = np.zeros(p.shape)
        correction = np.zeros(p.shape)

        a = 0.9911 + 6.35e-5*t + 8.5e-7*np.power(t,2)
        b = -1.093e-6 - 3.497e-9*t + 4.57e-12*np.power(t,2)
        c = -5e-11 + 6.429e-13*t - 1.43e-15*np.power(t,2)

        bwp[p<=pb] = a + b*p[p<=pb] + c*np.power(p[p<=pb],2)
        bwb = a + b*pb + c*np.power(pb,2)

        bwp[p>pb] = bwb = np.exp(cw*(pb-p))

        # Convert p in ppm to percentage %
        per_s = s/1e4
        correction = 1 + per_s * (5.1e-8*p + (5.47e-6 - 1.95e-10*p)*(t-60)-(3.23e-8 - 8.5e-13*p)*(np.power(t-60,2)))
        bw = bwp * correction
        bw_dict['bw_mccoy'] = bw
        print('mcoy')
        print(a)
        print(b)
        print(c)
        print(bwp)
        print(correction)
        print(bwp)

    bw_df = pd.DataFrame(bw_dict,index=p) if multiple==True else pd.DataFrame({'bw':bw},index=p)
    bw_df.index.name='pressure'
    return bw_df



    

    








