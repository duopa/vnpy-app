# -*- coding: utf-8 -*-
# 来源：量化缠论之分型笔线段的识别
# 网址：https://www.joinquant.com/post/425?tag=new
def get_Fnk(n=5, security, start, end):
    '''
    获得k分钟k线函数
    '''
    import pandas as pd

    k_data = get_price(security, start_date=start, end_date=end, frequency='minute',
                       fields=['open', 'close', 'high', 'low'])

    # 去除9:00与13:00的数据
    for i in range(len(k_data) / 242):
        team = list(k_data.index)
        x = [s.strftime("%Y-%m-%d %H:%M:%S") for s in team]
        y = filter(lambda t: "09:30:00" in t, x)
        k_data = k_data.drop(k_data.index[x.index(y[0])])
        del x[x.index(y[0])]
        y = filter(lambda t: "13:00:00" in t, x)
        k_data = k_data.drop(k_data.index[x.index(y[0])])
        del x[x.index(y[0])]

    # 计算n分钟K线
    Fnk = pd.DataFrame()
    for i in xrange(n, len(k_data) + 1, n):
        temp = k_data[i - n: i]
        temp_open = temp.open[0]
        temp_high = max(temp.high)
        temp_low = min(temp.low)
        temp_k = temp[-1:]
        temp_k.open = temp_open
        temp_k.high = temp_high
        temp_k.low = temp_low
        Fnk = pd.concat([Fnk, temp_k], axis=0)
    return Fnk


def middle_num(k_data):
    # 鸡肋函数，完全的强迫症所为，只为下面画图时candle图中折线时好看而已 - -！
    # k_data 为DataFrame格式
    plot_data = []
    for i in xrange(len(k_data)):
        temp_y = (k_data.high[i] + k_data.low[i]) / 2.0
        plot_data.append(temp_y)
    return plot_data


import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.finance as mpf

k_data = get_Fnk(n=5, security='000001.XSHE', start='2015-12-02', end='2015-12-05')

## 判断包含关系
after_fenxing = pd.DataFrame()
temp_data = k_data[:1]
zoushi = [3]  # 3-持平 4-向下 5-向上
for i in xrange(len(k_data)):
    case1_1 = temp_data.high[-1] > k_data.high[i] and temp_data.low[-1] < k_data.low[i]  # 第1根包含第2根
    case1_2 = temp_data.high[-1] > k_data.high[i] and temp_data.low[-1] == k_data.low[i]  # 第1根包含第2根
    case1_3 = temp_data.high[-1] == k_data.high[i] and temp_data.low[-1] < k_data.low[i]  # 第1根包含第2根
    case2_1 = temp_data.high[-1] < k_data.high[i] and temp_data.low[-1] > k_data.low[i]  # 第2根包含第1根
    case2_2 = temp_data.high[-1] < k_data.high[i] and temp_data.low[-1] == k_data.low[i]  # 第2根包含第1根
    case2_3 = temp_data.high[-1] == k_data.high[i] and temp_data.low[-1] > k_data.low[i]  # 第2根包含第1根
    case3 = temp_data.high[-1] == k_data.high[i] and temp_data.low[-1] == k_data.low[i]  # 第1根等于第2根
    case4 = temp_data.high[-1] > k_data.high[i] and temp_data.low[-1] > k_data.low[i]  # 向下趋势
    case5 = temp_data.high[-1] < k_data.high[i] and temp_data.low[-1] < k_data.low[i]  # 向上趋势
    if case1_1 or case1_2 or case1_3:
        if zoushi[-1] == 4:
            temp_data.high[-1] = k_data.high[i]
        else:
            temp_data.low[-1] = k_data.low[i]

    elif case2_1 or case2_2 or case2_3:
        temp_temp = temp_data[-1:]
        temp_data = k_data[i:i + 1]
        if zoushi[-1] == 4:
            temp_data.high[-1] = temp_temp.high[0]
        else:
            temp_data.low[-1] = temp_temp.low[0]

    elif case3:
        zoushi.append(3)
        pass

    elif case4:
        zoushi.append(4)
        after_fenxing = pd.concat([after_fenxing, temp_data], axis=0)
        temp_data = k_data[i:i + 1]

    elif case5:
        zoushi.append(5)
        after_fenxing = pd.concat([after_fenxing, temp_data], axis=0)
        temp_data = k_data[i:i + 1]
# after_fenxing.head()

## 因为使用candlestick2函数，要求输入open、close、high、low。为了美观，处理k线的最大最小值、开盘收盘价，之后k线不显示影线。
for i in xrange(len(after_fenxing)):
    if after_fenxing.open[i] > after_fenxing.close[i]:
        after_fenxing.open[i] = after_fenxing.high[i]
        after_fenxing.close[i] = after_fenxing.low[i]
    else:
        after_fenxing.open[i] = after_fenxing.low[i]
        after_fenxing.close[i] = after_fenxing.high[i]

## 画出k线图
stock_middle_num = middle_num(after_fenxing)
fig, ax = plt.subplots(figsize=(50, 20))
fig.subplots_adjust(bottom=0.2)
mpf.candlestick2(ax, list(after_fenxing.open), list(after_fenxing.close), list(after_fenxing.high),
                 list(after_fenxing.low), width=0.6, colorup='r', colordown='b', alpha=0.75)
plt.grid(True)
dates = after_fenxing.index
ax.set_xticklabels(dates)  # Label x-axis with dates
# ax.autoscale_view()
plt.plot(stock_middle_num, 'k', lw=1)
plt.plot(stock_middle_num, 'ko')
plt.setp(plt.gca().get_xticklabels(), rotation=30)

## 找出顶和底
temp_num = 0  # 上一个顶或底的位置
temp_high = 0  # 上一个顶的high值
temp_low = 0  # 上一个底的low值
temp_type = 0  # 上一个记录位置的类型
i = 1
fenxing_type = []  # 记录分型点的类型，1为顶分型，-1为底分型
fenxing_time = []  # 记录分型点的时间
fenxing_plot = []  # 记录点的数值，为顶分型去high值，为底分型去low值
fenxing_data = pd.DataFrame()  # 分型点的DataFrame值
while (i < len(after_fenxing) - 1):
    case1 = after_fenxing.high[i - 1] < after_fenxing.high[i] and after_fenxing.high[i] > after_fenxing.high[
        i + 1]  # 顶分型
    case2 = after_fenxing.low[i - 1] > after_fenxing.low[i] and after_fenxing.low[i] < after_fenxing.low[i + 1]  # 底分型
    if case1:
        if temp_type == 1:  # 如果上一个分型为顶分型，则进行比较，选取高点更高的分型
            if after_fenxing.high[i] <= temp_high:
                i += 1
            # continue
            else:
                temp_high = after_fenxing.high[i]
                temp_num = i
                temp_type = 1
        elif temp_type == 2:  # 如果上一个分型为底分型，则记录上一个分型，用当前分型与后面的分型比较，选取同向更极端的分型
            if temp_low >= after_fenxing.high[i]:  # 如果上一个底分型的底比当前顶分型的顶高，则跳过当前顶分型。
                i += 1
            else:
                fenxing_type.append(-1)
                fenxing_time.append(after_fenxing.index[temp_num].strftime("%Y-%m-%d %H:%M:%S"))
                fenxing_data = pd.concat([fenxing_data, after_fenxing[temp_num:temp_num + 1]], axis=0)
                fenxing_plot.append(after_fenxing.high[i])
                temp_high = after_fenxing.high[i]
                temp_num = i
                temp_type = 1
                i += 4
        else:
            temp_high = after_fenxing.high[i]
            temp_num = i
            temp_type = 1
            i += 4

    elif case2:
        if temp_type == 2:  # 如果上一个分型为底分型，则进行比较，选取低点更低的分型
            if after_fenxing.low[i] >= temp_low:
                i += 1
            # continue
            else:
                temp_low = after_fenxing.low[i]
                temp_num = i
                temp_type = 2
                i += 4
        elif temp_type == 1:  # 如果上一个分型为顶分型，则记录上一个分型，用当前分型与后面的分型比较，选取同向更极端的分型
            if temp_high <= after_fenxing.low[i]:  # 如果上一个顶分型的底比当前底分型的底低，则跳过当前底分型。
                i += 1
            else:
                fenxing_type.append(1)
                fenxing_time.append(after_fenxing.index[temp_num].strftime("%Y-%m-%d %H:%M:%S"))
                fenxing_data = pd.concat([fenxing_data, after_fenxing[temp_num:temp_num + 1]], axis=0)
                fenxing_plot.append(after_fenxing.low[i])
                temp_low = after_fenxing.low[i]
                temp_num = i
                temp_type = 2
                i += 4
        else:
            temp_high = after_fenxing.low[i]
            temp_num = i
            temp_type = 2

    else:
        i += 1

print fenxing_type
print fenxing_time
print fenxing_plot

# 下面画出识别分型之后的走势图！
fig, ax = plt.subplots(figsize=(20, 5))
dates = fenxing_data.index
ax.set_xticklabels(dates)  # Label x-axis with dates
ax.autoscale_view()
plt.plot(fenxing_plot, 'k', lw=1)
plt.plot(fenxing_plot, 'o')
plt.grid(True)
plt.setp(plt.gca().get_xticklabels(), rotation=30)