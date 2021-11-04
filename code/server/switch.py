import math
import os, sys
from .node import _Node
sys.path.insert(0, os.path.basename(__file__) + os.sep + '..')
from utils import util
from client import jobs


JOBS = jobs.JOBS


class _Switch(object):

    def __init__(self, id, num_node=0, num_gpu_p_node=0, num_cpu_p_node=0, mem_p_node=0):
        self.num_node = num_node
        self.num_gpu_p_node = num_gpu_p_node
        self.num_cpu_p_node = num_cpu_p_node
        self.mem_p_node = mem_p_node
        self.id = id
        self.node_list = list()


    def add_nodes(self, num_node, num_gpu_p_node, num_cpu_p_node, mem_p_node, belong_cluster):
        self.num_node = num_node
        self.num_gpu_p_node = num_gpu_p_node
        self.num_cpu_p_node = num_cpu_p_node
        self.mem_p_node = mem_p_node
        self.belong_cluster = belong_cluster
        
        for node_id in range(self.num_node):
            node_instance = _Node(node_id, self.num_gpu_p_node, self.num_cpu_p_node, self.mem_p_node)
            node_instance.add_gpus(self.num_gpu_p_node, self)
            
            self.node_list.append(node_instance)

    def add_ir_nodes(self, switch_info, belong_cluster):
        # irregular switch init parameter
        self.num_node = len(switch_info.keys())
        self.belong_cluster = belong_cluster
        self.num_gpu_p_node = dict()
        self.num_cpu_p_node = dict()
        self.mem_p_node = dict()
        

        for node_name, node_info in switch_info.items():
            assert 'node' in node_name, 'node must exists in {}'.format(node_name)
            self.num_gpu_p_node[node_name] = node_info['num_gpu']
            self.num_cpu_p_node[node_name] = node_info['num_cpu']
            self.mem_p_node[node_name] = node_info['mem']
            # construct node instance
            node_instance = _Node(node_name, node_info['num_gpu'], node_info['num_cpu'], node_info['mem'])
            node_instance.add_gpus(node_info['num_gpu'], self)
            self.node_list.append(node_instance)


    def ir_init(self, switch_info):
        self.num_node = len(switch_info.keys())
        self.num_gpu_p_node = dict()
        self.num_cpu_p_node = dict()
        self.mem_p_node = dict()
        for node_name, node_info in switch_info.items():
            assert 'node' in node_name, 'node must exists in {}'.format(node_name)
            self.num_gpu_p_node[node_name] = node_info['num_gpu']
            self.num_cpu_p_node[node_name] = node_info['num_cpu']
            self.mem_p_node[node_name] = node_info['mem']



    def try_cross_node_alloc(self, job):
        '''
        used in MS_YARN placement
        try get gpus from multiple nodes
            [need_gpu / gpu_p_node] nodes, and one node with [need_gpu % gpu_p_node]
        if can't find , give up, and return False
        '''
        need_gpu = job['num_gpu']
        num_full_nodes = math.floor(need_gpu / self.num_gpu_p_node)
        last_node_gpu =  need_gpu % self.num_gpu_p_node
        last_node_cpu = int(last_node_gpu * 6)
        last_node = None
        idle_node_cpu = int(self.num_gpu_p_node * 6) #w:2, ps:4

        model_size = job['model']['total_size']

        ps_mem = JOBS.ps_mem + need_gpu * JOBS.p_w_mem
        ps_w_mem = ps_mem + JOBS.worker_mem 

        full_node_list = list()
        for node in self.node_list:
            if node.check_free_gpus() == node.num_gpu and node.check_free_cpus() >= idle_node_cpu and node.free_mem >= (ps_w_mem * node.num_gpu):
                #get idle node
                full_node_list.append(node)
                if len(full_node_list) == num_full_nodes:
                    #enough full nodes
                    break
        if len(full_node_list) < num_full_nodes:
            return False 

        if last_node_gpu != 0:
            for node in self.node_list: 
                if node not in full_node_list:
                    if node.check_free_gpus() >= last_node_gpu and node.check_free_cpus() >= last_node_cpu and node.free_mem >= (ps_w_mem * last_node_gpu):
                        #get last node
                        last_node = node
                        break
            if last_node == None:
                return False


        ''' can allocate, do resource counting and record job placement '''
        node_list = list()
        idx = 0
        for node in full_node_list:
            node.alloc_job_res(node.num_gpu, idle_node_cpu)  
            node.free_mem -= ps_w_mem * node.num_gpu
            node_dict = dict()
            node_dict['id'] = node.id
            node_dict['num_gpu'] = node.num_gpu
            node_dict['num_cpu'] = idle_node_cpu
            node_dict['mem'] = ps_w_mem * node.num_gpu

            # traffic = round(model_size * node.num_gpu, 1)
            # for i in range(0, node.num_gpu):
            #     traffic += traffic + job['ps_network'][idx]
            #     traffic = round(traffic, 1)
            #     idx += 1

            #worker traffic
            traffic = round(model_size * node.num_gpu, 1)
            #ps traffic
            for i in range(0, node.num_gpu):
                #add ps traffic
                traffic += job['ps_network'][idx] * (need_gpu - node.num_gpu) #send to (need - local_gpu) workers, no need for local PS-to-worker
                #remove co-locate worker traffic
                traffic -= job['ps_network'][idx] * node.num_gpu #no need for local worker-to-PS
                traffic = round(traffic, 1)
                idx += 1
            node_dict['network'] = traffic
            node.add_network_load(traffic, traffic)

            node_dict['tasks'] = list()
            node_list.append(node_dict)

        if last_node_gpu != 0:
            last_node.alloc_job_res(last_node_gpu, last_node_cpu)
            last_node.free_mem -= ps_w_mem * last_node_gpu 
            node_dict = dict()
            node_dict['id'] = last_node.id
            node_dict['num_gpu'] = last_node_gpu
            node_dict['num_cpu'] = last_node_cpu
            node_dict['mem'] = ps_w_mem * last_node_gpu

            traffic = round(model_size * last_node_gpu, 1)
            # for i in range(0, last_node_gpu):
            #     traffic += job['ps_network'][idx]
            #     traffic = round(traffic, 1)
            #     idx += 1
            for i in range(0, last_node_gpu):
                traffic += job['ps_network'][idx] * (need_gpu - last_node_gpu) #send to (need-last_gpu), no need for local PS-to-worker
                traffic -= job['ps_network'][idx] * last_node_gpu #no need for local worker-to-PS
                traffic = round(traffic, 1)
                idx += 1
            node_dict['network'] = traffic
            last_node.add_network_load(traffic, traffic)

            node_dict['tasks'] = list()
            node_list.append(node_dict)

        JOBS.create_multi_nodes_placement(job, self.id, node_list)
        return True


    def try_single_node_alloc(self, job):
        '''
        used in MS_YARN placement
        try get gpus from a single node
        if can't find a node, give up, and return False
        '''
        need_gpu = job['num_gpu']
        if len(job['ps_network']) == 0 and job['num_gpu'] == 1:
            need_cpu = int(need_gpu * 2) # worker:2
        else:
            need_cpu = int(need_gpu * 6) # worker:2, ps:4
        user_name = job['user'].name if 'user' in job else None
        for node in self.node_list:
            if (node.check_free_gpus(user_name) >= need_gpu) and (node.check_free_cpus() >= need_cpu) and (node.free_mem >= JOBS.worker_mem):
                # if node.alloc_gpus(need_gpu) == False:
                if node.alloc_job_res(need_gpu, need_cpu) == False:
                    continue
                node.free_mem = node.free_mem - JOBS.worker_mem
                traffic = JOBS.create_single_node_placement(job, self.id, node.id, need_gpu, need_cpu, JOBS.worker_mem)
                # node.add_network_load(traffic, traffic)

                return True
            else:
                continue

        return False


    def ms_yarn_alloc_gpus(self, job):
        '''
        ms_yarn allocates gpus from a single switch, 
        if no enough gpus, give up, return False (all-or-nothing)

        if need_gpu > gpu_p_node
            then get [need_gpu / gpu_p_node] nodes, and one node with [need_gpu % gpu_p_node]
        if need_gpu <= gpu_p_node
            then get one node with enough gpus
        '''
        need_gpu = job['num_gpu']
        ret = False
        if need_gpu > self.num_gpu_p_node:
            ret = self.try_cross_node_alloc(job)
        else:
            ret = self.try_single_node_alloc(job)

        return ret

    def ms_yarn_alloc_res(self, job):
        '''
        ms_yarn allocates res from a single switch, 
        if no enough gpus, give up, return False (all-or-nothing)

        if need_gpu > gpu_p_node
            then get [need_gpu / gpu_p_node] nodes, and one node with [need_gpu % gpu_p_node]
        if need_gpu <= gpu_p_node
            then get one node with enough gpus
        '''
        need_gpu = job['num_gpu']
        ret = False
        if need_gpu > self.num_gpu_p_node:
            ret = self.try_cross_node_alloc(job)
        else:
            ret = self.try_single_node_alloc(job)

        return ret

    def release_gpus(self, nodes):
        '''
        release gpus from nodes
        nodes:
        [{'id':xx, 'num_gpu':xxx}, {'id':xx, 'num_gpu':xxx}]
        '''
        for node_dict in nodes:
            if ('id' not in node_dict) or ('num_gpu' not in node_dict):
                return False
            node = self.node_list[node_dict['id']]
            ret = node.release_gpus(node_dict['num_gpu'])
            if ret == False:
                return False

        return True

    def release_job_resource(self, nodes, job):
        '''
        release job resources from nodes
        nodes:
        [{'id':xx, 'num_gpu':xxx, 'num_cpu': xxx, 'network': xxxx, 'tasks': [w2, ps2]}, 
        {'id':xx, 'num_gpu':xxx, 'num_cpu': xxx, 'network': xxxx, 'tasks': [ps0]}]
        '''
        
        for node_dict in nodes:
            if ('id' not in node_dict) or ('num_gpu' not in node_dict) or ('num_cpu' not in node_dict) or ('tasks' not in node_dict):
                return False
            found = False
            for node in self.node_list:
                if node_dict['id'] == node.id:
                    found = True
                    ret = node.release_job_resource(node_dict, job=job)
            assert found == True, 'should exist in node_list'
            if ret == False:
                return False

        return True

        
    def check_free_gpus(self, user_name=None):
        return sum([node.check_free_gpus(user_name) for node in self.node_list])
    
    def check_free_guarante_gpus(self, user_name=None):
        return sum([node.check_free_guarante_gpus(user_name) for node in self.node_list])

    def check_free_spot_gpus(self, user_name=None):
        return sum([node.check_free_spot_gpus(user_name) for node in self.node_list])

    def check_total_gpus(self, user_name=None):
        return sum([node.check_total_gpus(user_name) for node in self.node_list])

    def check_total_guarante_gpus(self, user_name=None):
        return sum([node.check_total_guarante_gpus(user_name) for node in self.node_list])

    def check_total_spot_gpus(self, user_name=None):
        return sum([node.check_total_spot_gpus(user_name) for node in self.node_list])

    def check_free_cpus(self, ):
        return sum([node.check_free_cpus() for node in self.node_list])


    def check_total_cpus(self, ):
        return sum([node.check_total_cpus() for node in self.node_list])
