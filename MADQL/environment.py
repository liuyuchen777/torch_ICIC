import logging
import numpy as np
from config import Config
from utils import index2str, neighbor_table, judge_skip
from channel import Channel


class Environment:
    def __init__(self, CUs):
        self.logger = logging.getLogger(__name__)
        self.config = Config()
        self.CUs = CUs
        self.channels = dict()  # dict(channel_index) -> Channel
        self._init_channel_()

    def _init_channel_(self):
        """
        build all channels
        """
        for cu in self.CUs:
            for sector in cu.sectors:
                # intra CU
                for ue in cu.UEs:
                    channel = Channel(sector, ue)
                    self.channels[index2str(channel.index)] = channel
                # inter CU
                for other_cu in self.CUs:
                    if other_cu.index == cu.index:
                        continue
                    for ue in other_cu.UEs:
                        channel = Channel(sector, ue)
                        self.channels[index2str(channel.index)] = channel

    def get_channel(self):
        return self.channels

    def print_channel(self):
        for (k, v) in self.channels.items():
            print(f'CSI of index {k}:')
            print(f'{v.get_csi()}')

    def step(self):
        for v in self.channels.values():
            v.step()

    def cal_reward(self):
        """
        use action and CSI calculate each CU's reward
        return in list, length of CU number
        NOTICE: characteristic of three-sector model
        """
        reward = []
        for cu in self.CUs:
            action_index = cu.get_decision_index()
            r = 0.
            for sector in cu.sectors:
                # calculate SINR
                w_i_k = self.config.beamform_list[action_index[sector.index][0]] \
                        * self.config.power_list[action_index[sector.index][1]]
                direct_channel = self.channels[index2str([cu.index, sector.index, cu.index, sector.index])].get_csi()
                up = np.linalg.norm(np.matmul(direct_channel, w_i_k)) ** 4
                bottom = self.config.noise_power * np.linalg.norm(np.matmul(direct_channel, w_i_k)) ** 2
                # intra CU interference
                for other_sector in cu.sectors:
                    if sector.index != other_sector.index:
                        w_j_k = self.config.beamform_list[action_index[other_sector.index][0]] \
                                * self.config.power_list[action_index[other_sector.index][1]]
                        # same cu channel
                        sc_channel = self.channels[index2str([cu.index, other_sector.index, cu.index, sector.index])] \
                            .get_csi()
                        bottom += np.linalg.norm(np.matmul(np.matmul(
                            np.matmul(np.transpose(w_j_k), np.transpose(sc_channel)), sc_channel),w_j_k)) ** 2
                # inter CU interference
                neighbor = neighbor_table[cu.index]
                for other_cu_index in neighbor:
                    other_cu = self.CUs[other_cu_index]
                    for other_cu_sector in other_cu.sectors:
                        index = [cu.index, sector.index, other_cu.index, other_cu_sector.index]
                        if judge_skip(index):
                            continue
                        w_j_l = self.config.beamform_list[action_index[other_cu_sector.index][0]] \
                                * self.config.power_list[action_index[other_cu_sector.index][1]]
                        ocs_channel = self.channels[index2str(index)].get_csi()
                        bottom += np.linalg.norm(np.matmul(np.matmul(
                            np.matmul(np.transpose(w_j_l), np.transpose(ocs_channel)), ocs_channel), w_j_l)) ** 2
                # use SINR calculate capacity
                SINR = up / bottom
                cap = np.log2(1 + SINR)
                r += cap
            # calculate reward
            r /= 3
            reward.append(r)

        return reward
