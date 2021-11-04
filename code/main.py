
import os, sys
import csv, json
import numpy as np
import pandas as pd
import options
from alg import PlaceMentFactory, TimeAwareWithLeaseScheduler
from server import cluster, profiler
from client import jobs, users
from client.jobs import Job
from client.users import VanillaUser, TimeAwareUser
from utils.logger import getLogger

opt = options.Singleton.init()
print(opt)
USERS = users.USERS
JOBS = jobs.JOBS
CLUSTER = cluster.CLUSTER
ProfileManager = profiler.ProfileManager

if not os.path.exists('log/'):
    os.makedirs('log/')
logger = getLogger(name='log/{}_{}_{}'.format(opt.schedule, opt.placement, opt.ident), level=opt.log_level)


def parse_job_file(trace_file):
    #check trace_file is *.csv
    fd = open(trace_file, 'r')
    deli = ','
    if ((trace_file.find('.csv') == (len(trace_file) - 4))):
        deli = ','
    elif ((trace_file.find('.txt') == (len(trace_file) - 4))):
        deli = ' '

    reader = csv.DictReader(fd, delimiter = deli)
    for idx, info_dict in enumerate(reader):
        if 'num_gpu' not in info_dict or info_dict['num_gpu'] == "0":
            continue
        exist_user = USERS.index_user(info_dict['user'])
        info_dict['user'] = exist_user
        if 'expect_time_list' in info_dict:
            info_dict['expect_time_list'] = [int(item) for item in info_dict['expect_time_list'].split('-')]
            info_dict['expect_value_list'] = [int(item) for item in info_dict['expect_value_list'].split('-')]
            info_dict['expect_time'] = info_dict['expect_time_list'][0]
        new_job = Job(info_dict)
        exist_user.submit_job(new_job)
    
    assert JOBS.num_job == len(JOBS.job_list) 

    JOBS.sort_all_jobs(key='submit_time')
    fd.close()


def prepare_partion_size(filename):
    user_partition_size = dict()
    share = pd.read_csv(filename)
    for index, row in share.iterrows():
        user_partition_size[row['user_name']] = int(int(row['partition_size']) * 0.6)
    
    return user_partition_size
       

def prepare_cluster():
    if opt.num_node_p_switch == -1:
        partition_size_info = prepare_partion_size(opt.user_partition_size)
        opt.num_node_p_switch = partition_size_info[opt.user_partition]
    

    CLUSTER.init_infra(num_switch=opt.num_switch, 
                        num_node_p_switch=opt.num_node_p_switch, 
                        num_gpu_p_node=opt.num_gpu_p_node, 
                        num_cpu_p_node=opt.num_cpu_p_node, 
                        mem_p_node=opt.mem_p_node)

def prepare_cluster_shadow():
    shadow_cluster = cluster._Cluster()
    shadow_cluster.init_infra(num_switch=opt.num_switch, 
                        num_node_p_switch=opt.num_node_p_switch, 
                        num_gpu_p_node=0, 
                        num_cpu_p_node=opt.num_cpu_p_node, 
                        mem_p_node=opt.mem_p_node)
    return shadow_cluster


def prepare_user(namelist):
    with open(namelist, 'r') as f:
        names = f.readlines()
        for name in names:
            if opt.schedule == 'time-aware':
                new_user = TimeAwareUser(JOBS=JOBS, CLUSTER=CLUSTER, name=name.strip(), logger=logger, quota=50)
            else:
                new_user = VanillaUser(JOBS=JOBS, CLUSTER=CLUSTER, name=name.strip(), logger=logger)
            USERS.add_user(new_user)


def summary_all_jobs():
    assert all([job['status'] == 'END' for job in JOBS.job_list])
    num_job = 1.0 * len(JOBS.job_list)
    jct = 0
    
    for job in JOBS.job_list:
        jct += (job['end_time'] - job['submit_time']) / num_job
    logger.info('average jct of scheduler %s is %d'%(opt.schedule,  jct))


def main():
    prepare_cluster()
    prepare_user(opt.name_list)
    with open('data/model_info.json', 'r') as f:
        model_info = json.load(f)

    if opt.cluster_partition == 'static':
        user_share = {user.name:1.0 / len(USERS) for user in USERS}
        CLUSTER.cluster_partition(user_share)
    elif opt.cluster_partition == 'static+dynamic':
        user_share = {user.name:1.0 / len(USERS) for user in USERS}
        CLUSTER.cluster_partition(user_share)
    elif opt.cluster_partition == 'all':
        pass
    else:
        raise NotImplementedError
    
        
    parse_job_file(opt.trace)
    if opt.profile:
        if opt.dynamic_profiler:
            submission_dist=np.load(opt.submission_dist).tolist()
            ProfileManager.dynamic_run(JOBS.job_list, model_info, dry_run=opt.profile_dry_run, \
                duration_limit=opt.profiler_duration, profile_method=opt.profile_method, save_dir=opt.save_log_dir, submission_dist=submission_dist)
        else:
            ProfileManager.build_cluster(node_num=opt.profile_node_num)
            ProfileManager.run(JOBS.job_list, model_info, dry_run=opt.profile_dry_run, \
                duration_limit=opt.profiler_duration, profile_method=opt.profile_method, save_dir=opt.save_log_dir)
        if opt.profile_dry_run:
            exit(0)


    JOBS.prepare_job_start_events()

    global PM
    PM = PlaceMentFactory(cluster=CLUSTER, name=opt.placement, model_info=model_info) # construct placement after init cluster
    if opt.schedule.startswith('time-aware-with-lease') or opt.schedule.startswith('advanced-time-aware-with-lease'):
        consolidatePM = PlaceMentFactory(cluster=CLUSTER, name='consolidate', model_info=model_info)
        PM = (PM, consolidatePM)
    
    if not os.path.exists(opt.save_log_dir):
        os.makedirs(opt.save_log_dir)
    if opt.schedule == 'fifo':
        scheduler = FifoScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                    logger=logger, check_time_interval=opt.check_time_interval, save_dir=opt.save_log_dir)
    elif opt.schedule == 'yarn-cs':
        scheduler = YarnCSScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                    logger=logger, check_time_interval=opt.check_time_interval, save_dir=opt.save_log_dir)
    elif opt.schedule == 'gandiva':
        assert opt.placement == 'gandiva'
        CLUSTER.init_gandiva_nodes()
        scheduler = GandivaScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                    logger=logger, check_time_interval = opt.check_time_interval, save_dir=opt.save_log_dir)
    elif opt.schedule == 'dlas':
        service_list = sorted([job.required_gpu_num * job['duration'] for job in JOBS.job_list])
        num_queue = 2
        queue_limit = np.percentile(service_list, [1.0 * i / num_queue * 100 for i in range(1, num_queue+1)])
        scheduler = DlasScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                        logger=logger, num_queue=num_queue, queue_limit=queue_limit, \
                                        solve_starvation=0, check_time_interval = opt.check_time_interval, save_dir=opt.save_log_dir)

    elif opt.schedule == 'gittins':
        service_list = sorted([job.required_gpu_num * job['duration'] for job in JOBS.job_list])
        num_queue = 3
        queue_limit = np.percentile(service_list, [1.0 * i / num_queue * 100 for i in range(1, num_queue+1)])
        
        scheduler = GittinsScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                        logger=logger, num_queue=num_queue, queue_limit=queue_limit, \
                                            solve_starvation=0, check_time_interval = opt.check_time_interval, save_dir=opt.save_log_dir)

    elif opt.schedule == 'time-aware':
        scheduler = TimeAwareScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                        logger=logger, num_queue=5, queue_limit=[0.1, 0.3, 0.5, 0.8, 1.0], \
                                        solve_starvation=0, check_time_interval = opt.check_time_interval, save_dir=opt.save_log_dir)
    elif opt.schedule == 'genie':
        scheduler = GenieScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                        logger=logger, num_queue=5, queue_limit=[0.1, 0.3, 0.5, 0.8, 1.0], \
                                        solve_starvation=0, check_time_interval = opt.check_time_interval, save_dir=opt.save_log_dir)
    elif opt.schedule == 'time-aware-with-lease':
        scheduler = TimeAwareWithLeaseScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                        logger=logger, solve_starvation=0, aggressive=opt.aggressive, \
                                        disable_turn_off=opt.disable_turn_off, mip_objective=opt.mip_objective, \
                                        disable_force_guarantee=opt.disable_force_guarantee, \
                                        disable_noise_tolerance=opt.disable_noise_tolerance, \
                                        noise_diff=opt.noise_diff, \
                                        check_time_interval=opt.check_time_interval, \
                                        lease_term_interval=opt.lease_term_interval,  \
                                        cluster_partition=opt.cluster_partition, save_dir=opt.save_log_dir, 
                                        model_info=model_info)
    elif opt.schedule == 'advanced-time-aware-with-lease':
        scheduler = AdvancedTimeAwareWithLeaseScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                        logger=logger, mip_objective=opt.mip_objective, \
                                        disable_noise_tolerance=opt.disable_noise_tolerance, \
                                        noise_diff=opt.noise_diff, \
                                        check_time_interval=opt.check_time_interval, \
                                        lease_term_interval=opt.lease_term_interval,  \
                                        cluster_partition=opt.cluster_partition, save_dir=opt.save_log_dir, 
                                        model_info=model_info)
    elif opt.schedule == 'time-aware-with-lease-with-multi-tenancy':
        scheduler = TimeAwareWithLeaseSchedulerWithMultiTenancy(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                        logger=logger, solve_starvation=0, aggressive=opt.aggressive, \
                                        disable_turn_off=opt.disable_turn_off, mip_objective=opt.mip_objective, \
                                        disable_force_guarantee=opt.disable_force_guarantee, \
                                        check_time_interval=opt.check_time_interval, \
                                        lease_term_interval=opt.lease_term_interval,  \
                                        cluster_partition=opt.cluster_partition, save_dir=opt.save_log_dir, 
                                        model_info=model_info)
    elif opt.schedule == 'tetri-sched':
        scheduler = TetriSchedScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                        logger=logger, solve_starvation=0, \
                                        check_time_interval=opt.check_time_interval, \
                                        lease_term_interval=opt.lease_term_interval, save_dir=opt.save_log_dir)
    elif opt.schedule == 'sigma':
        scheduler = SigmaScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                        logger=logger, solve_starvation=0, \
                                        check_time_interval=opt.check_time_interval, \
                                        lease_term_interval=opt.lease_term_interval, save_dir=opt.save_log_dir)
    
    elif opt.schedule == 'lease':
        scheduler = LeaseScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule,
                                   logger=logger, check_time_interval=opt.check_time_interval,
                                   lease_term_interval=opt.lease_term_interval, replacement=False,
                                   job_selection=opt.job_selection, share=opt.share,
                                   fairness_output=opt.fairness_output,
                                   numgpu_fallback_threshold=opt.numgpu_fallback_threshold,
                                   dist_trace_path=opt.dist_trace_path, metrics=opt.metrics,
                                   disc_priority_k=opt.disc_priority_k,
                                   metrics_path=opt.metrics_path, 
                                   save_dir=opt.save_log_dir)
    elif opt.schedule == 'fairness':
        scheduler = FairnessScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                        logger=logger, dis_priority=False, num_queue=5, queue_limit=[0.8, 1.2, 1.8, 2.6, 3.5], \
                                        solve_starvation=0, check_time_interval = opt.check_time_interval, 
                                        lease_term_interval=opt.lease_term_interval,save_dir=opt.save_log_dir)
    elif opt.schedule == 'themis':
        scheduler = ThemisScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                        logger=logger, dis_priority=False, num_queue=5, queue_limit=[0.8, 1.2, 1.8, 2.6, 3.5], \
                                        solve_starvation=0, check_time_interval = opt.check_time_interval, 
                                        lease_term_interval=opt.lease_term_interval,save_dir=opt.save_log_dir)
    
    elif opt.schedule == 'srtf':
        scheduler = ShortestRemainingTimeFirstScheduler(JOBS=JOBS, CLUSTER=CLUSTER, USERS=USERS, placement=PM, name=opt.schedule, \
                                    logger=logger, check_time_interval = opt.check_time_interval, save_dir=opt.save_log_dir)
    else:
        raise NotImplementedError

    scheduler.run()
    summary_all_jobs()



if __name__ == '__main__':
    main()