# encoding: UTF-8

# 首先写系统内置模块
from datetime import datetime, timedelta, date
from time import sleep

# 其次，导入vnpy的基础模块
import sys

# sys.path.append('C:\\vnpy_1.5\\vnpy-master\\vn.trader')
sys.path.append('../')
from vtConstant import EMPTY_STRING, EMPTY_INT, DIRECTION_LONG, DIRECTION_SHORT, OFFSET_OPEN, STATUS_CANCELLED
from utilSinaClient import UtilSinaClient

# 然后是自己编写的模块
from ctaTemplate import *
from ctaBase import *
from ctaLineBar import *
from ctaPosition import *
from ctaPolicy import *
from ctaBacktesting import BacktestingEngine


class Strategy_MACD_01(CtaTemplate):
    """螺纹钢、15分钟级别MACD策略
    
    v1:15f上多空仓开仓
    v2:60f上的仓位管理体系
    v3:15f上的加仓减仓+开仓点位优化
    
    注意：策略用在不同品种上需要调整策略参数
    
    本版本现存问题：
    无
    
    已解决问题：
    15f上按照百分比开仓
    
    """
    className = 'Strategy_MACD'
    author = u'横纵19950206'

    # 策略在外部设置的参数

    # ----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting=None):
        """Constructor"""
        super(Strategy_MACD_01, self).__init__(ctaEngine, setting)

        # 增加监控参数项目

        # 增加监控变量项目
        self.varList.append('pos')  # 仓位，这里的仓位通常是手数
        self.varList.append('entrust')  # 是否正在委托，0表示没有委托，1多仓，-1空仓
        self.varList.append('percentLimit')  # 当前账户最大仓位
        self.varList.append('percent')  # 当前仓位

        self.curDateTime = None  # 当前Tick时间
        self.curTick = None  # 最新的tick
        self.lastOrderTime = None  # 上一次委托时间
        self.cancelSeconds = 60  # 撤单时间(秒)

        # 定义日内的交易窗口
        self.openWindow = False  # 开市窗口
        self.tradeWindow = False  # 交易窗口
        self.closeWindow = False  # 收市平仓窗口

        self.inited = False  # 是否完成了策略初始化
        self.backtesting = False  # 是否回测
        self.lineM15 = None  # 5分钟K线
        self.lineM60 = None  # 60分钟k线

        # 增加仓位管理模块
        self.position = CtaPosition(self)
        # self.position.longPos多头持仓，self.position.shorPos多头持仓、
        # self.position.pos持仓状态，self.position.maxPos最大持仓

        # 增加ctabacktesing中的仓位管理
        if not ctaEngine:
            self.engine = BacktestingEngine()
        else:
            self.engine = ctaEngine
        # 实时权益，可用资金，仓位比例，仓位比例上限
        self.capital, self.available, self.percent, self.percentLimit = self.engine.getAccountInfo()

        if setting:
            # 根据配置文件更新参数
            self.setParam(setting)

            # 创建的M15 K线
            lineM15Setting = {}
            lineM15Setting['name'] = u'M15'  # k线名称
            lineM15Setting['barTimeInterval'] = 60 * 15  # K线的Bar时长
            lineM15Setting['inputMacdFastPeriodLen'] = 12  # DIF快线
            lineM15Setting['inputMacdSlowPeriodLen'] = 26  # DEA慢线
            lineM15Setting['inputMacdSignalPeriodLen'] = 9  # MACD中绿柱
            lineM15Setting['shortSymbol'] = self.shortSymbol
            self.lineM15 = CtaLineBar(self, self.onBarM15, lineM15Setting)
            try:
                mode = setting['mode']
                if mode != EMPTY_STRING:
                    self.lineM15.setMode(setting['mode'])
            except KeyError:
                self.lineM15.setMode(self.lineM15.TICK_MODE)

        self.onInit()

    # ----------------------------------------------------------------------
    def onInit(self, force=False):
        """初始化 """
        if force:
            self.writeCtaLog(u'策略强制初始化')
            self.inited = False
            self.trading = False  # 控制是否启动交易
        else:
            self.writeCtaLog(u'策略初始化')
            if self.inited:
                self.writeCtaLog(u'已经初始化过，不再执行')
                return

        self.position.pos = EMPTY_INT  # 初始化持仓
        self.entrust = EMPTY_INT  # 初始化委托状态
        self.percent = EMPTY_INT  # 初始化仓位状态

        if not self.backtesting:
            # 这里需要加载前置数据哦。
            if not self.__initDataFromSina():
                return

        self.inited = True  # 更新初始化标识
        self.trading = True  # 启动交易

        self.putEvent()
        self.writeCtaLog(u'策略初始化完成')

    def __initDataFromSina(self):
        """从sina初始化5分钟数据"""
        sina = UtilSinaClient(self)
        ret = sina.getMinBars(symbol=self.symbol, minute=15, callback=self.lineM15.addBar)
        if not ret:
            self.writeCtaLog(u'获取M15数据失败')
            return False

        return True

    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog(u'启动')

    # ----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.uncompletedOrders.clear()
        self.position.pos = EMPTY_INT
        self.entrust = EMPTY_INT
        self.percent = EMPTY_INT

        self.writeCtaLog(u'停止')
        self.putEvent()

    # ----------------------------------------------------------------------
    def onTrade(self, trade):
        """交易更新"""
        self.writeCtaLog(u'{0},OnTrade(),当前持仓：{1},当前仓位：{2} '.format(self.curDateTime, self.position.pos, self.percent))

    # ----------------------------------------------------------------------
    def onOrder(self, order):
        """报单更新"""
        self.writeCtaLog(
            u'OnOrder()报单更新，orderID:{0},{1},totalVol:{2},tradedVol:{3},offset:{4},price:{5},direction:{6},status:{7}'
                .format(order.orderID, order.vtSymbol, order.totalVolume, order.tradedVolume,
                        order.offset, order.price, order.direction, order.status))

        # 委托单主键，vnpy使用 "gateway.orderid" 的组合
        orderkey = order.gatewayName + u'.' + order.orderID

        if orderkey in self.uncompletedOrders:
            if order.totalVolume == order.tradedVolume:
                # 开仓，平仓委托单全部成交
                # 平空仓完成(cover)
                if self.uncompletedOrders[orderkey]['DIRECTION'] == DIRECTION_LONG and order.offset != OFFSET_OPEN:
                    self.writeCtaLog(u'平空仓完成，原持仓:{0}，原仓位{1}'.format(self.position.pos, self.percent))
                    self.position.closePos(direction=DIRECTION_LONG, vol=order.tradedVolume)
                    self.writeCtaLog(u'新持仓:{0},新仓位{1}'.format(self.position.pos, self.percent))

                # 平多仓完成(sell)
                if self.uncompletedOrders[orderkey]['DIRECTION'] == DIRECTION_SHORT and order.offset != OFFSET_OPEN:
                    self.writeCtaLog(u'平空仓完成，原持仓:{0}，原仓位{1}'.format(self.position.pos, self.percent))
                    self.position.closePos(direction=DIRECTION_SHORT, vol=order.tradedVolume)
                    self.writeCtaLog(u'新持仓:{0},新仓位{1}'.format(self.position.pos, self.percent))

                # 开多仓完成
                if self.uncompletedOrders[orderkey]['DIRECTION'] == DIRECTION_LONG and order.offset == OFFSET_OPEN:
                    self.writeCtaLog(u'平空仓完成，原持仓:{0}，原仓位{1}'.format(self.position.pos, self.percent))
                    self.position.openPos(direction=DIRECTION_LONG, vol=order.tradedVolume, price=order.price)
                    self.writeCtaLog(u'新持仓:{0},新仓位{1}'.format(self.position.pos, self.percent))

                # 开空仓完成
                if self.uncompletedOrders[orderkey]['DIRECTION'] == DIRECTION_SHORT and order.offset == OFFSET_OPEN:
                    # 更新仓位
                    self.writeCtaLog(u'平空仓完成，原持仓:{0}，原仓位{1}'.format(self.position.pos, self.percent))
                    self.position.openPos(direction=DIRECTION_SHORT, vol=order.tradedVolume, price=order.price)
                    self.writeCtaLog(u'新持仓:{0},新仓位{1}'.format(self.position.pos, self.percent))

                del self.uncompletedOrders[orderkey]

                if len(self.uncompletedOrders) == 0:
                    self.entrust = 0
                    self.lastOrderTime = None

            elif order.tradedVolume > 0 and not order.totalVolume == order.tradedVolume and order.offset != OFFSET_OPEN:
                # 平仓委托单部分成交
                pass

            elif order.offset == OFFSET_OPEN and order.status == STATUS_CANCELLED:
                # 开仓委托单被撤销
                self.entrust = 0
                pass

            else:
                self.writeCtaLog(u'OnOrder()委托单返回，total:{0},traded:{1}'
                                 .format(order.totalVolume, order.tradedVolume, ))

        self.putEvent()  # 更新监控事件

    # ----------------------------------------------------------------------
    def onStopOrder(self, orderRef):
        """停止单更新"""
        self.writeCtaLog(u'{0},停止单触发，orderRef:{1}'.format(self.curDateTime, orderRef))
        pass

    # ----------------------------------------------------------------------
    def onTick(self, tick):
        """行情更新
        :type tick: object
        """
        self.curTick = tick

        if (tick.datetime.hour >= 3 and tick.datetime.hour <= 8) or (
                        tick.datetime.hour >= 16 and tick.datetime.hour <= 20):
            self.writeCtaLog(u'休市/集合竞价排名时数据不处理')
            return

        # 更新策略执行的时间（用于回测时记录发生的时间）
        self.curDateTime = tick.datetime

        # 2、计算交易时间和平仓时间
        self.__timeWindow(self.curDateTime)

        # 推送Tick到lineM15
        self.lineM15.onTick(tick)

        # 首先检查是否是实盘运行还是数据预处理阶段
        if not (self.inited and len(self.lineM15.inputMacdSlowPeriodLen) > 0):
            return

    # ----------------------------------------------------------------------
    def onBar(self, bar):
        """分钟K线数据更新（仅用于回测时，从策略外部调用)"""

        # 更新策略执行的时间（用于回测时记录发生的时间）
        # 回测数据传送的bar.datetime，为bar的开始时间，所以，到达策略时，当前时间为bar的结束时间
        self.curDateTime = bar.datetime + timedelta(seconds=self.lineM15.barTimeInterval)

        # 2、计算交易时间和平仓时间
        self.__timeWindow(bar.datetime)

        # 推送tick到15分钟K线
        self.lineM15.addBar(bar)
        # self.lineM60.addBar(bar)

        # 4、交易逻辑
        # 首先检查是否是实盘运行还是数据预处理阶段
        if not self.inited:
            if len(self.lineM15.lineBar) > 120 + 5:
                self.inited = True
            else:
                return

    def onBarM15(self, bar):
        """分钟K线数据更新，实盘时，由self.lineM15的回调"""

        # 调用lineM15的显示bar内容
        self.writeCtaLog(self.lineM15.displayLastBar())

        # 未初始化完成
        if not self.inited:
            if len(self.lineM15.lineBar) > 120 + 5:
                self.inited = True
            else:
                return

        # 执行撤单逻辑
        self.__cancelLogic(dt=self.curDateTime)

        if self.lineM15.mode == self.lineM15.TICK_MODE:
            idx = 2
        else:
            idx = 1

        # 收集前15个dif和dea的数据
        difdea = []

        jincha_15f_total = self.lineM15.lineDif[-1 - idx] < self.lineM15.lineDea[-1 - idx] \
                           and self.lineM15.lineDif[0 - idx] > self.lineM15.lineDea[0 - idx] \
                           and abs(self.lineM15.lineMacd[0 - idx]) >= 2
        jincha_15f_part = self.lineM15.lineDif[0 - idx] > self.lineM15.lineDea[0 - idx] \
                          and abs(self.lineM15.lineMacd[0 - idx]) >= 2
        sicha_15f_total = self.lineM15.lineDif[-1 - idx] > self.lineM15.lineDea[-1 - idx] \
                          and self.lineM15.lineDif[0 - idx] < self.lineM15.lineDea[0 - idx] \
                          and abs(self.lineM15.lineMacd[0 - idx]) >= 2
        sicha_15f_part = self.lineM15.lineDif[0 - idx] < self.lineM15.lineDea[0 - idx] \
                         and abs(self.lineM15.lineMacd[0 - idx]) >= 2
        # 用于止盈的策略变量
        up_4line = self.lineM15.lineMacd[-3 - idx] > self.lineM15.lineMacd[-2 - idx] > self.lineM15.lineMacd[
            -1 - idx] > self.lineM15.lineMacd[0 - idx] and self.lineM15.lineMacd[-3 - idx] >= 10
        down_4line = self.lineM15.lineMacd[-3 - idx] < self.lineM15.lineMacd[-2 - idx] < self.lineM15.lineMacd[
            -1 - idx] < self.lineM15.lineMacd[0 - idx] and self.lineM15.lineMacd[-3 - idx] <= -10

        # 如果未持仓，检查是否符合开仓逻辑
        if self.position.pos == 0:
            # DIF快线上穿DEA慢线，15f上金叉，做多
            # 多仓的时候记录前期顶分型的价格，并且以此价格的稍高位做为止损位
            if jincha_15f_total:
                self.percentLimit = 0.4
                vol = self.getAvailablePos(bar)
                if not vol:
                    return
                for n in range(15):
                    difdea.append(self.lineM15.lineDif[-n - idx])
                    difdea.append(self.lineM15.lineDea[-n - idx])

                if max(difdea) >= 25:  # 高位金叉，不开多仓
                    return

                if max(difdea) <= -30:  # 低位金叉，开重仓
                    self.percentLimit = self.percentLimit + 0.1
                    vol = self.getAvailablePos(bar)
                    if not vol:
                        return
                    self.writeCtaLog(u'{0},开仓多单{1}手,价格:{2}'.format(bar.datetime, vol, bar.close))
                    orderid = self.buy(price=bar.close, volume=vol, orderTime=self.curDateTime)
                    if orderid:
                        # 更新下单价格（为了定时撤单）
                        self.lastOrderTime = self.curDateTime
                    return
                else:  # 在-30到30的位置
                    self.writeCtaLog(u'{0},开仓多单{1}手,价格:{2}'.format(bar.datetime, vol, bar.close))
                    orderid = self.buy(price=bar.close, volume=vol, orderTime=self.curDateTime)
                    if orderid:
                        # 更新下单价格（为了定时撤单）
                        self.lastOrderTime = self.curDateTime
                    return

            # DIF快线下穿DEA慢线，15f上死叉，做空
            if sicha_15f_total:
                self.percentLimit = 0.4
                vol = self.getAvailablePos(bar)
                if not vol:
                    return

                for n in range(15):
                    difdea.append(self.lineM15.lineDif[-n - idx])
                    difdea.append(self.lineM15.lineDea[-n - idx])
                if max(difdea) >= 30:  # 高位死叉，开重仓
                    self.percentLimit = self.percentLimit + 0.1  # 50%
                    vol = self.getAvailablePos(bar)
                    if not vol:
                        return
                    self.writeCtaLog(u'{0},开仓多单{1}手,价格:{2}'.format(bar.datetime, vol, bar.close))
                    orderid = self.short(price=bar.close, volume=vol, orderTime=self.curDateTime)
                    if orderid:
                        # 更新下单价格（为了定时撤单）
                        self.lastOrderTime = self.curDateTime
                    return
                if max(difdea) <= -25:  # 低位死叉，不开单
                    return
                else:
                    self.writeCtaLog(u'{0},开仓多单{1}手,价格:{2}'.format(bar.datetime, vol, bar.close))
                    orderid = self.buy(price=bar.close, volume=vol, orderTime=self.curDateTime)
                    if orderid:
                        # 更新下单价格（为了定时撤单）
                        self.lastOrderTime = self.curDateTime
                    return

                    # 持仓，检查是否满足平仓条件
        # else:  # 持仓
        #     """
        #     这里减仓策略加入后收益降低了，回头得对着图核对一下，修改减仓策略
        #     """
            # # 多单减仓
            # if self.position.pos > 0 and self.entrust != -1 and up_4line:
            #     self.writeCtaLog(u'{0},平仓多单{1}手,价格:{2}'.format(bar.datetime, self.position.pos / 2, bar.close))
            #     orderid = self.sell(price=bar.close, volume=self.position.pos / 2, orderTime=self.curDateTime)
            #     if orderid:
            #         self.lastOrderTime = self.curDateTime
            #     return
            #
            # # 空单减仓
            # if self.position.pos < 0 and self.entrust != 1 and down_4line:
            #     self.writeCtaLog(u'{0},平仓空单{1}手,价格:{2}'.format(bar.datetime, self.position.pos / 2, bar.close))
            #     vol = self.position.pos * -1
            #     orderid = self.cover(price=bar.close, volume=vol / 2, orderTime=self.curDateTime)
            #     if orderid:
            #         self.lastOrderTime = self.curDateTime
            #     return

        # 如果已持仓，检查是否符合平仓条件
        if sicha_15f_part and self.position.pos > 0:
            self.writeCtaLog(u'{0},平仓多单{1}手,价格:{2}'.format(bar.datetime, self.position.pos, bar.close))
            orderid = self.sell(price=bar.close, volume=self.position.pos, orderTime=self.curDateTime)
            if orderid:
                self.lastOrderTime = self.curDateTime
            return

        # 金叉，空单离场
        if jincha_15f_part and self.position.pos < 0:
            self.writeCtaLog(u'{0},平仓空单{1}手,价格:{2}'.format(bar.datetime, self.position.pos, bar.close))
            vol = self.position.pos * -1
            orderid = self.cover(price=bar.close, volume=vol, orderTime=self.curDateTime)
            if orderid:
                self.lastOrderTime = self.curDateTime
            return

    # ----------------------------------------------------------------------
    def __cancelLogic(self, dt, force=False):
        "撤单逻辑"""

        if len(self.uncompletedOrders) < 1:
            return

        if not self.lastOrderTime:
            self.writeCtaLog(u'异常，上一交易时间为None')
            return

        # 平仓检查时间比开开仓时间需要短一倍
        if (self.position.pos >= 0 and self.entrust == 1) \
                or (self.position.pos <= 0 and self.entrust == -1):
            i = 1
        else:
            i = 1  # 原来是2，暂时取消

        canceled = False

        if ((dt - self.lastOrderTime).seconds > self.cancelSeconds / i) \
                or force:  # 超过设置的时间还未成交

            for order in self.uncompletedOrders.keys():
                self.writeCtaLog(u'{0}超时{1}秒未成交，取消委托单：{2}'.format(dt, (dt - self.lastOrderTime).seconds, order))

                self.cancelOrder(str(order))
                canceled = True

            # 取消未完成的订单
            self.uncompletedOrders.clear()

            if canceled:
                self.entrust = 0
            else:
                self.writeCtaLog(u'异常：没有撤单')

    def __timeWindow(self, dt):
        """交易与平仓窗口"""
        # 交易窗口 避开早盘和夜盘的前5分钟，防止隔夜跳空。

        self.closeWindow = False
        self.tradeWindow = False
        self.openWindow = False

        # 初始化当日的首次交易
        # if (tick.datetime.hour == 9 or tick.datetime.hour == 21) and tick.datetime.minute == 0 and tick.datetime.second ==0:
        #  self.firstTrade = True

        # 开市期，波动较大，用于判断止损止盈，或开仓
        if (dt.hour == 9 or dt.hour == 21) and dt.minute < 2:
            self.openWindow = True

        # 日盘
        if dt.hour == 9 and dt.minute >= 0:
            self.tradeWindow = True
            return

        if dt.hour == 10:
            if dt.minute <= 15 or dt.minute >= 30:
                self.tradeWindow = True
                return

        if dt.hour == 11 and dt.minute <= 30:
            self.tradeWindow = True
            return

        if dt.hour == 13 and dt.minute >= 30:
            self.tradeWindow = True
            return

        if dt.hour == 14:

            if dt.minute < 59:
                self.tradeWindow = True
                return

            if dt.minute == 59:  # 日盘平仓
                self.closeWindow = True
                return

        # 夜盘

        if dt.hour == 21 and dt.minute >= 0:
            self.tradeWindow = True
            return

        # 上期 贵金属， 次日凌晨2:30
        if self.shortSymbol in NIGHT_MARKET_SQ1:

            if dt.hour == 22 or dt.hour == 23 or dt.hour == 0 or dt.hour == 1:
                self.tradeWindow = True
                return

            if dt.hour == 2:
                if dt.minute < 29:  # 收市前29分钟
                    self.tradeWindow = True
                    return
                if dt.minute == 29:  # 夜盘平仓
                    self.closeWindow = True
                    return
            return

        # 上期 有色金属，黑色金属，沥青 次日01:00
        if self.shortSymbol in NIGHT_MARKET_SQ2:
            if dt.hour == 22 or dt.hour == 23:
                self.tradeWindow = True
                return

            if dt.hour == 0:
                if dt.minute < 59:  # 收市前29分钟
                    self.tradeWindow = True
                    return

                if dt.minute == 59:  # 夜盘平仓
                    self.closeWindow = True
                    return

            return

        # 上期 天然橡胶  23:00
        if self.shortSymbol in NIGHT_MARKET_SQ3:

            if dt.hour == 22:
                if dt.minute < 59:  # 收市前1分钟
                    self.tradeWindow = True
                    return

                if dt.minute == 59:  # 夜盘平仓
                    self.closeWindow = True
                    return

        # 郑商、大连 23:30
        if self.shortSymbol in NIGHT_MARKET_ZZ or self.shortSymbol in NIGHT_MARKET_DL:
            if dt.hour == 22:
                self.tradeWindow = True
                return

            if dt.hour == 23:
                if dt.minute < 29:  # 收市前1分钟
                    self.tradeWindow = True
                    return
                if dt.minute == 29 and dt.second > 30:  # 夜盘平仓
                    self.closeWindow = True
                    return
            return

    # ----------------------------------------------------------------------
    def strToTime(self, t, ms):
        """从字符串时间转化为time格式的时间"""
        hh, mm, ss = t.split(':')
        tt = datetime.time(int(hh), int(mm), int(ss), microsecond=ms)
        return tt

    # ----------------------------------------------------------------------
    def saveData(self, id):
        """保存过程数据"""
        # 保存K线
        if not self.backtesting:
            return

    # ----------------------------------------------------------------------
    def getAvailablePos(self, bar):
        """剩余可开仓数量"""
        # 实时权益，可用资金，仓位比例，仓位比例上限
        capital, avail, _, _ = self.engine.getAccountInfo()

        avail = min(avail, capital * self.percentLimit)
        midPrice = (bar.high - bar.low) / 2 + bar.low
        pricePerLot = self.engine.moneyPerLot(midPrice, self.vtSymbol)  # 每笔所需保证金
        if pricePerLot:
            return int(avail / pricePerLot)  # 剩余可加仓数量（整数）
        else:
            return None


def testRbByTick():
    # 创建回测引擎
    engine = BacktestingEngine()

    # 设置引擎的回测模式为Tick
    engine.setBacktestingMode(engine.TICK_MODE)

    # 设置回测用的数据起始日期
    engine.setStartDate('20100101')

    # 设置回测用的数据结束日期
    engine.setEndDate('20160330')

    # engine.connectMysql()
    engine.setDatabase(dbName='stockcn', symbol='rb')

    # 设置产品相关参数
    engine.setSlippage(0.5)  # 1跳（0.1）2跳0.2
    engine.setRate(float(0.0001))  # 万1
    engine.setSize(10)  # 合约大小

    settings = {}
    settings['vtSymbol'] = 'RB'
    settings['shortSymbol'] = 'RB'
    settings['name'] = 'MACD'
    settings['mode'] = 'tick'
    settings['backtesting'] = True

    # 在引擎中创建策略对象
    engine.initStrategy(Strategy_MACD_01, setting=settings)

    # 使用简单复利模式计算
    engine.usageCompounding = False  # True时，只针对FINAL_MODE有效

    # 启用实时计算净值模式REALTIME_MODE / FINAL_MODE 回测结束时统一计算模式
    engine.calculateMode = engine.REALTIME_MODE
    engine.initCapital = 100000  # 设置期初资金
    engine.percentLimit = 30  # 设置资金使用上限比例(%)
    engine.barTimeInterval = 60 * 5  # bar的周期秒数，用于csv文件自动减时间
    engine.fixCommission = 10  # 固定交易费用（每次开平仓收费）
    # 开始跑回测
    engine.runBacktestingWithMysql()

    # 显示回测结果
    engine.showBacktestingResult()


def testRbByBar():
    # 创建回测引擎
    engine = BacktestingEngine()

    # 设置引擎的回测模式为Tick
    engine.setBacktestingMode(engine.BAR_MODE)

    # 设置回测用的数据起始日期
    engine.setStartDate('20170101')

    # 设置回测用的数据结束日期
    engine.setEndDate('20170605')

    # engine.setDatabase(dbName='stockcn', symbol='rb')
    engine.setDatabase(dbName='stockcn', symbol='RB')

    # 设置产品相关参数
    engine.setSlippage(0.5)  # 1跳（0.1）2跳0.2
    engine.setRate(float(0.0003))  # 万3
    engine.setSize(10)  # 合约大小

    settings = {}
    # settings['vtSymbol'] = 'rb'
    settings['vtSymbol'] = 'RB'
    settings['shortSymbol'] = 'RB'
    settings['name'] = 'MACD'
    settings['mode'] = 'bar'
    settings['backtesting'] = True
    settings['percentLimit'] = 30

    # 在引擎中创建策略对象
    engine.initStrategy(Strategy_MACD_01, setting=settings)

    # 使用简单复利模式计算
    engine.usageCompounding = False  # True时，只针对FINAL_MODE有效

    # 启用实时计算净值模式REALTIME_MODE / FINAL_MODE 回测结束时统一计算模式
    engine.calculateMode = engine.REALTIME_MODE
    engine.initCapital = 100000  # 设置期初资金

    engine.percentLimit = 40  # 设置资金使用上限比例(%)
    engine.barTimeInterval = 300  # bar的周期秒数，用于csv文件自动减时间

    # 开始跑回测
    engine.runBackTestingWithBarFile(os.getcwd() + '/cache/RB99_20100101_20170605_15m.csv')

    # 显示回测结果
    engine.showBacktestingResult()


# 从csv文件进行回测
if __name__ == '__main__':
    # 提供直接双击回测的功能
    # 导入PyQt4的包是为了保证matplotlib使用PyQt4而不是PySide，防止初始化出错
    from ctaBacktesting import *
    from setup_logger import setup_logger

    setup_logger(
        filename=u'TestLogs/{0}_{1}.log'.format(Strategy_MACD_01.className, datetime.now().strftime('%m%d_%H%M')),
        debug=False
    )
    # 回测螺纹
    testRbByBar()
