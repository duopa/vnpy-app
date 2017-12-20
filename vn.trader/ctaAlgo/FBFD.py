# -*- coding: utf-8 -*-
import pandas as pd

k_data = pd.read_csv('C:\\xuye\\vnpy-app\\vn.trader\ctaAlgo\cache\\000001.csv')
merge_data = pd.DataFrame()
temp_data = k_data[0:1]  # 第一个数据
trend = 0  # 0:持平, # 1:向上. # -1:向下
for i in range(1, len(k_data) - 1):  # 提取序列
    same = temp_data.high[-1] == k_data.high[i] and temp_data.low[-1] == k_data.high[i]
    up = temp_data.high[-1] < k_data.high[i] and temp_data.low[-1] < k_data.low[i]
    down = temp_data.high[-1] > k_data.high[i] and temp_data.low[-1] > k_data.low[i]
    if same:
        trend = 1  # 第一次输入时默认趋势向上
        continue
    # 左边包含右边
    if temp_data.high[-1] >= k_data.high[i] and temp_data.low[-1] <= k_data.low[i] and not same:
        if trend == 1:  # 趋势向上
            temp_data.low[-1] = k_data.low[i]
        else:  # 趋势向下
            temp_data.high[-1] = k_data.high[i]
    # 右边包含左边
    if temp_data.high[-1] <= k_data.high[i] and temp_data.low[-1] >= k_data.low[i] and not same:
        if trend == 1:  # 趋势向上
            temp_data.high[-1] = k_data.high[i]
        else:  # 趋势向下
            temp_data.low[-1] = k_data.low[i]

    if up:
        trend = 1
        temp_data = k_data[i:i + 1]

    if down:
        trend = -1
        temp_data = k_data[i:i + 1]

    # 调整收盘价和开盘价
    if temp_data.open[-1] > temp_data.close[-1]:
        if temp_data.open[-1] > temp_data.high[-1]:
            temp_data.open[-1] = temp_data.high[-1]
        if temp_data.close[-1] < temp_data.low[-1]:
            temp_data.close[-1] = temp_data.low[-1]
    else:
        if temp_data.open[-1] < temp_data.low[-1]:
            temp_data.open[-1] = temp_data.low[-1]
        if temp_data.close[-1] > temp_data.high[-1]:
            temp_data.close[-1] = temp_data.high[-1]

    adjusted_data = k_data[i:i + 1]
    adjusted_data.open[-1] = temp_data.open[-1]
    adjusted_data.close[-1] = temp_data.close[-1]
    adjusted_data.high[-1] = temp_data.high[-1]
    adjusted_data.low[-1] = temp_data.low[-1]
    merge_data = pd.concat([merge_data, adjusted_data], axis=0)

print(merge_data)
