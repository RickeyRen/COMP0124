"""
# @Time    : 2021/6/30 10:07 下午
# @Author  : hezhiqiang
# @Email   : tinyzqh@163.com
# @File    : train.py
"""
import random

#  TODO env的seed需要设置，否则每次启动的env都是一样的，这样就无法进行对比了
#  TODO 环境更复杂
# !/usr/bin/env python
import sys
import os
import socket
import setproctitle
import numpy as np
from pathlib import Path
import torch
from metadrive.component.sensors.rgb_camera import RGBCamera
from metadrive.policy.idm_policy import ManualControllableIDMPolicy

# Get the parent directory of the current file
parent_dir = os.path.abspath(os.path.join(os.getcwd(), "."))

# Append the parent directory to sys.path, otherwise the following import will fail
sys.path.append(parent_dir)

from config import get_config
from envs.env_wrappers import DummyVecEnv


def parse_args(args, parser):
    parser.add_argument("--scenario_name", type=str, default="MyEnv", help="Which scenario to run on")
    # parser.add_argument("--num_landmarks", type=int, default=3)
    all_args = parser.parse_known_args(args)[0]
    return all_args


def main(args):
    parser = get_config()
    print("-------------------------content inside parser------------------------------------")
    print(parser)
    print("-------------------------------------------------------------")
    all_args = parse_args(args, parser)
    print("---------------------------content inside all_args----------------------------------")
    print(all_args)
    print("-------------------------------------------------------------")
    if all_args.algorithm_name == "rmappo":
        assert all_args.use_recurrent_policy or all_args.use_naive_recurrent_policy, "check recurrent policy!"
    elif all_args.algorithm_name == "mappo":
        assert (
            all_args.use_recurrent_policy == False and all_args.use_naive_recurrent_policy == False
        ), "check recurrent policy!"
    else:
        raise NotImplementedError

    assert (
        all_args.share_policy == True and all_args.scenario_name == "simple_speaker_listener"
    ) == False, "The simple_speaker_listener scenario can not use shared policy. Please check the config.py."

    # cuda
    if all_args.cuda and torch.cuda.is_available():
        print("choose to use gpu...")
        device = torch.device("cuda:0")
        torch.set_num_threads(all_args.n_training_threads)
        if all_args.cuda_deterministic:
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True
    else:
        print("choose to use cpu...")
        device = torch.device("cpu")
        torch.set_num_threads(all_args.n_training_threads)

    # run dir
    run_dir = (
        Path(os.path.split(os.path.dirname(os.path.abspath(__file__)))[0] + "/results")
        / all_args.env_name
        / all_args.scenario_name
        / all_args.algorithm_name
        / all_args.experiment_name
    )
    if not run_dir.exists():
        os.makedirs(str(run_dir))

    if not run_dir.exists():
        curr_run = "run1"
    else:
        exst_run_nums = [
            int(str(folder.name).split("run")[1])
            for folder in run_dir.iterdir()
            if str(folder.name).startswith("run")
        ]
        if len(exst_run_nums) == 0:
            curr_run = "run1"
        else:
            curr_run = "run%i" % (max(exst_run_nums) + 1)
    run_dir = run_dir / curr_run
    if not run_dir.exists():
        os.makedirs(str(run_dir))

    setproctitle.setproctitle(
        str(all_args.algorithm_name)
        + "-"
        + str(all_args.env_name)
        + "-"
        + str(all_args.experiment_name)
        + "@"
        + str(all_args.user_name)
    )

    # seed
    torch.manual_seed(all_args.seed)
    torch.cuda.manual_seed_all(all_args.seed)
    np.random.seed(all_args.seed)

    # env init
    # envs = make_train_env(all_args)
    # eval_envs = make_eval_env(all_args) if all_args.use_eval else None
    num_agents = all_args.num_agents

    config_train=dict(
        random_spawn_lane_index=False,
        start_seed=0,
        use_render=all_args.use_render,
        crash_done= True,
        sensors=dict(rgb_camera=(RGBCamera, 512, 256)),
        # start_seed=random.randint(0, 1000),
        show_coordinates=True,
        image_observation=False,
        # interface_panel=["rgb_camera", "dashboard"],
        random_traffic=all_args.human_vehicle,
        traffic_density=all_args.traffic_density[all_args.env] if all_args.human_vehicle else 0,

        #agent_policy=ManualControllableIDMPolicy,
        num_agents=num_agents,
        vehicle_config=dict(
            show_navi_mark=all_args.show_navi,
            show_dest_mark=all_args.show_navi,
            show_line_to_dest=all_args.show_navi,
            use_special_color=True,
            random_color=False,
            lidar=dict(
                add_others_navi=False,
                num_others=4,
                distance=50,
                num_lasers=30,
            ),
            side_detector=dict(num_lasers=30),
            lane_line_detector=dict(num_lasers=12),
        )
    )

    config_eval=dict(
        random_spawn_lane_index=False,
        start_seed=0,
        use_render=all_args.use_render_eval,
        crash_done=True,
        sensors=dict(rgb_camera=(RGBCamera, 512, 256)),
        # start_seed=random.randint(0, 1000),
        show_coordinates=True,
        image_observation=False,
        # interface_panel=["rgb_camera", "dashboard"],
        random_traffic=all_args.human_vehicle,
        traffic_density=all_args.traffic_density[all_args.env] if all_args.human_vehicle else 0,


        # agent_policy=ManualControllableIDMPolicy,
        num_agents=num_agents,
        vehicle_config=dict(
            show_navi_mark=all_args.show_navi,
            show_dest_mark=all_args.show_navi,
            show_line_to_dest=all_args.show_navi,
            use_special_color=True,
            random_color=False,
            lidar=dict(
                add_others_navi=False,
                num_others=4,
                distance=50,
                num_lasers=30,
            ),
            side_detector=dict(num_lasers=30),
            lane_line_detector=dict(num_lasers=12),
        )
    )


    config = {
        "all_args": all_args,
        "config_train": config_train,
        "config_eval": config_eval,
        "num_agents": num_agents,
        "device": device,
        "run_dir": run_dir,
    }

    # run experiments
    if all_args.share_policy:
        from runner.shared.env_runner import EnvRunner as Runner
    else:
        from runner.separated.env_runner import EnvRunner as Runner

    runner = Runner(config)
    runner.run()

    # post process
    runner.envs.close()
    if all_args.use_eval:
        runner.eval_envs.close()

    # if all_args.use_eval and eval_envs is not envs:
    #     runner.eval_envs.close()

    runner.writter.export_scalars_to_json(str(runner.log_dir + "/summary.json"))
    runner.writter.close()


if __name__ == "__main__":
    main(sys.argv[1:])
