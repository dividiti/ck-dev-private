#!/usr/bin/python

# Author : Marco Cianfriglia



################################################################################
################################################################################

# IMPORTS
################################################################################

import ck.kernel as ck
import re
import argparse
import os
from shutil import copyfile
import json
from sklearn import tree
import copy
import random
import sys
import glob
import math

# Ratio between test and training sets
DEFAULT_RATIO=80
pipeline_output='con' 
program = 'clblast-tune-ml'
program_check = 'clblast-check-ml'
cmd_key = 'xgemm-fp32'
platform = 'nvidia-dgx'
run=3
num_leaf = 0
output_dir =''
json_out_dir = ''
device_id=0

# Generate Input Dataset
def generateInputDataset(num_samples=6):
    X=[]
    for i in range(num_samples):
        for j in range(num_samples):
            for y in range(num_samples):
                curr={'m': 2**(i+6), 'n': 2**(j+6) ,'k' : 2**(y+6)}
                X.append(curr)

    return X





def runPipelineCheck(data_uoa, cmd_key, env, cdeps, rdeps, M, N, K):
     # Detect basic platform info.
    ii={'action':'detect',
        'module_uoa':'platform',
        'out':'out'}
    r=ck.access(ii)
    if r['return']>0: return r

    # Host and target OS params.
    hos=r['host_os_uoa']
    hosd=r['host_os_dict']

    tos=r['os_uoa']
    tosd=r['os_dict']
    tdid=tdid=r['device_id']

    # Load  program meta and desc to check deps.
    ii={'action':'load',
        'module_uoa':'program',
        'data_uoa': data_uoa}
    rx=ck.access(ii)
    if rx['return']>0: return rx
    mm=rx['dict']

     # Get compile-time and run-time deps.
    cdeps=mm.get('compile_deps',{})
    rdeps=mm.get('run_deps',{})

    # # Merge rdeps with cdeps for setting up the pipeline (which uses
    # # common deps), but tag them as "for_run_time".
    for j in rdeps:
        cdeps[j]=rdeps[j]
        cdeps[j]['for_run_time']='yes'
    
    global pipeline_output
    ii={'action' : 'pipeline',
                
        'target_os':tos,
        'device_id':tdid,

        'module_uoa' : 'program',
        'data_uoa' : data_uoa,
        'cmd_key' : cmd_key,
        'prepare' : 'yes',
        'dependencies' : cdeps,
        'no_compiler_description' : 'yes',
        'out' : 'con',
        'no_state_check' : 'yes',
        'flags' : '-O3',
        'cpu_freq':'max',
        'gpu_freq':'max'
        }
    r=ck.access(ii)
    
    if r['return']>0: return r
    fail=r.get('fail','')
    if fail=='yes': return {'return':10, 'error':'pipeline failed ('+r.get('fail_reason','')+')'}

    ready=r.get('ready','')
    if ready!='yes': return {'return':11, 'error':'pipeline not ready'}


    state=r['state']
    tmp_dir=state['tmp_dir']
    xcdeps=r.get('dependencies',{})
    # Clean pipeline.
    if 'ready' in r: del(r['ready'])
    if 'fail' in r: del(r['fail'])
    if 'return' in r: del(r['return'])
    pipeline=copy.deepcopy(r)


    record_repo='local'
    record_uoa='check_training_dataset-' + cmd_key + '-' + platform
    ck.out('---------------------------------------------------------------------------------------')
    ck.out('Experiment - %s:%s' % (record_repo, record_uoa))
    
    size_m = []
    size_n = []
    size_k = []
    
    size_m.append(M)
    size_n.append(N)
    size_k.append(K)
    

    cpipeline=copy.deepcopy(pipeline)
    ii={
        'action':'autotune',
        'module_uoa':'pipeline',
        'data_uoa':'program',
        'choices_order':[
            [
             '##env#CK_CLBLAST_MSIZE'
            ],
            [
             '##env#CK_CLBLAST_NSIZE',
            ],
            [
             '##env#CK_CLBLAST_KSIZE'
            ],
            [
             '##env#CK_CLBLAST_NUM_ITERATIONS'
            ],
            [
             '##env#CK_CLBLAST_KWG'
            ],
            [
             '##env#CK_CLBLAST_KWI'
            ],
            [
             '##env#CK_CLBLAST_MDIMA'
            ],
            [
             '##env#CK_CLBLAST_MDIMC'
            ],
            [
             '##env#CK_CLBLAST_MWG'
            ],
            [
             '##env#CK_CLBLAST_NDIMB'
            ],
            [
             '##env#CK_CLBLAST_NDIMC'
            ],
            [
             '##env#CK_CLBLAST_NWG'
            ],
            [
             '##env#CK_CLBLAST_SA'
            ],
            [
             '##env#CK_CLBLAST_SB'
            ],
            [
             '##env#CK_CLBLAST_STRM'
            ],
            [
             '##env#CK_CLBLAST_STRN'
            ],
            [
             '##env#CK_CLBLAST_VWM'
            ],
            [
             '##env#CK_CLBLAST_VWN'
            ]

        ],
        'choices_selection':[
            {"type":"loop-with-next", "choice":size_m, "default":"256"},
            {"type":"loop-with-next", "choice":size_n, "default":"256"},
            {"type":"loop-with-next", "choice":size_k, "default":"256"},
            {"type" : "loop", "choice":[env['run']] , 'default':[env['run']]},
            {"type" : "loop", "choice":[env['kwg']] , 'default':[env['kwg']]},
            {"type" : "loop", "choice":[env['kwi']] , 'default':[env['kwi']]},
            {"type" : "loop", "choice":[env['mdima']] , 'default':[env['mdima']]},
            {"type" : "loop", "choice":[env['mdimc']] , 'default':[env['mdimc']]},
            {"type" : "loop", "choice":[env['mwg']] , 'default':[env['mwg']]},
            {"type" : "loop", "choice":[env['ndimb']] , 'default':[env['ndimb']]},
            {"type" : "loop", "choice":[env['ndimc']] , 'default':[env['ndimc']]},
            {"type" : "loop", "choice":[env['nwg']] , 'default':[env['nwg']]},
            {"type" : "loop", "choice":[env['sa']] , 'default':[env['sa']]},
            {"type" : "loop", "choice":[env['sb']] , 'default':[env['sb']]},
            {"type" : "loop", "choice":[env['strm']] , 'default':[env['strm']]},
            {"type" : "loop", "choice":[env['strn']] , 'default':[env['strn']]},
            {"type" : "loop", "choice":[env['vwm']] , 'default':[env['vwm']]},
            {"type" : "loop", "choice":[env['vwn']] , 'default':[env['vwn']]}
        ],
        'features_keys_to_process':['##choices#*'],


        'iterations':-1,
        'repetitions':1,
        'record':'no',
        'pipeline': cpipeline,
        'out':pipeline_output

    }
    r=ck.access(ii)
    
    if r['return']>0: 
        return r
    fail=r.get('fail','')
    if fail=='yes':
       return {'return':10, 'error':'pipeline failed ('+r.get('fail_reason','')+')'}




def checkUndirectTotaltime(input_file,gflops_compare):
    f=open(input_file)
    json_data = json.load(f)

    #LOAD PARAMETERS
    kwg = json_data['statistics']['best_configuration']['parameters']['KWG']
    kwi = json_data['statistics']['best_configuration']['parameters']['KWI']
    mdima = json_data['statistics']['best_configuration']['parameters']['MDIMA']
    mdimc = json_data['statistics']['best_configuration']['parameters']['MDIMC']
    ndimb = json_data['statistics']['best_configuration']['parameters']['NDIMB']
    ndimc = json_data['statistics']['best_configuration']['parameters']['NDIMC']
    mwg = json_data['statistics']['best_configuration']['parameters']['MWG']
    nwg = json_data['statistics']['best_configuration']['parameters']['NWG']
    vwm = json_data['statistics']['best_configuration']['parameters']['VWM']
    vwn = json_data['statistics']['best_configuration']['parameters']['VWN']
    sa = json_data['statistics']['best_configuration']['parameters']['SA']
    sb = json_data['statistics']['best_configuration']['parameters']['SB']
    strm = json_data['statistics']['best_configuration']['parameters']['STRM']
    strn = json_data['statistics']['best_configuration']['parameters']['STRN']

    #LOAD SIZES
    m = json_data['arg_m']
    n = json_data['arg_n']
    k = json_data['arg_k']

    # Detect basic platform info.
    ii={'action':'detect',
        'module_uoa':'platform',
        'out':'out'}
    r=ck.access(ii)
    if r['return']>0: return r

    # Host and target OS params.
    hos=r['host_os_uoa']
    hosd=r['host_os_dict']

    tos=r['os_uoa']
    tosd=r['os_dict']
    tdid=tdid=r['device_id']

    # Load  program meta and desc to check deps.
    ii={'action':'load',
        'module_uoa':'program',
        'data_uoa':program_check}
    rx=ck.access(ii)
    if rx['return']>0: return rx
    mm=rx['dict']

     # Get compile-time and run-time deps.
    cdeps=mm.get('compile_deps',{})
    rdeps=mm.get('run_deps',{})

    # # Merge rdeps with cdeps for setting up the pipeline (which uses
    # # common deps), but tag them as "for_run_time".
    for j in rdeps:
        cdeps[j]=rdeps[j]
        cdeps[j]['for_run_time']='yes'
  
    
    
    ii={'action': 'search',
        'module_uoa': 'program',
        'data_uoa': program_check
    }
    r = ck.access(ii)
    if r['return'] > 0:
        print("[ERROR] : unable to find program entry ", program_check)
        return r
    env ={ 
            'run' : run,
            'kwg' : kwg,
            'kwi' : kwi,
            'mdima' : mdima,
            'mdimc' : mdimc,
            'mwg' : mwg,
            'ndimb' : ndimb,
            'ndimc' : ndimc,
            'nwg' : nwg,
            'sa' : sa,
            'sb' : sb,
            'strm' : strm,
            'strn' : strn,
            'vwm' : vwm,
            'vwn' : vwn
        }
    cmd_key='clblast_test_dvdt_runtime_check'
    runPipelineCheck(program_check, cmd_key, env, cdeps, rdeps,m,n,k)

    #Check the overall GFLOPS
    exp_dir=r['lst'][0]['path']
    exp_dir = exp_dir + '/tmp'

    check_file='clblast_xgemm_override.json'
    f_c = open(exp_dir + os.sep + check_file)
    json_data_check = json.load(f_c)

    gflops_all = json_data_check['GFLOPS']
    if  gflops_all > gflops_compare : 
        json_data['GFLOPS_tune'] = json_data['statistics']['best_configuration']['GFLOPS']
        json_data['statistics']['best_configuration']['GFLOPS'] = gflops_all
        f.close()
        f=open(input_file,"w")
        json.dump(json_data, f, sort_keys=True, indent = 4)
        f.close()
        return True
    else: 
        return False

def getGFlops(exp_dir, inp):
    if not os.path.isfile(exp_dir + os.sep + inp):
        print ("Not found")
        return 0.0
    f=open(exp_dir + os.sep + inp)
    jdata=json.load(f)
    f.close()
    if 'GFLOPS' in jdata['statistics']['best_configuration']:
        return jdata['statistics']['best_configuration']['GFLOPS']
    else:
        print ("Not found")
        return 0.0

def getClFiles(exp_dir,fin):
    s=fin.split('-')
    kernel=s[4]
    m=s[6]
    n=s[7]
    s= s[8].split('.')
    k=s[0]
    
    expr=exp_dir + os.sep + 'clblast_'+ kernel + '_[1,2]_*_multiconf_' + m + '_' + n + '_' + k + '.json'
    f = glob.glob(expr)
    if len(f) == 0:
        return '/dev/null'
    f = f[0].split(os.sep)
    l = len(f)

    return f[(l-1)]

def copyBests(exp_dir, out_dir):
    for f in os.listdir(exp_dir):
        if 'tmp-ck-clblast-tune-xgemm_direct' in f:
            f_dir=f
            f_und=f.replace('_direct','')
            gflops_dir=getGFlops(exp_dir,f_dir)
            gflops_und=getGFlops(exp_dir,f_und)
            cl_dir = getClFiles(exp_dir,f_dir)
            cl_und = getClFiles(exp_dir,f_und)
            print ("Undirect ", str(gflops_und), " ", f_und )
            print ("Direct " , str(gflops_dir) , " " , f_dir)
            if gflops_dir > gflops_und:
                copyfile(exp_dir + os.sep + f_dir , output_dir + os.sep + f_dir)
                copyfile(exp_dir + os.sep + cl_dir , output_dir + os.sep + cl_dir)
            elif gflops_und > gflops_dir:
                gflops_und_real = checkUndirectTotaltime(exp_dir + os.sep + f_und,gflops_dir)
                if gflops_und_real:
                    copyfile(exp_dir + os.sep + f_und , output_dir + os.sep + f_und)
                    copyfile(exp_dir + os.sep + cl_und , output_dir + os.sep + cl_und)
                else :
                    copyfile(exp_dir + os.sep + f_dir , output_dir + os.sep + f_dir)
                    copyfile(exp_dir + os.sep + cl_dir , output_dir + os.sep + cl_dir)
            else:
                if gflops_dir != 0.0:
                    copyfile(exp_dir + os.sep + f_dir , output_dir + os.sep + f_dir)
                    copyfile(exp_dir + os.sep + f_und , output_dir + os.sep + f_und)
                    copyfile(exp_dir + os.sep + cl_dir , output_dir + os.sep + cl_dir)
                    copyfile(exp_dir + os.sep + cl_und , output_dir + os.sep + cl_und)


def runPipeline(data_uoa, cmd_key, env, cdeps, rdeps, training_set):
	 # Detect basic platform info.
    ii={'action':'detect',
        'module_uoa':'platform',
        'out':'out'}
    r=ck.access(ii)
    if r['return']>0: return r

    # Host and target OS params.
    hos=r['host_os_uoa']
    hosd=r['host_os_dict']

    tos=r['os_uoa']
    tosd=r['os_dict']
    tdid=tdid=r['device_id']

    # Load  program meta and desc to check deps.
    ii={'action':'load',
        'module_uoa':'program',
        'data_uoa': data_uoa}
    rx=ck.access(ii)
    if rx['return']>0: return rx
    mm=rx['dict']

     # Get compile-time and run-time deps.
    cdeps=mm.get('compile_deps',{})
    rdeps=mm.get('run_deps',{})

    # # Merge rdeps with cdeps for setting up the pipeline (which uses
    # # common deps), but tag them as "for_run_time".
    for k in rdeps:
        cdeps[k]=rdeps[k]
        cdeps[k]['for_run_time']='yes'
    
    global pipeline_output
    ii={'action' : 'pipeline',
                
        'target_os':tos,
        'device_id':tdid,

        'module_uoa' : 'program',
        'data_uoa' : data_uoa,
        'cmd_key' : cmd_key,
        'prepare' : 'yes',
        'dependencies' : cdeps,
        'no_compiler_description' : 'yes',
        'out' : 'con',
        'no_state_check' : 'yes',
        'flags' : '-O3',
        'env':{
            'CK_CLBLAST_NUM_ITERATIONS': env['run'],
            'CK_TUNER_NUM_OF_STRATEGIES': env['num_of_strategy'],
            'CK_SEARCH_STRATEGY': env['search_strategy'],
            'CK_PSO_SWARM_SIZE':env['pso_swarm_size'],
            'CK_PSO_INF_G' : env['pso_inf_g'],
            'CK_PSO_INF_L' : env['pso_inf_l'],
            'CK_PSO_INF_R' : env['pso_inf_r']
           	       
           	},
        'cpu_freq':'max',
        'gpu_freq':'max'
        }
    r=ck.access(ii)
    
    if r['return']>0: return r
    fail=r.get('fail','')
    if fail=='yes': return {'return':10, 'error':'pipeline failed ('+r.get('fail_reason','')+')'}

    ready=r.get('ready','')
    if ready!='yes': return {'return':11, 'error':'pipeline not ready'}


    state=r['state']
    tmp_dir=state['tmp_dir']
    xcdeps=r.get('dependencies',{})
    # Clean pipeline.
    if 'ready' in r: del(r['ready'])
    if 'fail' in r: del(r['fail'])
    if 'return' in r: del(r['return'])
    pipeline=copy.deepcopy(r)


    record_repo='local'
    record_uoa='create-training-dataset-' + cmd_key + '-' + platform
    ck.out('---------------------------------------------------------------------------------------')
    ck.out('Experiment - %s:%s' % (record_repo, record_uoa))
    
    size_m = []
    size_n = []
    size_k = []
    
    for j in range(len(training_set)):
        size_m.append(training_set[j]['m'])
        size_n.append(training_set[j]['n'])
        size_k.append(training_set[j]['k'])

    cpipeline=copy.deepcopy(pipeline)
    ii={
        'action':'autotune',
        'module_uoa':'pipeline',
        'data_uoa':'program',
        'env':{
            'CK_CLBLAST_NUM_ITERATIONS': env['run'],
            'CK_TUNER_NUM_OF_STRATEGIES': env['num_of_strategy'],
            'CK_SEARCH_STRATEGY': env['search_strategy'],
            'CK_PSO_SWARM_SIZE':env['pso_swarm_size'],
            'CK_PSO_INF_G' : env['pso_inf_g'],
            'CK_PSO_INF_L' : env['pso_inf_l'],
            'CK_PSO_INF_R' : env['pso_inf_r']
           	       
           	},
        'choices_order':[
            [
             '##env#CK_CLBLAST_MSIZE'
            ],
            [
             '##env#CK_CLBLAST_NSIZE',
            ],
            [
             '##env#CK_CLBLAST_KSIZE'
            ],
            [
             '##env#CK_CLBLAST_NUM_ITERATIONS'
            ],
            [
             '##env#CK_TUNER_NUM_OF_STRATEGIES'
            ],
            [
             '##env#CK_SEARCH_STRATEGY'
            ],
            [
             '##env#CK_PSO_SWARM_SIZE'
            ],
            [
             '##env#CK_PSO_INF_G'
            ],
            [
             '##env#CK_PSO_INF_G'
            ],
            [
             '##env#CK_PSO_INF_R'
            ]

        ],
        'choices_selection':[
            {"type":"loop-with-next", "choice":size_m, "default":"256"},
            {"type":"loop-with-next", "choice":size_n, "default":"256"},
            {"type":"loop-with-next", "choice":size_k, "default":"256"},
            {"type" : "loop", "choice":[env['run']] , 'default':[env['run']]},
            {"type" : "loop", "choice":[env['num_of_strategy']] , 'default':[env['num_of_strategy']]},
            {"type" : "loop", "choice":[env['search_strategy']] , 'default':[env['search_strategy']]},
            {"type" : "loop", "choice":[env['pso_swarm_size']] , 'default':[env['pso_swarm_size']]},
            {"type" : "loop", "choice":[env['pso_inf_g']] , 'default':[env['pso_inf_g']]},
            {"type" : "loop", "choice":[env['pso_inf_l']] , 'default':[env['pso_inf_l']]},
            {"type" : "loop", "choice":[env['pso_inf_r']] , 'default':[env['pso_inf_r']]}
        ],
        'features_keys_to_process':['##choices#*'],


        'iterations':-1,
        'repetitions':1,
        'record':'yes',
        'record_failed':'yes',
        'record_params':{
            'search_point_by_features':'yes'
        },
        'record_repo':record_repo,
        'record_uoa':record_uoa,
        'tags':['create-training-dataset', cmd_key, platform],
        'pipeline': cpipeline,
        'out':pipeline_output

    }
    r=ck.access(ii)
    
    if r['return']>0: 
        return r
    fail=r.get('fail','')
    if fail=='yes':
       return {'return':10, 'error':'pipeline failed ('+r.get('fail_reason','')+')'}



# Tune the library and extract the best configurations 
# for each matrix in the Input Dataset
def tuneLibrary(training,output_dir,kernels_name):

	 # Detect basic platform info.
    ii={'action':'detect',
        'module_uoa':'platform',
        'out':'out'}
    r=ck.access(ii)
    if r['return']>0: return r

    # Host and target OS params.
    hos=r['host_os_uoa']
    hosd=r['host_os_dict']

    tos=r['os_uoa']
    tosd=r['os_dict']
    tdid=tdid=r['device_id']

    # Load  program meta and desc to check deps.
    ii={'action':'load',
        'module_uoa':'program',
        'data_uoa':program}
    rx=ck.access(ii)
    if rx['return']>0: return rx
    mm=rx['dict']

     # Get compile-time and run-time deps.
    cdeps=mm.get('compile_deps',{})
    rdeps=mm.get('run_deps',{})

    # # Merge rdeps with cdeps for setting up the pipeline (which uses
    # # common deps), but tag them as "for_run_time".
    for k in rdeps:
        cdeps[k]=rdeps[k]
        cdeps[k]['for_run_time']='yes'
  
    training_dim = len (training)
    if training_dim <= 0 :
        print ("[ERROR] : Invalid training set")
        return -1
    Z = []
    ii={'action': 'search',
        'module_uoa': 'program',
        'data_uoa': program
    }
    r = ck.access(ii)
    if r['return'] > 0:
    	print ("[ERROR] : unable to find program entry ", program, sep="")
    	return r
    env ={ 
        	'run' : run,
        	'num_of_strategy' : 1,
        	'search_strategy' : 0,
        	'pso_swarm_size' : 8,
        	'pso_inf_g' : 0.3,
        	'pso_inf_l' : 0.6,
        	'pso_inf_r' : 0.1
        }
    for j in range(len(kernels_name)):
        cmd_key = kernels_name[j] + '-fp32'
        runPipeline(program, cmd_key, env, cdeps, rdeps, training)

    exp_dir=r['lst'][0]['path']
    exp_dir = exp_dir + '/tmp'
    print ("EXP_DIR:" + exp_dir)
    copyBests(exp_dir,output_dir)
    return 0



# GET TRAINING DATASET
################################################################################
def loadModelMatrixes(csv_files_dir):
    
    m = set()
    for i in os.listdir(csv_files_dir):
        f=open(csv_files_dir + os.sep + i)
        lines=f.read().split('\r\n')
        for j in range(2,len(lines)):
            m.add(lines[j])
        f.close()
    return m

def loadMatrixesFromCsv(csv_file):
    X = []
    f=open(csv_file)
    lines=f.readlines()
    for j in range(len(lines)):
        size=lines[j].split(',')
        X.append({'m': size[0], 'n' : size[1], 'k' : size[2]})
    f.close()
    return X

def loadModelMatrixesFromJson(json_file):
    f=open(json_file)
    j=json.load(f)
    return j


def getAllMatrixFromSet(dataset):
    X=[]
    for e in dataset:
        e=e.split(',')
        X.append({'m' : e[0], 'n' : e[1], 'k': e[2]})
    
    return X



# Create the Training Set
def createTrainingSet(arg):
    
    DATASET=[]
    build_dataset = False
    global output_dir
    global json_out_dir
    output_dir = '/tmp/exp'
    if arg.output_dir != None:
        output_dir = arg.output_dir

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    else:
        print ("[INFO] : " , output_dir , " exists", sep="")
   
    json_out_dir = output_dir + '/json'
    if not os.path.exists(json_out_dir):
        os.makedirs(json_out_dir)
    else:
        print ("[INFO] : " , json_out_dir , " exists", sep = "")


    
    if arg.csv_files_dir != None:
        M = loadModelMatrixes(arg.csv_files_dir)
        X = getAllMatrixFromSet(M)
        # Override default parameter
        build_dataset = True 
    elif arg.load_matrix_from_csv != None:
    	X = loadMatrixesFromCsv(arg.load_matrix_from_csv)
    	build_dataset = True
    elif arg.load_matrix_from_json != None:
        X = loadModelMatrixesFromJson(arg.load_matrix_from_json)
        build_dataset = True
    else:
        X = generateInputDataset()


    print ("[INFO] : Training dataset len : " , str(len(X)), sep="")
    
    
    if build_dataset == True:
        r = tuneLibrary(X,output_dir,arg.kernel_name)
        if r > 0:
            print ("[FATAL] : exit")
            exit(1)
  


################################################################################
################################################################################

# MAIN 
################################################################################
parser = argparse.ArgumentParser(description='Adaptive Library')


#parser.add_argument("--random_samples", action = "store", type = int, dest = "random_num", help = "Number of random matrix sizes. The tuner will be launched on each matrix")
parser.add_argument("--output_dir", action = "store", required = True, dest = "output_dir", help = "output_dir to store tuner results over training data")
#parser.add_argument("--target_os", action = "store", dest = "tos")
parser.add_argument("--device_id", action = "store", type = int, dest = "device_id", required = True)
parser.add_argument("--kernel", action = "store", dest = "kernel_name", nargs ='*', default = ["xgemm"], help = "kernel name(s) you want data train on")
#parser.add_argument("--seed", type = int, help = "You can specify the initial seed for reproducibility. It only works with --random_samples")
parser.add_argument("--quiet", action = "store_true", help = "It will suppress CK output")
parser.add_argument("--csv", action="store", dest ="csv_files_dir", help="load Model matrix sizes from csv")
parser.add_argument("--load_matrix_from_csv", action="store", help="load Model matrix sizes from csv")
parser.add_argument("--store_on_json", action = "store", dest = "out_json_file", default = 'out', help = "dump the training set on file")
#parser.add_argument("--dataset_dir", action ="store", help = "the directory containing the dataset")
parser.add_argument("--load_matrix_from_json", action = "store")
#parser.add_argument("--load_dataset_from_json", action = "store", dest ="fp", help = "Json file containing dump of training data")
parser.add_argument("--ratio", action = "store", dest = "ratio", help = "define the ratio between training and test sets (default 80:20 pareto)")

parser.add_argument("--platform", action = "store", required = True)
myarg=parser.parse_args()

platform = myarg.platform

out_dir = '/tmp'
if myarg.output_dir != None :
    out_dir = myarg.output_dir

device_id = myarg.device_id;

pipeline_output = 'out' if myarg.quiet else 'con'
DATASET=createTrainingSet(myarg)
print ("[INFO] : Dataset created")

