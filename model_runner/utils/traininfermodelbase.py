import abc
import pandas as pd
import typing


class TrainInferModelBase:

    @abc.abstractmethod
    def train(self,
              train_data: pd.DataFrame
              ):
        pass

    @abc.abstractmethod
    def infer(self,
              payload_stream: typing.Iterator[pd.DataFrame]
              ):
        pass