import os
import sys
module_path = os.path.abspath(os.path.join('../'))
if module_path not in sys.path:
    sys.path.append(module_path)

module_path = os.path.abspath(os.path.join('./'))
if module_path not in sys.path:
    sys.path.append(module_path)

from ario3.simulation import Simulation
from ario3.indicators import Indicators
from ario3.logging_conf import DEBUGFORMATTER
import json
import pandas as pd
import numpy as np
import pathlib
import csv
import logging
import coloredlogs
import pickle
from datetime import datetime

# REGIONS presents both in JRC data and EXIOBASE3
# We have to work on RoW
#REGIONS = ['SI', 'PL', 'LV', 'BG', 'CZ', 'SE', 'KR', 'NO', 'HR', 'ES', 'JP', 'IN', 'BR', 'DE', 'CH', 'IE', 'EE', 'GB', 'ID', 'RU', 'GR', 'ZA', 'RO', 'MX', 'FI', 'AT', 'NL', 'US', 'IT', 'LT', 'FR', 'BE', 'HU', 'CA', 'AU', 'CN', 'TR', 'PT', 'SK']

REGIONS = ['AT']

LOGPATH = "/diskdata/cired/sjuhel/Data/Runs/Flood-Dottori/outputs/logs"
LOGNAME = "run"

if __name__ == "__main__":
    print("=============== STARTING EXPLOIT OF RUN1 RESULTS ================")
    logFormatter = DEBUGFORMATTER
    rootLogger = logging.getLogger(__name__)
    #model_logger = logging.getLogger("ario3")

    consoleHandler = logging.StreamHandler(sys.stderr)

    fileHandler = logging.FileHandler("{0}/{1}.log".format(LOGPATH, LOGNAME))
    fileHandler.setFormatter(logFormatter)
    rootLogger.addHandler(fileHandler)

    fieldstyle = {'asctime': {'color': 'green'},
              'levelname': {'bold': True, 'color': 'black'},
              'filename':{'color':'cyan'},
              'funcName':{'color':'blue'}}

    levelstyles = {'critical': {'bold': True, 'color': 'red'},
               'debug': {'color': 'green'},
               'error': {'color': 'red'},
               'info': {'color':'magenta'},
               'warning': {'color': 'yellow'}}

    coloredlogs.install(level=logging.DEBUG,
                    logger=rootLogger,
                    fmt='%(asctime)s [%(levelname)s] - [%(filename)s > %(funcName)s() > %(lineno)s] - %(message)s',
                    datefmt='%H:%M:%S',
                    field_styles=fieldstyle,
                    level_styles=levelstyles)

    rootLogger.info("Computing gdp dataframe")
    with open("/diskdata/cired/sjuhel/Data/Runs/Flood-Dottori/inputs/params.json") as f:
        params_template = json.load(f)


    with open("/diskdata/cired/sjuhel/Data/Runs/Flood-Dottori/inputs/flood_country_gdp_share.json") as f:
        flood_gdp_share = json.load(f)


    with open("/diskdata/cired/sjuhel/Data/Runs/Flood-Dottori/inputs/event_template.json") as f:
        event_template = json.load(f)

    res = [{
            "tot_fd_unmet": "unset",
            "aff_fd_unmet": "unset",
            "rebuild_durations": "unset",
            "shortage_b": False,
            "shortage_date_start": "unset",
            "shortage_date_end": "unset",
            "shortage_date_max": "unset",
            "shortage_ind_max": "unset",
            "shortage_ind_mean": "unset",
            "10_first_shortages": "unset",
            "prod_gain_tot": "unset",
            "prod_lost_tot": "unset",
            "prod_gain_unaff": "unset",
            "prod_lost_unaff": "unset",
            "region":"unset",
            "q_dmg":"unset",
            "pib": "unset",
            "psi": "unset",
            "inv_tau": "unset"
            }]


    for region in REGIONS:
        mrio_path = list(pathlib.Path(params_template['input_dir']).glob('mrio_'+region+'*.pkl'))
        rootLogger.info("Trying to load {}".format(mrio_path))
        assert len(mrio_path)==1
        mrio_path = list(mrio_path)[0]
        with mrio_path.open('rb') as f:
            mrio = pickle.load(f)

        value_added = (mrio.x.T - mrio.Z.sum(axis=0))
        value_added = value_added.reindex(sorted(value_added.index), axis=0) #type: ignore
        value_added = value_added.reindex(sorted(value_added.columns), axis=1)
        value_added[value_added < 0] = 0.0
        gdp_df = value_added.groupby('region',axis=1).sum().T['indout']
        gdp_df_pct = gdp_df*1000000
        rootLogger.info('Done !')
        rootLogger.info("Main storage dir is : {}".format(pathlib.Path(params_template['output_dir']).resolve()))
        dmgs = { '1%': flood_gdp_share[region]['1%'],
                     '5%': flood_gdp_share[region]['5%'],
                     '10%': flood_gdp_share[region]['10%'],
                     '33%': flood_gdp_share[region]['33%'],
                     '50%': flood_gdp_share[region]['50%'],
                     '66%': flood_gdp_share[region]['66%'],
                     '75%': flood_gdp_share[region]['75%'],
                     '80%': flood_gdp_share[region]['80%'],
                     '90%': flood_gdp_share[region]['90%'],
                     '99%': flood_gdp_share[region]['99%'],
                     'max': flood_gdp_share[region]['max']
                    }
        for qdmg, v in dmgs.items():
            dmg = gdp_df_pct[region] * v
            event = event_template.copy()
            sim_params = params_template.copy()
            event['aff-regions'] = region
            event['q_dmg'] = dmg
            psi = sim_params['psi_param']
            inv_tau = sim_params['inventory_restoration_time']
            sim_params["results_storage"] = params_template["results_storage"]+"/"+region+'_RoW_'+'qdmg_'+qdmg+'_Psi_'+str(sim_params['psi_param']).replace(".","_")+"_inv_tau_"+str(sim_params['inventory_restoration_time'])
            model = Simulation(sim_params, mrio_path)
            model.read_events_from_list([event])
            try:
                model.loop(progress=False)
            except Exception:
                rootLogger.exception("There was a problem:")
