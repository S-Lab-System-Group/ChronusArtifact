for trace in 'Philly_MIX2' #  'Philly_MIX1'  'Helios_MIX2' 'Helios_MIX1'; #   'Helios_MIX2' 'Helios_MIX1' 'Helios_SLO'; #  'Philly_MIX2' 'Philly_SLO'  'Philly_MIX1';
do
obj='adaptive'
if [[ $trace = 'Helios_SLO' ]]; then 
    echo $trace
    name_list='data/name.lst'
    num_node_p_switch=96
    lease_term_interval=20
elif [[ $trace = 'Helios_MIX1' ]]; then 
    num_node_p_switch=96
    lease_term_interval=20
    name_list='data/name.lst'
elif [[ $trace = 'Helios_MIX2' ]]; then 
    num_node_p_switch=96
    lease_term_interval=20
    name_list='data/name.lst'
elif [[ $trace = 'Pri_MIX3' ]]; then 
    num_node_p_switch=96
    lease_term_interval=20
    name_list='data/name.lst'
elif [[ $trace = 'Philly_SLO' ]]; then 
    num_node_p_switch=120
    name_list='data/philly/name.lst'
    lease_term_interval=20
elif [[ $trace = 'Philly_MIX1' ]]; then 
    num_node_p_switch=120
    lease_term_interval=20
    name_list='data/philly/name.lst'
elif [[ $trace = 'Philly_MIX2' ]]; then 
    num_node_p_switch=120
    lease_term_interval=20
    name_list='data/philly/name.lst'
fi

echo $num_node_p_switch
echo $name_list
# python main.py --schedule=srtf --trace=data/exp/trace_job_"$trace".csv --save_log_dir=result/$trace --ident=$trace --placement=consolidate --num_node_p_switch=$num_node_p_switch --name_list=$name_list &
# python main.py --schedule=fifo --trace=data/exp/trace_job_$trace.csv --save_log_dir=result/$trace --ident=$trace --placement=consolidate --num_node_p_switch=$num_node_p_switch --name_list=$name_list &
# python main.py --schedule=themis --trace=data/exp/trace_job_$trace.csv --save_log_dir=result/$trace --ident=$trace --placement=consolidate  --num_node_p_switch=$num_node_p_switch --name_list=$name_list --check_time_interval=5 &
# python main.py --schedule=dlas --trace=data/exp/trace_job_$trace.csv --save_log_dir=result/$trace --ident=$trace --placement=consolidate --num_node_p_switch=$num_node_p_switch --name_list=$name_list &
# python main.py --schedule=tetri-sched --trace=data/exp/trace_job_$trace.csv --save_log_dir=result/$trace --ident=$trace --lease_term_interval=20 --check_time_interval=5 --placement=random --num_node_p_switch=$num_node_p_switch --name_list=$name_list &
# python main.py --schedule=time-aware --trace=data/exp/trace_job_"$trace".csv --save_log_dir=result/$trace --ident=$trace --placement=consolidate --num_node_p_switch=$num_node_p_switch --name_list=$name_list --check_time_interval=1 &
# python main.py --schedule=genie --trace=data/exp/trace_job_"$trace".csv --save_log_dir=result/$trace --ident=$trace --placement=consolidate --num_node_p_switch=$num_node_p_switch --name_list=$name_list --check_time_interval=5 &
# python main.py --schedule=sigma --trace=data/exp/trace_job_$trace.csv --save_log_dir=result/$trace --ident=$trace --lease_term_interval=15 --check_time_interval=15 --placement=consolidate --num_node_p_switch=$num_node_p_switch --name_list=$name_list &
python main.py --schedule=time-aware-with-lease --trace=data/exp/trace_job_"$trace".csv --save_log_dir=result/$trace --ident=$trace --aggressive=True   --mip_objective=$obj --placement=local_search --profile=True --check_time_interval=1 --disable_turn_off=True --num_node_p_switch=$num_node_p_switch --lease_term_interval=$lease_term_interval  --name_list=$name_list  & 
done

# standard
# python main.py --schedule=tetri-sched --trace=data/exp/trace_job_$trace.csv --save_log_dir=result/$trace --ident=$trace --lease_term_interval=15 --check_time_interval=5 --placement=random --num_node_p_switch=$num_node_p_switch --name_list=$name_list &
# python main.py --schedule=time-aware --trace=data/exp/trace_job_"$trace".csv --save_log_dir=result/$trace --ident=$trace --placement=consolidate --num_node_p_switch=$num_node_p_switch --name_list=$name_list --check_time_interval=10 &

# bash run/exp_cluster/batch_run.sh
# python run/exp_cluster/eval.py --input_file_dir=result --output_file_dir=stats