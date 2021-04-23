"""
environment of DRL
"""

import numpy as np
from const import P_cb, precoding_matrices, bs_num
from data_generator.data_generator import test_data_generator
from data_generator.channel_capacity import system_capacity

# 可以选择的动作空间 发射功率等级数目*precoding_matrix的大小
action_space = list(range(len(P_cb) * len(precoding_matrices)))


def onehot(index, size):
    r = np.zeros((size,))
    r[index] = 1
    return r


class Env(object):
    def __init__(self, args):
        self.num_agents = args['num_agents']
        self.state_size = test_data_generator(1)[0].shape[1]
        self.action_size = len(action_space)

    def effective_actions(self, agent_actions):
        for i in range(self.num_agents):
            self.power_index[i] = action_space[agent_actions[i]] // len(precoding_matrices)
            self.precoding_index[i] = action_space[agent_actions[i]] % len(precoding_matrices)

    def reset(self):
        self.terminal = False
        self.X, self.G = test_data_generator(1)
        self.X = self.X.reshape(-1)
        self.power_index = np.random.randint(len(P_cb), size=self.num_agents)
        self.precoding_index = np.random.randint(len(precoding_matrices), size=self.num_agents)
        self.state = self.X
        return self.state, 0

    def set_state(self, state, G):
        self.terminal = False
        self.X = state
        self.G = G
        self.power_index = np.random.randint(len(P_cb), size=self.num_agents)
        self.precoding_index = np.random.randint(len(precoding_matrices), size=self.num_agents)
        self.state = self.X
        return self.state, 0

    def step(self, agent_actions):
        self.effective_actions(agent_actions)
        signal_pow = [P_cb[m] for m in list(self.power_index)]
        precoding_index_list = list(self.precoding_index)
        reward = system_capacity(self.G[0], [0, 1, 2], signal_pow, precoding_index_list)
        self.last_actions = agent_actions
        return reward


if __name__ == '__main__':
    args = {'num_agents': bs_num}
    env = Env(args)
    env.reset()
    env.step([3, 3, 3])
