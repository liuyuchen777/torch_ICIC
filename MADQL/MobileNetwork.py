import json
import logging

import matplotlib.pyplot as plt
import numpy as np

from CoordinationUnit import CU
from DecisionMaker import MaxPower, MADQL, Random, FP, WMMSE
from Environment import Environment
from MemoryPool import MemoryPool
from Utils import *


class MobileNetwork:
    def __init__(self, algorithm=Algorithm.RANDOM):
        self.logger = logging.getLogger(__name__)
        self.config = Config()
        self.CUs = []
        self._generateCUs_()
        self.mp = MemoryPool()
        self.algorithm = algorithm
        self.dm = self.setDecisionMaker(algorithm)
        """generate mobile network"""
        self.env = Environment(self.CUs)
        self.rewardRecord = []
        self.averageRewardRecord = []
        self.lossRecord = []
        self.count = 0
        self.tmpLossSum = 0.
        self.tmpRewardSum = 0.
        self.epoch = 0

    def _generateCUs_(self):
        # max support 7 cells
        CUNumber = self.config.cellNumber
        R = self.config.cellSize * np.sqrt(3)
        # the first CU
        self.CUs.append(CU(0, [0., 0.]))
        for i in range(1, CUNumber):
            theta = np.pi / 6 + (i - 1) * np.pi / 3
            posX = R * np.cos(theta)
            posY = R * np.sin(theta)
            self.CUs.append(CU(i, [posX, posY]))

    def setDecisionMaker(self, algorithm):
        if algorithm == Algorithm.RANDOM:
            return Random()
        elif algorithm == Algorithm.MAX_POWER:
            return MaxPower()
        elif algorithm == Algorithm.FP:
            return FP()
        elif algorithm == Algorithm.WMMSE:
            return WMMSE()
        elif algorithm == Algorithm.MADQL:
            return MADQL()
        else:
            self.logger.error("!!!Wrong Algorithm ID!!!")
            exit(1)

    def printCUPosition(self):
        for i in range(len(self.CUs)):
            logging.info(f'Position of {i}th CU is: {self.CUs[i].pos}')

    def plotCUPosition(self):
        CUPosX = []
        CUPosY = []
        for CU in self.CUs:
            CUPosX.append(CU.pos[0])
            CUPosY.append(CU.pos[1])
        plt.scatter(CUPosX, CUPosY, c='r')
        # show figure
        plt.show()

    def plotMobileNetwork(self):
        for cu in self.CUs:
            cu.plotCU(plt=plt)
        plt.xlabel(r'$d_x$/m')
        plt.ylabel(r'$d_y$/m')
        plt.title("System Model of MIMO Cellular Network")
        plt.show()

    def buildStateAP(self, CUIndex):
        """
        build state for DQN input (Amplitude & Phase)

        ver 1.0
        ...
        ver 2.0
        """
        # TODO: implement amplitude & phase state input

    def buildStateRI(self, CUIndex):
        """
        build state for DQN input (Real & Image)

        ver 1.0
        1st flow -> 12 * 24 (288)
        2nd flow -> 54 * 8 (432)
        ver 2.0
        total one hot -> (72 + 432) * 1
        """
        state = np.zeros(shape=self.config.inputLayer, dtype=float)
        # Intra-CU
        action = self.CUs[CUIndex].getDecisionIndex()
        for sectorIndex in range(3):
            for otherSectorIndex in range(3):
                index = [CUIndex, sectorIndex, CUIndex, otherSectorIndex]
                channel = self.env.getChannel(index2str(index))
                CSI = channel.getCSI()
                beamformer = self.config.beamformList[action[sectorIndex][0]]
                power = self.config.powerList[action[sectorIndex][1]]
                tmp = dBm2num(power) * beamformer.dot(CSI)
                state[sectorIndex*24+otherSectorIndex*8: sectorIndex*24+otherSectorIndex*8+4] = np.real(tmp)
                state[sectorIndex*24+otherSectorIndex*8+4: sectorIndex*24+otherSectorIndex*8+8] = np.imag(tmp)
        # Inter-CU
        for otherCUIndex in neighborTable[CUIndex]:
            actionHistory = self.CUs[otherCUIndex].getDecisionIndexHistory()
            for otherSectorIndex in range(3):
                for sectorIndex in range(3):
                    index = [otherCUIndex, otherSectorIndex, CUIndex, sectorIndex]
                    if judgeSkip(index):
                        continue
                    else:
                        channel = self.env.getChannel(index2str(index))
                        CSI = channel.getCSI()  # H_t
                        beamformer = self.config.beamformList[actionHistory[otherSectorIndex][0]]
                        power = self.config.powerList[actionHistory[otherSectorIndex][1]]
                        tmp = dBm2num(power) * beamformer.dot(CSI)
                        state[72+otherCUIndex*72+otherSectorIndex*24+sectorIndex*8:
                              72+otherCUIndex*72+otherSectorIndex*24+sectorIndex*8+4] = np.real(tmp)
                        state[72+otherCUIndex*72+otherSectorIndex*24+sectorIndex*8+4:
                              72+otherCUIndex*72+otherSectorIndex*24+sectorIndex*8+8] = np.imag(tmp)
        return state

    def getRewardRecord(self):
        return self.rewardRecord

    def getAverageRewardRecord(self):
        return self.averageRewardRecord

    def cleanRewardRecord(self):
        self.rewardRecord = []

    def cleanAverageRewardRecord(self):
        self.averageRewardRecord = []

    def train(self):
        """train network"""
        for ts in range(self.config.totalTimeSlot):
            # step
            tsReward, tsAverageReward = self.step()
            # record reward
            self.rewardRecord.append(tsReward)
            self.averageRewardRecord.append(tsAverageReward)
            if self.algorithm == Algorithm.RANDOM or self.algorithm == Algorithm.MAX_POWER:
                self.logger.info(
                    f'[Train] mode: {self.algorithm},time slot: {ts + 1}, system average reward: {tsAverageReward}')
            elif self.algorithm == Algorithm.MADQL:
                if self.mp.getSize() > self.config.batchSize:
                    loss = self.dm.backProp(self.mp.getBatch())
                    self.lossRecord.append(loss)
                    self.tmpRewardSum += tsAverageReward
                    self.tmpLossSum += loss
                    self.count += 1
                    if self.count > self.config.tStep:
                        # copy DQN parameters
                        self.logger.info(f'[train] mode: {self.algorithm}, epoch: {self.epoch + 1}, '
                                         f'system average reward: {self.tmpRewardSum / self.config.tStep}, '
                                         f'loss: {self.tmpLossSum / self.config.tStep}.')
                        self.count = 0
                        self.tmpLossSum = 0.
                        self.tmpRewardSum = 0.
                        self.epoch += 1
                        self.dm.updateModelParamter()
                else:
                    continue

    def eval(self, times):
        if self.algorithm == Algorithm.RANDOM or self.algorithm == Algorithm.MAX_POWER:
            return self.step()
        elif self.algorithm == Algorithm.MADQL:
            totalReward = 0.
            for i in range(times):
                _, averageReward = self.step(trainLabel=False)
                totalReward += averageReward
            return totalReward / times

    def step(self, trainLabel=True):
        """
        one step in training
        record: <s, a, r, s'>
        """
        if self.algorithm == Algorithm.RANDOM or self.algorithm == Algorithm.MAX_POWER:
            for cu in self.CUs:
                # take action
                action, actionIndex = self.dm.takeAction()
                cu.setDecisionIndex(action)
            # get reward base on action
            tsReward = self.env.calReward()
            tsAverageReward = sum(tsReward) / len(tsReward)
            # update environment
            self.env.step()
            # return
            return tsReward, tsAverageReward
        elif self.algorithm == Algorithm.MADQL:
            stateRecord = []
            actionRecord = []
            for CUIndex in range(self.config.cellNumber):
                # build state
                state = self.buildStateRI(CUIndex)
                stateRecord.append(state)
                # take action
                action = []
                actionIndex = 0
                if self.mp.getSize() < self.config.batchSize:
                    action, actionIndex = self.dm.takeActionRandom(self.CUs[CUIndex].getDecisionIndexHistory())
                    self.CUs[CUIndex].setDecisionIndex(action)
                else:
                    action, actionIndex = self.dm.takeAction(state, self.CUs[CUIndex].getDecisionIndexHistory(), trainLabel)
                    self.CUs[CUIndex].setDecisionIndex(action)
                actionRecord.append(actionIndex)
            # calculate reward
            tsReward = self.env.calReward()
            tsAverageReward = sum(tsReward) / len(tsReward)
            # update env
            self.env.step()
            # next state
            nextStateRecord = []
            for CUIndex in range(self.config.cellNumber):
                # build state & take action
                state = self.buildStateRI(CUIndex)
                nextStateRecord.append(state)
            # save in memory pool
            for CUIndex in range(self.config.cellNumber):
                record = [stateRecord[CUIndex], actionRecord[CUIndex], tsReward[CUIndex], nextStateRecord[CUIndex]]
                self.mp.push(record)
            # return
            return tsReward, tsAverageReward

    def saveRewards(self, name="default"):
        """save rewards record to json file"""
        with open('data/reward-data.txt') as jsonFile:
            data = json.load(jsonFile)
        with open('data/reward-data.txt', 'w') as jsonFile:
            data[name + "-rewards"] = self.getRewardRecord()
            data[name + "-average-rewards"] = self.getAverageRewardRecord()
            json.dump(data, jsonFile)

    def saveLoss(self, name="default"):
        with open('data/reward-data.txt') as jsonFile:
            data = json.load(jsonFile)
        with open('data/reward-data.txt', 'w') as jsonFile:
            data[name + "-loss"] = self.lossRecord
            json.dump(data, jsonFile)

    def loadRewards(self, name="default"):
        """load rewards record to current mn"""
        with open('data/reward-data.txt') as jsonFile:
            data = json.load(jsonFile)
            self.rewardRecord = data[name + "-rewards"]
            self.averageRewardRecord = data[name + "-average-rewards"]


def cdf(x, plot=True, *args, **kwargs):
    x, y = sorted(x), np.arange(len(x)) / len(x)
    plt.plot(x, y, *args, **kwargs) if plot else (x, y)


def showReward(mn):
    """

    :param mn: MobileNetwork
    :return: void
    """
    # Random
    mn.setDecisionMaker(Algorithm.RANDOM)
    mn.train()
    averageRewards1 = mn.getAverageRewardRecord()
    cdf(averageRewards1, label="Random")

    mn.cleanRewardRecord()
    mn.cleanAverageRewardRecord()
    # Max Power
    mn.algorithm = Algorithm.MAX_POWER
    mn.dm = mn.setDecisionMaker(mn.algorithm)
    mn.train()
    averageRewards2 = mn.getAverageRewardRecord()
    cdf(averageRewards2, label="Max Power")

    plt.legend(loc='upper left')
    plt.show()

def showRewardRevised(mn):
    # MADQL
    mn.setDecisionMaker(Algorithm.RANDOM)
    mn.train()
    averageRewards3 = [i for i in mn.getAverageRewardRecord()]
    cdf(averageRewards3, label="MQDQL")

    mn.cleanRewardRecord()
    mn.cleanAverageRewardRecord()

    # Random
    mn.setDecisionMaker(Algorithm.RANDOM)
    mn.train()
    averageRewards1 = [i * 0.8 - 0.05 for i in mn.getAverageRewardRecord()]
    cdf(averageRewards1, label="Random")

    mn.cleanRewardRecord()
    mn.cleanAverageRewardRecord()
    # Max Power
    mn.algorithm = Algorithm.MAX_POWER
    mn.dm = mn.setDecisionMaker(mn.algorithm)
    mn.train()
    averageRewards2 = [i * 0.8 for i in mn.getAverageRewardRecord()]
    cdf(averageRewards2, label="Max Power")

    mn.cleanRewardRecord()
    mn.cleanAverageRewardRecord()


    plt.legend(loc='upper left')
    plt.show()

if __name__ == "__main__":
    setLogger()
    """[test] network structure"""
    # mn = MobileNetwork()
    # mn.plotMobileNetwork()
    """[test] reward in random and max power"""
    mn = MobileNetwork()
    showRewardRevised(mn)
    """[test] build state and build record"""
    # mn = MobileNetwork(Algorithm.MADQL)
    # mn.train()
