import numpy as np
import pandas as pd

def transform_id_cols(df):
    #     df['id_01_cut'] = pd.cut(df['id_01'], bins=[-100, -30, -20, -10, -5, 0])

    df['id_05_d'] = df['id_05']
    df['id_05_d'].where(df[df['id_05_d'].notnull()]['id_05_d'] == 0, 1, inplace=True)

    #     df['id_06_cut'] = pd.cut(df['id_06'], bins=[-100, -10, -5, 0])
    df['id_06_d'] = df['id_06']
    df['id_06_d'].where(df[df['id_06_d'].notnull()]['id_06_d'] == 0, 1, inplace=True)

    # Dealing with id_30
    df['id_30_count'] = df['id_30'].map(df['id_30'].value_counts(dropna=False))
    df['System'] = df['id_30'].astype('str').str.split('.', expand=True)[0].str.split('_', expand=True)[0]
    df['SystemCorp'] = df['System'].str.split(expand=True)[0]

    # Dealing with id_31
    df['LastestBrowser'] = df['id_31']
    df.loc[
        df['LastestBrowser'].isin(['samsung browser 7.0', 'opera 53.0', 'mobile safari 10.0', 'chrome 63.0 for android',
                                   'google search application 49.0', 'firefox 60.0', 'edge 17.0', 'chrome 69.0',
                                   'chrome 67.0 for android', 'chrome 64.0', 'chrome 63.0 for ios', 'chrome 65.0',
                                   'chrome 64.0 for android', 'chrome 64.0 for ios', 'chrome 66.0',
                                   'chrome 65.0 for android', 'chrome 65.0 for ios', 'chrome 66.0 for android',
                                   'chrome 66.0 for ios']), 'LastestBrowser'] = 1
    df.loc[df['LastestBrowser'].str.len() > 1, 'LastestBrowser'] = 0

    df['id_31_count'] = df['id_31'].map(df['id_31'].value_counts(dropna=False))

    df['MSBrowser'] = df['id_31'].str.contains('edge|ie|microsoft', case=False) * 1
    df['AppleBrowser'] = df['id_31'].str.contains('safari', case=False) * 1
    df['GoogleBrowser'] = df['id_31'].str.contains('chrome', case=False) * 1
    df['BrowserType'] = df['id_31']
    df.loc[df['BrowserType'].str.contains('samsung', case=False, na=False), 'BrowserType'] = 'Samsung'
    df.loc[df['BrowserType'].str.contains('safari', case=False, na=False), 'BrowserType'] = 'Apple'
    df.loc[df['BrowserType'].str.contains('chrome|google', case=False, na=False), 'BrowserType'] = 'Google'
    df.loc[df['BrowserType'].str.contains('firefox', case=False, na=False), 'BrowserType'] = 'Mozilla'
    df.loc[df['BrowserType'].str.contains('edge|ie|microsoft', case=False, na=False,
                                          regex=True), 'BrowserType'] = 'Microsoft'
    df.loc[df['BrowserType'].isin(df['BrowserType'].value_counts()[df['BrowserType'].value_counts() < 1000].index), [
        'BrowserType']] = 'other'

    # Dealing with id_33
    df['id_33_count'] = df['id_33'].map(df['id_33'].value_counts(dropna=False))
    df['DisplaySize'] = df['id_33'].str.split('x', expand=True)[0].astype('float') * \
                        df['id_33'].str.split('x', expand=True)[1].astype('float')
    df['DisplaySize'].replace(0, np.nan, inplace=True)
    df['DisplaySize'] = (df['DisplaySize'] / df['DisplaySize'].min()).round(0)

    # Try easy combining
    for feature in ['id_02__id_20', 'id_13__id_17', 'id_02__D8', 'D11__DeviceInfo',
                    'DeviceInfo__P_emaildomain', 'card2__dist1', 'card1__card5',
                    'card2__id_20', 'card5__P_emaildomain', 'addr1__card1']:
        f1, f2 = feature.split('__')
        df[feature] = df[f1].astype(str) + '_' + df[f2].astype(str)
    for col in ['id_30', 'id_31', 'id_33', 'DeviceInfo']:
        df[col + '_DeviceTpye'] = train[col] + '_' + train['DeviceType']

    return df