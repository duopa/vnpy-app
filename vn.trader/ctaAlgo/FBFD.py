# -*- coding: utf-8 -*-
import pandas as pd
# 目录用相对路劲,用linux格式"/",不要用windows格式"\\" , 这样程序才可以在不同环境运行

k_data = pd.read_csv('../ctaAlgo/cache/000001.csv')
print k_data
merge_data = pd.DataFrame()
trend = 1  # 0:持平, # 1:向上. # -1:向下

i_tmp = 0
for i in range(1, len(k_data) - 1):  # 提取序列
    # same = temp_data.high[0] == k_data.high[i] and temp_data.low[0] == k_data.low[i]
    temp_data = k_data.loc[i-1]
    up = temp_data.high < k_data.high[i] and temp_data.low < k_data.low[i]
    down = temp_data.high > k_data.high[i] and temp_data.low > k_data.low[i]

    # if same:
    #     trend = 1  # 第一次输入时默认趋势向上
    #     continue
    if up:
        trend = 1
        merge_data[i_tmp] = temp_data
        i_tmp += 1
    elif down:
        trend = -1
        merge_data[i_tmp] = temp_data
        i_tmp += 1
    elif temp_data.high >= k_data.high[i] and temp_data.low <= k_data.low[i]:
        # 左边包含右边
        if trend == 1:  # 趋势向上
            temp_data.low = k_data.low[i]
        else:  # 趋势向下
            temp_data.high = k_data.high[i]

    elif temp_data.high <= k_data.high[i] and temp_data.low >= k_data.low[i]:
        # 右边包含左边
        if trend == 1:  # 趋势向上
            temp_data.high = k_data.high[i]
        else:  # 趋势向下
            temp_data.low = k_data.low[i]



    # 调整收盘价和开盘价
    # if temp_data.open[-1] > temp_data.close[-1]:
    #     if temp_data.open[-1] > temp_data.high[-1]:
    #         temp_data.open[-1] = temp_data.high[-1]
    #     if temp_data.close[-1] < temp_data.low[-1]:
    #         temp_data.close[-1] = temp_data.low[-1]
    # else:
    #     if temp_data.open[-1] < k_data.low[i-1]:
    #         temp_data.open[-1] = k_data.low[i-1]
    #     if temp_data.close[-1] > k_data.high[i-1]:
    #         temp_data.close[-1] = k_data.high[i-1]
    #
    # adjusted_data = k_data[i:i + 1]
    # adjusted_data.open[-1] = temp_data.open[-1]
    # adjusted_data.close[-1] = temp_data.close[-1]
    # adjusted_data.high[-1] = k_data.high[i-1]
    # adjusted_data.low[-1] = k_data.low[i-1]
    # merge_data = pd.concat([merge_data, adjusted_data], axis=0)
merge_data = merge_data.T
print(merge_data)
