"""
* 账户模块, 存储资金修改, 负责对外部的成交单进行成交撮合 并扣除手续费 等操作
* 需要向外提供API
    trading: 发起交易
    is_traded: 是否可以进行交易
    result: 回测结果
"""

from collections import defaultdict

import numpy as np
from pandas import DataFrame

from ctpbee.constant import TradeData
from ctpbee.data_handle.local_position import LocalPositionManager


class AliasDayResult:
    """
    每天的结果
    """

    def __init__(self, **kwargs):
        """ 实例化进行调用 """
        for i, v in kwargs.items():
            setattr(self, i, v)

    def __repr__(self):
        result = "DailyResult: { "
        for x in dir(self):
            if x.startswith("_"):
                continue
            result += f"{x}:{getattr(self, x)} "
        return result + "}"

    def _to_dict(self):
        return self.__dict__


class Account:
    """
    账户类

    支持成交之后修改资金 ， 对外提供API

    """
    balance = 100000
    frozen = 0
    size = 5
    pricetick = 10
    daily_limit = 20
    commission: float = 0

    def __init__(self, interface):
        self.interface = interface
        self.position_manager = LocalPositionManager(interface.params)
        # 每日资金情况

        self.pre_balance = 0
        self.daily_life = defaultdict(AliasDayResult)
        self.date = None
        self.commission = 0
        self.commission_expense = 0
        self.pre_commission_expense = 0
        self.count_statistics = 0
        self.pre_count = 0
        self.initial_capital = 0

        self.init = False

    def is_traded(self, trade: TradeData) -> bool:
        """ 当前账户是否足以支撑成交 """
        # 根据传入的单子判断当前的账户资金和冻结 是否足以成交此单
        if trade.price * trade.volume < self.balance - self.frozen:
            """ 可用不足"""
            return False
        return True

    def update_trade(self, trade: TradeData) -> None:
        """
        当前选择调用这个接口的时候就已经确保了这个单子是可以成交的，

        make sure it can be traded if you choose to call this method,

        :param trade:交易单子/trade_id
        :return:
        """
        # 根据单子 更新当前的持仓 ----->
        if not self.date:
            self.date = self.interface.date
        if self.interface.date != self.date:
            """ 新的一天 """
            self.get_new_day()
            self.date = self.interface.date
        if self.commission != 0:
            commission_expense = trade.price * trade.volume
        else:
            commission_expense = 0
        self.balance -= commission_expense
        self.commission_expense += commission_expense
        # todo : 更新本地账户数据， 如果是隔天数据， 那么统计战绩 -----> AliasDayResult，然后推送到字典 。 以日期为key
        self.count_statistics += 1
        self.position_manager.update_trade(trade=trade)

    def get_new_day(self, interface_date):
        """ 获取到新的一天数据 """

        if not self.date:
            date = interface_date
        else:
            date = self.date
        p = AliasDayResult(
            **{"balance": self.balance, "frozen": self.frozen, "available": self.balance - self.frozen,
               "date": date, "commission": self.commission_expense - self.pre_commission_expense,
               "net_pnl": self.balance - self.pre_balance,
               "count": self.count_statistics - self.pre_count})

        self.pre_commission_expense = self.commission_expense
        self.pre_balance = self.balance
        self.pre_count = self.count_statistics
        self.daily_life[date] = p._to_dict()

        self.balance -= 10000

    def via_aisle(self):
        if self.interface.date != self.date:
            self.get_new_day(self.interface.date)
            self.date = self.interface.date
        else:
            pass

    def update_params(self, params: dict):
        """ 更新本地账户回测参数 """
        for i, v in params.items():
            if i == "initial_capital" and not self.init:
                self.balance = v
                self.pre_balance = v
                self.initial_capital = v
                self.init = True
            else:
                continue
            setattr(self, i, v)

    @property
    def result(self):
        # 根据daily_life里面的数据 获取最后的结果
        result = defaultdict(list)
        for daily in self.daily_life.values():
            for key, value in daily.items():
                result[key].append(value)
        df = DataFrame.from_dict(result).set_index("date")
        return self._cal_result(df)

    def _cal_result(self, df: DataFrame) -> dict:
        result = dict()
        df["return"] = np.log(df["balance"] / df["balance"].shift(1)).fillna(0)
        df["high_level"] = (
            df["balance"].rolling(
                min_periods=1, window=len(df), center=False).max()
        )
        df["draw_down"] = df["balance"] - df["high_level"]
        df["dd_percent"] = df["draw_down"] / df["high_level"] * 100
        result['initial_capital'] = self.initial_capital
        result['start_date'] = df.index[0]
        result['end_date'] = df.index[-1]
        result['total_days'] = len(df)
        result['profit_days'] = len(df[df["net_pnl"] > 0])
        result['loss_days'] = len(df[df["net_pnl"] < 0])
        result['end_balance'] = df["balance"].iloc[-1]
        result['max_draw_down'] = df["draw_down"].min()
        result['max_dd_percent'] = df["dd_percent"].min()
        result['total_pnl'] = df["net_pnl"].sum()
        result['daily_pnl'] = result['total_pnl'] / result['total_days']
        result['total_commission'] = df["commission"].sum()
        result['daily_commission'] = result['total_commission'] / result['total_days']
        # result['total_slippage'] = df["slippage"].sum()
        # result['daily_slippage'] = result['total_slippage'] / result['total_days']
        # result['total_turnover'] = df["turnover"].sum()
        # result['daily_turnover'] = result['total_turnover'] / result['total_days']
        result['total_count'] = df["count"].sum()
        result['daily_count'] = result['total_count'] / result['total_days']
        result['total_return'] = (result['end_balance'] / self.initial_capital - 1) * 100
        result['annual_return'] = result['total_return'] / result['total_days'] * 240
        result['daily_return'] = df["return"].mean() * 100
        result['return_std'] = df["return"].std() * 100
        return result
